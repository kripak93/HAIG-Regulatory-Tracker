"""
Source1 adapter: ailawsbystate.com healthcare-AI tracker (saved HTML page).

Parses every bill row out of the DB-driven table in a saved page and returns
canonical bill records. Category -> domain is auto-mapped via schema; mechanism
is intentionally left blank (classification stays a human/LLM step), so these
rows are status-complete but unscored until a mechanism is assigned.

The exhaustive archive keeps ALL statuses, including Dead/Failed/Vetoed — those
are labeled, not dropped.

Usage:
    from sources import source1_ailawsbystate as src1
    records = src1.parse("10-31_Source1.html")
"""

from __future__ import annotations

import os
import re
import sys
from html import unescape

# allow running both as a module and as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schema
import normalize

SOURCE_ID = "ailawsbystate"
SOURCE_URL = "https://www.ailawsbystate.com/tools/healthcare-ai-tracker"

_ROW_RE = re.compile(r'<tr data-state="([A-Z]{2})"\s+data-category="([^"]*)"[^>]*>(.*?)</tr>', re.S)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
# captures the FULL <td ...>...</td> including attributes, for reading data-sort
_TD_FULL_RE = re.compile(r"(<td[^>]*>.*?</td>)", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(r'href="(/law/[^"]+)"')
# flagship curated rows: plain <tr> whose first cell links to /state/XX
_FLAGSHIP_RE = re.compile(r'<tr>\s*<td><a href="/state/([A-Z]{2})">.*?</tr>', re.S)
_HTTP_RE = re.compile(r'href="(https?://[^"]+)"')

# descriptions the source uses as placeholders — treat as "no real description"
_GENERIC_DESCS = {
    "regulates ai in healthcare",
    "regulates ai use in utilization review or prior authorization",
    "regulates ai chatbots for mental health services",
    "governs ai-assisted clinical decisions or coding",
    "requires disclosure of ai use by healthcare providers",
}


def _is_generic(desc: str) -> bool:
    return desc.strip().lower() in _GENERIC_DESCS


def _text(html_fragment: str) -> str:
    return unescape(_TAG_RE.sub("", html_fragment)).strip()


def _parse_flagship(html: str) -> dict:
    """
    Parse the curated flagship table (richer descriptions + primary-source
    URLs). Returns {(state, bill): {desc, source, status, effective}}.
    """
    out: dict[tuple, dict] = {}
    for m in _FLAGSHIP_RE.finditer(html):
        state = m.group(1)
        tds_full = _TD_FULL_RE.findall(m.group(0))
        tds = [_TD_RE.match(c).group(1) for c in tds_full]
        if len(tds) < 6:
            continue
        bill = normalize.normalize_bill_number(_text(tds[1]))
        if not bill:
            continue
        eff = ""
        eff_m = re.search(r'data-sort="([^"]*)"', tds_full[3])
        if eff_m:
            eff = eff_m.group(1).strip()
        src_m = _HTTP_RE.search(tds[5])
        out[(state, bill)] = {
            "desc": _text(tds[4]),
            "source": src_m.group(1) if src_m else "",
            "status": schema.normalize_status(_text(tds[2])),
            "status_raw": _text(tds[2]),
            "effective": eff,
        }
    return out


def parse(path: str) -> dict:
    """Return {(state, bill): record} for every row in the source page."""
    with open(path, encoding="utf-8") as f:
        html = f.read()

    flagship = _parse_flagship(html)

    found: dict[tuple, dict] = {}
    for m in _ROW_RE.finditer(html):
        state = m.group(1)
        category = unescape(m.group(2)).strip()
        body = m.group(3)
        tds_full = _TD_FULL_RE.findall(body)
        tds = [_TD_RE.match(c).group(1) for c in tds_full]
        if len(tds) < 6:
            continue

        bill_raw = _text(tds[1])
        bill = normalize.normalize_bill_number(bill_raw)
        if not state or not bill:
            continue

        status = schema.normalize_status(_text(tds[2]))
        effective = ""
        eff_m = re.search(r'data-sort="([^"]*)"', tds_full[3])
        if eff_m:
            effective = eff_m.group(1).strip()
        desc = _text(tds[5])
        domain = schema.category_to_domain(category)

        # build a source url from the /law/ link if present
        href_m = _HREF_RE.search(tds[1])
        detail_path = href_m.group(1) if href_m else ""
        url = (SOURCE_URL.rsplit("/tools", 1)[0] + detail_path) if detail_path else SOURCE_URL

        key = (state, bill)
        rec = {
            "state": state,
            "bill": bill,
            "status": status,
            "status_raw": _text(tds[2]),
            "effective": effective,
            "domains": [domain] if domain else [],
            "mechs": [],                      # classification is a human/LLM step
            "desc": desc,
            "source": url,
            "detail_path": detail_path,       # /law/... page with the full summary
            "source_id": SOURCE_ID,
            "category_raw": category,
            "flag": False,
            "domain_scores": {},
        }

        # a state may list the same bill under two categories; union the domains
        if key in found:
            for d in rec["domains"]:
                if d not in found[key]["domains"]:
                    found[key]["domains"].append(d)
            # prefer the furthest-along status and the longer description
            if schema.status_weight(status) > schema.status_weight(found[key]["status"]):
                found[key]["status"] = status
                found[key]["status_raw"] = rec["status_raw"]
            if len(desc) > len(found[key]["desc"]):
                found[key]["desc"] = desc
            if not found[key]["effective"]:
                found[key]["effective"] = effective
        else:
            found[key] = rec

    # Overlay the curated flagship rows: richer description + primary-source URL
    # win over the generic DB-table text.
    for key, fl in flagship.items():
        if key not in found:
            continue
        rec = found[key]
        if fl["desc"] and (_is_generic(rec["desc"]) or len(fl["desc"]) > len(rec["desc"])):
            rec["desc"] = fl["desc"]
        if fl["source"]:
            rec["source"] = fl["source"]           # primary source beats /law/ link
        if not rec["effective"] and fl["effective"]:
            rec["effective"] = fl["effective"]
        if schema.status_weight(fl["status"]) > schema.status_weight(rec["status"]):
            rec["status"] = fl["status"]
            rec["status_raw"] = fl["status_raw"]

    return found


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "10-31_Source1.html"
    recs = parse(p)
    print(f"[{SOURCE_ID}] parsed {len(recs)} bills from {p}")
    buckets: dict[str, int] = {}
    unmapped = 0
    for r in recs.values():
        buckets[schema.status_bucket(r["status"])] = buckets.get(schema.status_bucket(r["status"]), 0) + 1
        if not r["domains"]:
            unmapped += 1
    print("  by status bucket:", dict(sorted(buckets.items())))
    print(f"  rows with no domain mapping: {unmapped}")
