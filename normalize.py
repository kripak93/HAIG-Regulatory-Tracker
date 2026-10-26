"""
Normalization and dedupe for the AI Regulatory Tracker.

Two jobs:
  1. Turn messy bill identifiers into a canonical form so (state, bill) is a
     reliable key:  "SB 903" / "SB903" / "sb903" -> "SB903".
  2. Dedupe the dataset on (state, normalized_bill), merging companion/duplicate
     rows rather than letting them inflate the counts.

Combined rows like "HB2368 / SB1444" are split into two keys so each bill is
tracked separately (they are companion bills, not one bill).
"""

from __future__ import annotations

import re
import json
from collections import OrderedDict

import schema


_BILL_RE = re.compile(r"^\s*([A-Za-z]+)\s*0*(\d+)\s*$")
# split on "/", "&", " and " when a row crammed two bill numbers together
_SPLIT_RE = re.compile(r"\s*(?:/|&|\band\b)\s*")


def normalize_bill_number(raw: str) -> str:
    """
    Canonicalize a single bill identifier.
      "SB 903"  -> "SB903"
      "sb903"   -> "SB903"
      "HB 0452" -> "HB452"   (leading zeros in the number dropped)
      "LD2082"  -> "LD2082"
    Non-standard identifiers (e.g. "CMS-2027-PFS-RPM/RTM") are returned
    uppercased-and-trimmed but otherwise untouched.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    # drop trailing parenthetical notes like "HB5003 (Introduced)"
    s = re.sub(r"\s*\(.*?\)\s*$", "", s).strip()
    m = _BILL_RE.match(s)
    if m:
        prefix, number = m.group(1).upper(), m.group(2)
        return f"{prefix}{number}"
    return s.upper()


def split_bill_identifiers(raw: str) -> list[str]:
    """
    "HB2368 / SB1444" -> ["HB2368", "SB1444"].
    Only splits when BOTH sides look like real bill numbers, so we don't
    shred identifiers like "CMS-2027-PFS-RPM/RTM".
    """
    if raw is None:
        return [""]
    parts = _SPLIT_RE.split(str(raw).strip())
    normd = [normalize_bill_number(p) for p in parts if p.strip()]
    # keep the split only if every part is a clean ALPHA+DIGITS bill id
    if len(normd) > 1 and all(_BILL_RE.match(f"{p[:2]} {p[2:]}") or re.match(r"^[A-Z]+\d+$", p) for p in normd):
        return normd
    return [normalize_bill_number(raw)]


def _parse_domain_scores(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw or str(raw).strip() in ("", "{}", "nan"):
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_list_field(raw) -> list[str]:
    """domains/mechs are stored as '; '-joined strings in the CSV."""
    if isinstance(raw, list):
        return [x.strip() for x in raw if str(x).strip()]
    if not raw or str(raw).strip() in ("", "nan"):
        return []
    return [x.strip() for x in str(raw).split(";") if x.strip()]


def canonicalize_row(row: dict) -> list[dict]:
    """
    Take one raw CSV row (dict) and return one or more canonical bill records.
    Returns a list because a combined "A / B" row expands into multiple records.
    """
    bill_ids = split_bill_identifiers(row.get("bill", ""))
    records = []
    for bill_id in bill_ids:
        rec = {
            "state": str(row.get("state", "")).strip().upper(),
            "bill": bill_id,
            "status": schema.normalize_status(row.get("status")),
            "status_raw": str(row.get("status", "")).strip(),
            "effective": str(row.get("effective", "")).strip(),
            "domains": _parse_list_field(row.get("domains")),
            "mechs": _parse_list_field(row.get("mechs")),
            "desc": str(row.get("desc", "")).strip(),
            "source": str(row.get("source", "")).strip(),
            "flag": str(row.get("flag", "")).strip().lower() in ("true", "1", "yes"),
            "severity": _parse_domain_scores(row.get("severity")),
            "domain_scores": _parse_domain_scores(row.get("domain_scores")),
        }
        records.append(rec)
    return records


def _merge_two(a: dict, b: dict) -> dict:
    """
    Merge a duplicate/companion record b into a. Prefers the more-advanced
    status and the richer (non-empty) fields. Unions domains and mechanisms.
    """
    out = dict(a)

    # keep the furthest-along status (highest status weight wins)
    if schema.status_weight(b["status"]) > schema.status_weight(a["status"]):
        out["status"] = b["status"]
        out["status_raw"] = b["status_raw"]

    out["domains"] = sorted(set(a["domains"]) | set(b["domains"]))
    out["mechs"] = sorted(set(a["mechs"]) | set(b["mechs"]))

    # prefer a non-flagged, longer description and a real source url
    if len(b["desc"]) > len(a["desc"]):
        out["desc"] = b["desc"]
    if (not a["source"]) or ("ailawsbystate.com/tools" in a["source"] and b["source"]):
        out["source"] = b["source"] or a["source"]
    if not a["effective"]:
        out["effective"] = b["effective"]

    # a flagged (mis-tagged) record stays flagged only if BOTH agree it's junk
    out["flag"] = a["flag"] and b["flag"]

    # keep the richer domain_scores (more keys / higher values)
    out["domain_scores"] = a["domain_scores"] if len(a["domain_scores"]) >= len(b["domain_scores"]) else b["domain_scores"]
    # union severities, keeping the higher value per domain
    sev = dict(a.get("severity", {}))
    for d, v in b.get("severity", {}).items():
        sev[d] = max(sev.get(d, 0.0), v)
    out["severity"] = sev
    return out


def dedupe(records: list[dict]) -> tuple[list[dict], list[tuple]]:
    """
    Collapse records on (state, bill). Returns (deduped_records, merged_pairs)
    where merged_pairs lists the (state, bill) keys that absorbed a duplicate,
    for the report.
    """
    index: "OrderedDict[tuple, dict]" = OrderedDict()
    merged = []
    for rec in records:
        key = (rec["state"], rec["bill"])
        if key in index:
            index[key] = _merge_two(index[key], rec)
            merged.append(key)
        else:
            index[key] = rec
    return list(index.values()), merged


# Prefix aliases that mean the same chamber in some states' numbering.
# Used ONLY for flagging suspected near-dupes, never for silent merging.
_PREFIX_ALIASES = [{"S", "SB"}, {"H", "HB"}, {"A", "AB"}]


def _prefix_and_number(bill: str) -> tuple[str, str]:
    m = re.match(r"^([A-Za-z]+)(\d+)$", bill)
    return (m.group(1), m.group(2)) if m else (bill, "")


def find_near_duplicates(records: list[dict]) -> list[tuple]:
    """
    Flag pairs that are probably the same bill but differ only by a prefix
    alias (RI S2197 vs SB2197) or by a near-identical description. Returns
    [(key_a, key_b, reason), ...] for the human-review report. Does NOT merge.
    """
    suspects = []
    by_state: dict[str, list[dict]] = {}
    for r in records:
        by_state.setdefault(r["state"], []).append(r)

    for st, recs in by_state.items():
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                a, b = recs[i], recs[j]
                pa, na = _prefix_and_number(a["bill"])
                pb, nb = _prefix_and_number(b["bill"])
                if na and na == nb and {pa, pb} in _PREFIX_ALIASES:
                    suspects.append(((st, a["bill"]), (st, b["bill"]),
                                     "prefix-alias same number"))
                elif a["desc"] and a["desc"] == b["desc"]:
                    suspects.append(((st, a["bill"]), (st, b["bill"]),
                                     "identical description"))
    return suspects


def load_and_clean_csv(path: str) -> tuple[list[dict], list[tuple]]:
    """Read the canonical CSV, expand combined rows, and dedupe."""
    import csv

    raw_rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_rows.extend(canonicalize_row(row))
    return dedupe(raw_rows)
