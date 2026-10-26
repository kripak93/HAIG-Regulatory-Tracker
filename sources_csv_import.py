"""
CSV-import source adapter for the AI Regulatory Tracker.

A credential-free way to feed new/updated bills into the same pipeline the
LegiScan path uses. A human gathers facts from any source (primary legislature
sites, NCSL, a vendor's published llms.txt, etc.), drops them into a simple
CSV, and this adapter normalizes them into canonical bill records — identical
shape to what legiscan_scraper.normalize_hit produces — so dedupe / diff /
score / publish all work unchanged.

Expected import CSV columns (header row required):
    state, bill, status, effective, domains, mechs, desc, source

- state   : 2-letter code (US for federal)
- bill    : bill identifier (normalized by the pipeline)
- status  : any wording; mapped onto the canonical pipeline via schema
- effective: optional ISO-ish date or blank
- domains : one or more of the 7 canonical domains, '; '-joined
- mechs   : optional mechanism tag(s), '; '-joined (blank => unscored, flagged
            for classification, same as a fresh LegiScan hit)
- desc    : short description
- source  : PRIMARY-SOURCE url (statute / bill page), not an aggregator
"""

from __future__ import annotations

import csv

import schema
import normalize


def run_search_from_import(path: str) -> dict:
    """
    Read an import CSV and return {(state, bill): record}, matching the shape
    the orchestrator expects from a source.
    """
    found: dict[tuple, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            state = str(row.get("state", "")).strip().upper()
            bill = normalize.normalize_bill_number(row.get("bill", ""))
            if not state or not bill:
                continue
            domains = [d.strip() for d in str(row.get("domains", "")).split(";") if d.strip()]
            mechs = [m.strip() for m in str(row.get("mechs", "")).split(";") if m.strip()]
            rec = {
                "state": state,
                "bill": bill,
                "status": schema.normalize_status(row.get("status")),
                "status_raw": str(row.get("status", "")).strip(),
                "effective": str(row.get("effective", "")).strip(),
                "domains": [d for d in domains if d in schema.DOMAINS],
                "mechs": mechs,
                "desc": str(row.get("desc", "")).strip(),
                "source": str(row.get("source", "")).strip(),
                "flag": False,
                "domain_scores": {},
            }
            found[(state, bill)] = rec
    print(f"[csv-import] loaded {len(found)} bills from {path}")
    return found
