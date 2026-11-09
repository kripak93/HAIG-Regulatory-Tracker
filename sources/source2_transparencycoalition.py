"""
Source2 adapter: Transparency Coalition healthcare-AI enacted-law list.

A curated, primary-source-cited list extracted from the Transparency Coalition's
2026 healthcare-AI legislation report. Each row is in the import schema and
cited to its LegiScan/official page. Parsed into canonical records so it merges
with Source1 (ailawsbystate) via build_archive.py.

Category -> domain is auto-mapped; mechanism is left to the classification layer.
"""

from __future__ import annotations

import os
import sys
import csv
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schema
import normalize

SOURCE_ID = "transparencycoalition"
CSV_PATH = os.path.join(os.path.dirname(__file__), "source2_transparencycoalition.csv")


def parse(path: str = CSV_PATH) -> dict:
    found: dict[tuple, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            state = str(row.get("state", "")).strip().upper()
            bill = normalize.normalize_bill_number(row.get("bill", ""))
            if not state or not bill:
                continue
            domain = schema.category_to_domain(row.get("category", ""))
            found[(state, bill)] = {
                "state": state,
                "bill": bill,
                "status": schema.normalize_status(row.get("status")),
                "status_raw": str(row.get("status", "")).strip(),
                "effective": str(row.get("effective", "")).strip(),
                "domains": [domain] if domain else [],
                "mechs": [],
                "desc": str(row.get("desc", "")).strip(),
                "source": str(row.get("source", "")).strip(),
                "source_id": SOURCE_ID,
                "flag": False,
                "domain_scores": {},
            }
    return found


if __name__ == "__main__":
    recs = parse()
    print(f"[{SOURCE_ID}] parsed {len(recs)} bills")
