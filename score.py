"""
Scoring + regeneration for the AI Regulatory Tracker.

Recomputes per-bill domain scores from (status_weight x mechanism_severity),
then aggregates to per-state domain scores (max across that state's bills) and
regenerates the state-level CSV outputs.

A bill with explicit `mechs` is scored from the mechanism severity. A bill with
no mechanism (common for insurance/utilization-review rows) keeps whatever
domain_scores it already carries, so we don't zero out hand-tuned values.

New bills landed by the scraper with no mechanism and no domain_scores are
treated as UNSCORED and skipped (they contribute 0) until a human tags them.
"""

from __future__ import annotations

import csv
import json

import schema


US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def severity_by_domain(rec: dict) -> dict:
    """
    Return {domain: severity} (0-4) for a bill, independent of its current
    status. This is the stable "how strict" value that status weighting is
    later applied to.

    Priority:
      1. An explicit per-domain `severity` map already stored on the record.
      2. A mechanism tag -> its severity, applied to every tagged domain.
      3. Recovered from legacy `domain_scores`:  severity = score / status_weight
         (back-calculated once using the status the score was computed under).
    """
    domains = [d for d in rec.get("domains", []) if d in schema.DOMAINS]

    # 1. already-resolved severities
    stored = rec.get("severity")
    if isinstance(stored, dict) and stored:
        return {d: v for d, v in stored.items() if d in schema.DOMAINS}

    # 2. mechanism tag
    mechs = rec.get("mechs", [])
    if mechs and domains:
        top_sev = max(schema.mechanism_severity(m) for m in mechs)
        return {d: top_sev for d in domains}

    # 3. back out severity from legacy pre-computed domain_scores
    pre = {d: v for d, v in rec.get("domain_scores", {}).items() if d in schema.DOMAINS}
    if pre:
        sw = schema.status_weight(rec["status"])
        if sw > 0:
            return {d: round(v / sw, 3) for d, v in pre.items()}
    return {}


def score_bill(rec: dict) -> dict:
    """
    Return {domain: score} for one canonical bill record, computed fresh as
    status_weight(current_status) x severity(domain). Flagged bills score
    nothing. Bills with no resolvable severity (newly scraped, untagged) score
    nothing until a human classifies them.
    """
    if rec.get("flag"):
        return {}
    sw = schema.status_weight(rec["status"])
    return {d: round(sw * sev, 3) for d, sev in severity_by_domain(rec).items()}


def aggregate_by_state(records: list[dict]) -> dict:
    """
    -> { "CA": {"name": "California", "bill_count": N,
                "domains": {domain: max_score, ...}, "overall": x}, ... }
    """
    out = {
        abbr: {"name": name, "bill_count": 0,
               "domains": {d: 0.0 for d in schema.DOMAINS}, "overall": 0.0}
        for abbr, name in US_STATES.items()
    }

    for rec in records:
        st = rec["state"]
        if st not in out:
            continue  # skip federal "US" rows and anything non-state
        out[st]["bill_count"] += 1
        for domain, sc in score_bill(rec).items():
            if sc > out[st]["domains"][domain]:
                out[st]["domains"][domain] = sc

    for st in out:
        domain_scores = out[st]["domains"].values()
        out[st]["overall"] = round(max(domain_scores), 3) if domain_scores else 0.0
    return out


def write_domain_csv(state_agg: dict, path: str):
    header = ["state", "state_name", "bill_count"] + schema.DOMAINS + ["Overall"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for abbr in sorted(state_agg):
            s = state_agg[abbr]
            row = [abbr, s["name"], s["bill_count"]]
            row += [round(s["domains"][d], 3) for d in schema.DOMAINS]
            row.append(s["overall"])
            w.writerow(row)
    print(f"Wrote {path}")


def write_canonical_csv(records: list[dict], path: str):
    """Persist the cleaned, deduped, rescored dataset back to the CSV schema."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(schema.CSV_COLUMNS)
        for rec in records:
            # Resolve severity ONCE and persist it, so future status changes
            # rescore from a stable severity instead of re-deriving from a
            # score that was computed under a different status.
            sev = severity_by_domain(rec)
            rec["severity"] = sev
            scores = score_bill(rec)
            w.writerow([
                rec["state"],
                rec["bill"],
                rec["status"],
                rec.get("effective", ""),
                "; ".join(rec.get("domains", [])),
                "; ".join(rec.get("mechs", [])),
                rec.get("desc", ""),
                rec.get("source", ""),
                rec.get("flag", False),
                round(schema.status_weight(rec["status"]), 3),
                json.dumps(sev),
                json.dumps(scores),
            ])
    print(f"Wrote {path} ({len(records)} bills)")


def rescore_all(csv_path: str, out_canonical: str, out_domain_csv: str):
    """Full regeneration: clean -> score -> write canonical + state CSVs."""
    import normalize

    records, merged = normalize.load_and_clean_csv(csv_path)
    state_agg = aggregate_by_state(records)
    write_canonical_csv(records, out_canonical)
    write_domain_csv(state_agg, out_domain_csv)
    return records, state_agg, merged
