"""
One-off coverage check: diff the bills in a saved source-tracker HTML page
against our canonical import CSV, using the pipeline's own bill-number
normalizer so the comparison is apples-to-apples.

Usage:
    python coverage_diff.py 10-31_Source1.html import_livecompliance.csv
"""

from __future__ import annotations

import re
import sys
import csv
from html import unescape

import normalize


def parse_source_html(path: str) -> dict[tuple, dict]:
    """
    Pull every bill row out of the source tracker's big DB-driven table.
    Each row looks like:
        <tr data-state="AL" data-category="Utilization Review">
          ... <td> ... >SB 63< ... </td> ...
          <td>Enacted (Act 2026-589)</td>
    We grab state from data-state, the bill id from the 2nd <td>, and the
    status text from the 3rd <td>.
    """
    with open(path, encoding="utf-8") as f:
        html = f.read()

    found: dict[tuple, dict] = {}
    # each data-driven row
    for m in re.finditer(r'<tr data-state="([A-Z]{2})"[^>]*>(.*?)</tr>', html, re.S):
        state = m.group(1)
        body = m.group(2)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        if len(tds) < 3:
            continue
        # bill id is the text of the 2nd cell (strip any <a> tags)
        bill_cell = re.sub(r"<[^>]+>", "", tds[1])
        bill_raw = unescape(bill_cell).strip()
        status_cell = re.sub(r"<[^>]+>", "", tds[2])
        status = unescape(status_cell).strip()
        bill = normalize.normalize_bill_number(bill_raw)
        if not bill:
            continue
        key = (state, bill)
        # a state can list the same bill twice (curated + db); keep first status
        found.setdefault(key, {"state": state, "bill": bill,
                               "bill_raw": bill_raw, "status": status})
    return found


def parse_our_csv(path: str) -> dict[tuple, dict]:
    found: dict[tuple, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            state = str(row.get("state", "")).strip().upper()
            for bill in normalize.split_bill_identifiers(row.get("bill", "")):
                if not state or not bill:
                    continue
                found[(state, bill)] = {"state": state, "bill": bill,
                                        "status": row.get("status", "").strip()}
    return found


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else "10-31_Source1.html"
    csv_path = sys.argv[2] if len(sys.argv) > 2 else "import_livecompliance.csv"

    source = parse_source_html(src_path)
    ours = parse_our_csv(csv_path)

    src_keys = set(source)
    our_keys = set(ours)

    DEAD = ("dead", "failed", "vetoed")

    def is_dead(status: str) -> bool:
        s = status.lower()
        return any(d in s for d in DEAD)

    in_source_not_ours = sorted(src_keys - our_keys)
    in_ours_not_source = sorted(our_keys - src_keys)
    in_both = sorted(src_keys & our_keys)

    print(f"Source bills:        {len(src_keys)}")
    print(f"Our bills:           {len(our_keys)}")
    print(f"In both:             {len(in_both)}")
    print(f"In source, NOT ours: {len(in_source_not_ours)}")
    print(f"In ours, NOT source: {len(in_ours_not_source)}")
    print()

    live_missing = [k for k in in_source_not_ours if not is_dead(source[k]["status"])]
    dead_missing = [k for k in in_source_not_ours if is_dead(source[k]["status"])]

    print("=" * 70)
    print(f"LIVE bills in source but MISSING from ours ({len(live_missing)})")
    print("(enacted / in committee / introduced / passed — i.e. not dead)")
    print("=" * 70)
    for k in sorted(live_missing):
        s = source[k]
        print(f"  {k[0]:<3} {s['bill_raw']:<12} {s['status']}")

    print()
    print("=" * 70)
    print(f"DEAD/FAILED/VETOED in source, not ours ({len(dead_missing)})")
    print("(expected gaps — we track live law, these never became law)")
    print("=" * 70)
    for k in sorted(dead_missing):
        s = source[k]
        print(f"  {k[0]:<3} {s['bill_raw']:<12} {s['status']}")

    print()
    print("=" * 70)
    print(f"In OURS but not in source ({len(in_ours_not_source)})")
    print("(bills we have that the source tracker doesn't list)")
    print("=" * 70)
    for k in sorted(in_ours_not_source):
        print(f"  {k[0]:<3} {k[1]:<12} {ours[k]['status']}")


if __name__ == "__main__":
    main()
