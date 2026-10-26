"""
Orchestrator for the AI Regulatory Tracker automation.

The loop:
    fetch (LegiScan)
      -> normalize + dedupe
        -> diff against last snapshot
          -> write diff_report.txt   [STOP: human reviews]
            -> (re-run with --merge)
              -> merge new/changed into canonical CSV
                -> re-score + regenerate state CSV

Usage:
    python run_pipeline.py                 # live search, writes diff report only
    python run_pipeline.py --fixture f.json# offline search from a fixture
    python run_pipeline.py --merge         # apply the reviewed diff + rescore
    python run_pipeline.py --fixture f.json --merge

New bills land UNSCORED (no mechanism tag) and are listed in the report under
"NEEDS CLASSIFICATION" so a human assigns a mechanism before they count toward
any state's stringency. Nothing is ever merged without --merge.
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone

import os

import schema
import normalize
import score
import publish
import legiscan_scraper as scraper
import sources_csv_import as csv_source

CANONICAL_CSV = "bills_detailed_dataset.csv"
SNAPSHOT_PATH = "snapshot.json"
DIFF_REPORT_PATH = "diff_report.txt"
DOMAIN_CSV = "state_domain_stringency_scores.csv"
MAP_HTML = "genai_healthcare_stringency_map.html"


# --- snapshot persistence ------------------------------------------------------
def load_snapshot() -> dict:
    if not os.path.exists(SNAPSHOT_PATH):
        return {}
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {tuple(k.split("||")): v for k, v in data.items()}


def save_snapshot(bills: dict):
    data = {f"{k[0]}||{k[1]}": v for k, v in bills.items()}
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --- diff ----------------------------------------------------------------------
def diff(new_bills: dict, old_bills: dict):
    new_keys = set(new_bills) - set(old_bills)
    removed_keys = set(old_bills) - set(new_bills)
    changed = []
    for k in set(new_bills) & set(old_bills):
        if new_bills[k]["status"] != old_bills[k].get("status"):
            changed.append(k)
    return new_keys, changed, removed_keys


def write_report(new_bills, new_keys, changed, removed, near_dupes):
    ts = datetime.now(timezone.utc).isoformat()
    L = [f"AI Regulatory Tracker -- diff report -- {ts}", "=" * 60, ""]

    needs_class = [k for k in new_keys if not new_bills[k].get("mechs")]

    L.append(f"NEW BILLS ({len(new_keys)}):")
    for k in sorted(new_keys):
        b = new_bills[k]
        L.append(f"  + {k[0]} {k[1]} [{b['status']}] {b['domains']} -- {b['desc'][:90]}")
    L.append("")

    L.append(f"NEEDS CLASSIFICATION ({len(needs_class)}) -- assign a mechanism before these score:")
    for k in sorted(needs_class):
        L.append(f"  ? {k[0]} {k[1]} -- {new_bills[k]['desc'][:90]}")
    L.append("")

    L.append(f"STATUS CHANGES ({len(changed)}):")
    for k in sorted(changed):
        L.append(f"  ~ {k[0]} {k[1]} -- status moved to {new_bills[k]['status']}")
    L.append("")

    L.append(f"NO LONGER IN SEARCH ({len(removed)}) -- verify before marking dead:")
    for k in sorted(removed):
        L.append(f"  - {k[0]} {k[1]}")
    L.append("")

    L.append(f"SUSPECTED NEAR-DUPLICATES ({len(near_dupes)}) -- review, do not auto-merge:")
    for a, b, reason in near_dupes:
        L.append(f"  = {a[0]} {a[1]} <-> {b[1]}  ({reason})")

    report = "\n".join(L)
    with open(DIFF_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nDiff report -> {DIFF_REPORT_PATH}")
    print(f"  {len(new_keys)} new | {len(needs_class)} need classification | "
          f"{len(changed)} status changes | {len(removed)} dropped | {len(near_dupes)} near-dupes")
    return needs_class


# --- merge ---------------------------------------------------------------------
def merge(new_bills, new_keys, changed):
    """Apply reviewed diff into the canonical CSV, then rescore + regenerate.

    Reconciles against the canonical dataset directly rather than trusting the
    snapshot: any searched bill absent from the CSV is added, and any status
    advance is applied. This keeps merge correct even if the snapshot and the
    dataset have drifted out of sync.
    """
    records, merged = normalize.load_and_clean_csv(CANONICAL_CSV)
    index = {(r["state"], r["bill"]): r for r in records}

    added = updated = 0
    for k, incoming in new_bills.items():
        if k not in index:
            rec = {kk: vv for kk, vv in incoming.items()
                   if kk in ("state", "bill", "status", "effective", "domains",
                             "mechs", "desc", "source", "flag", "domain_scores")}
            records.append(rec)
            index[k] = rec
            added += 1
        else:
            # apply a status advance if the searched status is further along
            cur = index[k]
            if schema.status_weight(incoming["status"]) > schema.status_weight(cur["status"]):
                cur["status"] = incoming["status"]
                updated += 1

    state_agg = score.aggregate_by_state(records)
    score.write_canonical_csv(records, CANONICAL_CSV)
    score.write_domain_csv(state_agg, DOMAIN_CSV)

    # Republish the map in place (template == current map). Skip gracefully if
    # the map file isn't present.
    if os.path.exists(MAP_HTML):
        try:
            publish.regenerate_map(MAP_HTML, MAP_HTML, records, state_agg)
        except ValueError as e:
            print(f"[warn] map not regenerated: {e}")
    else:
        print(f"[warn] {MAP_HTML} not found; skipped map regeneration.")

    print(f"Merged: +{added} new, ~{updated} status updates. "
          f"Canonical set now {len(records)} bills.")


# --- entry point ---------------------------------------------------------------
def main(argv):
    do_merge = "--merge" in argv
    fixture = None
    if "--fixture" in argv:
        fixture = argv[argv.index("--fixture") + 1]

    source = "legiscan"
    if "--source" in argv:
        source = argv[argv.index("--source") + 1]
    import_file = None
    if "--file" in argv:
        import_file = argv[argv.index("--file") + 1]

    old = load_snapshot()
    if source == "csv":
        if not import_file:
            sys.exit("--source csv requires --file <path to import csv>")
        new = csv_source.run_search_from_import(import_file)
    elif fixture:
        new = scraper.run_search_from_fixture(fixture)
    else:
        new = scraper.run_search()

    new_keys, changed, removed = diff(new, old)

    # near-dupe check runs over the would-be-merged canonical set
    existing, _ = normalize.load_and_clean_csv(CANONICAL_CSV)
    near_dupes = normalize.find_near_duplicates(
        existing + [new[k] for k in new_keys]
    )

    write_report(new, new_keys, changed, removed, near_dupes)
    save_snapshot(new)

    if do_merge:
        merge(new, new_keys, changed)
    else:
        print("\nReview diff_report.txt, then re-run with --merge to apply.")


if __name__ == "__main__":
    main(sys.argv[1:])
