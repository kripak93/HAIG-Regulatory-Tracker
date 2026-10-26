"""
Map republishing for the AI Regulatory Tracker.

Regenerates the embedded data in the stringency map HTML from the current
canonical dataset. The map template embeds two JS arrays on their own lines:

    const SCORE_DATA = [ ...per-state aggregate... ];
    const BILL_DATA  = [ ...per-bill detail... ];

We rewrite exactly those two lines, leaving all the SVG/CSS/JS rendering code
untouched. This keeps the hand-built visualization intact while refreshing the
numbers after a merge.
"""

from __future__ import annotations

import re
import json

import schema
import score


def build_score_data(state_agg: dict) -> list[dict]:
    """Per-state records in the exact shape the map's SCORE_DATA expects."""
    rows = []
    for abbr in sorted(state_agg):
        s = state_agg[abbr]
        row = {"state": abbr, "state_name": s["name"], "bill_count": s["bill_count"]}
        for d in schema.DOMAINS:
            row[d] = round(s["domains"][d], 3)
        row["Overall"] = s["overall"]
        rows.append(row)
    return rows


def build_bill_data(records: list[dict]) -> list[dict]:
    """Per-bill records for the map's BILL_DATA drill-down array."""
    rows = []
    for rec in records:
        rows.append({
            "state": rec["state"],
            "bill": rec["bill"],
            "status": rec["status"],
            "effective": rec.get("effective", ""),
            "mechs": rec.get("mechs", []),
            "desc": rec.get("desc", ""),
            "source": rec.get("source", ""),
            "flag": bool(rec.get("flag", False)),
            "status_weight": round(schema.status_weight(rec["status"]), 3),
            "domains": rec.get("domains", []),
            "domain_scores": score.score_bill(rec),
        })
    return rows


def _splice_const(html: str, const_name: str, payload: list) -> str:
    """
    Replace the line `const <const_name> = [...];` with a fresh one.
    Matches non-greedily to the first `];` so SCORE_DATA and BILL_DATA don't
    bleed into each other.
    """
    pattern = re.compile(
        r"const\s+" + re.escape(const_name) + r"\s*=\s*\[.*?\];",
        re.DOTALL,
    )
    replacement = f"const {const_name} = {json.dumps(payload)};"
    # Pass replacement via a lambda so backslashes in the JSON (e.g. \u2014 for
    # em-dashes) are treated literally, not as regex-template escapes.
    new_html, n = pattern.subn(lambda _m: replacement, html, count=1)
    if n == 0:
        raise ValueError(f"Could not find `const {const_name} = [...]` in template.")
    return new_html


def regenerate_map(template_path: str, out_path: str, records: list[dict], state_agg: dict):
    """Read the template map, splice in fresh data, write the published map."""
    with open(template_path, encoding="utf-8") as f:
        html = f.read()

    html = _splice_const(html, "SCORE_DATA", build_score_data(state_agg))
    if "BILL_DATA" in html:
        html = _splice_const(html, "BILL_DATA", build_bill_data(records))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Published map -> {out_path}")
