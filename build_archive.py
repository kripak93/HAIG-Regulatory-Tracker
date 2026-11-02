"""
Build the exhaustive AI-regulation archive from source adapters.

Pipeline:
    for each source adapter -> parse() -> canonical records
      -> merge all sources (dedupe on (state, bill); furthest-along status wins)
        -> classify (category->domain already set by the adapter; score via score.py)
          -> write bills_archive.csv   (every bill, every status — nothing dropped)
          -> write bills.json          (map-ready: per-bill + per-state buckets)

Exhaustive by design: Dead / Failed / Vetoed bills are KEPT and labeled, not
filtered. Add a new web source by dropping another adapter in sources/ and
listing it in SOURCES below — then re-run this on your cadence.

Usage:
    python build_archive.py
"""

from __future__ import annotations

import os
import csv
import json
from datetime import datetime, timezone

import schema
import score
from sources import source1_ailawsbystate as src1

ENRICHMENT_CSV = "enrichment_ailawsbystate.csv"

TODAY = datetime.now(timezone.utc).date().isoformat()


def effective_bucket(rec: dict, today: str = TODAY) -> str:
    """
    Refine the display bucket using the effective date.

    The source labels signed laws "Enacted" without saying whether they're live.
    We compute it: an enacted/effective bill whose effective date has passed is
    Effective (in force now); one with a future effective date is Enacted
    (on the books, not yet enforceable). Everything else keeps its base bucket.
    """
    base = schema.status_bucket(rec["status"])
    if base not in ("Enacted", "Effective"):
        return base
    eff = (rec.get("effective") or "").strip()
    if eff and eff <= today:
        return "Effective"
    if eff and eff > today:
        return "Enacted"
    # enacted but no date recorded -> treat as Enacted (don't assume it's live)
    return "Enacted"


def timeline_date(rec: dict) -> str:
    """Best available date for the time slider: the effective date if known."""
    return (rec.get("effective") or "").strip()


def load_enrichment(path: str) -> dict:
    """{(state, bill): {title, desc, official_source, summary_caveat}}."""
    out: dict[tuple, dict] = {}
    if not os.path.exists(path):
        print(f"  [warn] {path} not found — run enrich_ailawsbystate.py for real descriptions.")
        return out
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["state"].strip().upper(), row["bill"].strip().upper())
            out[key] = row
    return out

# Register source adapters here. Order = merge precedence (earlier wins ties,
# but status still advances to the furthest-along across all sources).
SOURCES = [
    (src1, "10-31_Source1.html"),
]

ARCHIVE_CSV = "bills_archive.csv"
ARCHIVE_JSON = "bills.json"
SCHEMA_VERSION = "2.0-archive"


def merge_sources() -> dict:
    """Parse every registered source and merge into one {(state,bill): rec}."""
    merged: dict[tuple, dict] = {}
    for adapter, path in SOURCES:
        recs = adapter.parse(path)
        print(f"  [{adapter.SOURCE_ID}] {len(recs)} bills from {path}")
        for key, rec in recs.items():
            if key not in merged:
                merged[key] = rec
                continue
            cur = merged[key]
            # union domains
            for d in rec["domains"]:
                if d not in cur["domains"]:
                    cur["domains"].append(d)
            # furthest-along status wins
            if schema.status_weight(rec["status"]) > schema.status_weight(cur["status"]):
                cur["status"] = rec["status"]
                cur["status_raw"] = rec.get("status_raw", "")
            # richer fields
            if len(rec.get("desc", "")) > len(cur.get("desc", "")):
                cur["desc"] = rec["desc"]
            if not cur.get("effective"):
                cur["effective"] = rec.get("effective", "")
            cur.setdefault("source_ids", {cur.get("source_id")})
            cur["source_ids"].add(rec.get("source_id"))
    return merged


def write_archive_csv(records: list[dict], path: str):
    cols = ["state", "bill", "title", "status", "status_bucket", "effective",
            "domains", "mechs", "desc", "source", "summary_caveat", "source_id",
            "status_weight", "severity", "domain_scores"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for rec in records:
            sev = score.severity_by_domain(rec)
            rec["severity"] = sev
            scores = score.score_bill(rec)
            w.writerow([
                rec["state"], rec["bill"], rec.get("title", ""), rec["status"],
                schema.status_bucket(rec["status"]),
                rec.get("effective", ""),
                "; ".join(rec.get("domains", [])),
                "; ".join(rec.get("mechs", [])),
                rec.get("desc", ""),
                rec.get("source", ""),
                rec.get("summary_caveat", ""),
                rec.get("source_id", ""),
                round(schema.status_weight(rec["status"]), 3),
                json.dumps(sev),
                json.dumps(scores),
            ])
    print(f"Wrote {path} ({len(records)} bills)")


def build_json(records: list[dict]) -> dict:
    """Map-ready structure: per-bill list + per-state bucket counts."""
    bills = []
    # per-state: counts per status bucket + the live stringency score
    states: dict[str, dict] = {}
    for rec in records:
        bucket = effective_bucket(rec)
        scores = score.score_bill(rec)
        overall = max(scores.values()) if scores else 0.0
        bill_obj = {
            "state": rec["state"],
            "bill": rec["bill"],
            "title": rec.get("title", ""),
            "status": rec["status"],
            "bucket": bucket,
            "effective": rec.get("effective", ""),
            "timeline_date": timeline_date(rec),
            "domains": rec.get("domains", []),
            "desc": rec.get("desc", ""),
            "source": rec.get("source", ""),
            "caveat": rec.get("summary_caveat", ""),
            "score": round(overall, 3),
        }
        bills.append(bill_obj)

        st = rec["state"]
        if st not in states:
            states[st] = {b: 0 for b in schema.STATUS_BUCKETS}
            states[st]["total"] = 0
            states[st]["stringency"] = 0.0
        states[st][bucket] += 1
        states[st]["total"] += 1
        # live stringency = max score among live (enacted/effective) bills only
        if bucket in ("Effective", "Enacted") and overall > states[st]["stringency"]:
            states[st]["stringency"] = round(overall, 3)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [a.SOURCE_ID for a, _ in SOURCES],
        "status_buckets": schema.STATUS_BUCKETS,
        "domains": schema.DOMAINS,
        "counts": {
            "total": len(bills),
            "by_bucket": {b: sum(1 for x in bills if x["bucket"] == b)
                          for b in schema.STATUS_BUCKETS},
        },
        "states": states,
        "bills": sorted(bills, key=lambda b: (b["state"], b["bill"])),
    }


def main():
    print("Building exhaustive archive from sources...")
    merged = merge_sources()
    records = list(merged.values())
    print(f"Merged total: {len(records)} distinct bills")

    # Overlay per-bill enrichment (real title + summary + official source URL).
    enrich = load_enrichment(ENRICHMENT_CSV)
    enriched = 0
    for rec in records:
        e = enrich.get((rec["state"], rec["bill"]))
        if not e:
            continue
        if e.get("desc"):
            rec["desc"] = e["desc"]
            enriched += 1
        if e.get("title"):
            rec["title"] = e["title"]
        if e.get("official_source"):
            rec["source"] = e["official_source"]   # official legislature URL is the primary source
        if e.get("summary_caveat"):
            rec["summary_caveat"] = e["summary_caveat"]
    print(f"Enriched {enriched} bills with full descriptions from detail pages.")

    write_archive_csv(records, ARCHIVE_CSV)

    data = build_json(records)
    with open(ARCHIVE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {ARCHIVE_JSON}")
    print("  by bucket:", data["counts"]["by_bucket"])


if __name__ == "__main__":
    main()
