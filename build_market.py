"""
Build the healthcare-AI market dataset from provider_table.txt.

Parses the ~950-company vendor table into market.json for the market dashboard:
  - segment -> category hierarchy (clean 5 -> 18)
  - per-company funding, stage, HQ, buyers, use-case themes
  - per-category aggregates (company count, capital raised, 2026 momentum, stage mix)

Usage:
    python build_market.py
"""

from __future__ import annotations

import csv
import json
import collections

from category_taxonomy import subgroup_for

SRC = "provider_table.txt"
OUT = "market.json"


def num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return 0.0


def split_list(s):
    return [p.strip() for p in str(s or "").split(";") if p.strip()]


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))

    companies = []
    for r in rows:
        cat = r.get("Category", "").strip()
        use_cases = split_list(r.get("Use cases", ""))
        companies.append({
            "name": r["Company"].strip(),
            "type": r.get("Company type", "").strip(),
            "segment": r.get("Segment", "").strip(),
            "category": cat,
            "subgroup": subgroup_for(cat, use_cases),
            "secondary": r.get("Secondary category", "").strip(),
            "desc": r.get("Description", "").strip(),
            "useCases": split_list(r.get("Use cases", "")),
            "buyers": split_list(r.get("Buyers", "")),
            "hq": r.get("HQ", "").strip(),
            "country": r.get("Country", "").strip(),
            "founded": r.get("Founded", "").strip(),
            "stage": r.get("Stage", "").strip(),
            "latestRound": num(r.get("Latest round ($M)")),
            "totalRaised": num(r.get("Total raised ($M)")),
            "raised2026": r.get("Raised in 2026", "").strip().lower() == "yes",
            "keyInvestors": split_list(r.get("Key investors", "")),
        })

    # category aggregates
    cats = collections.defaultdict(lambda: {
        "segment": "", "n": 0, "raised": 0.0, "r26": 0,
        "stages": collections.Counter(), "themes": collections.Counter(),
        "sub": collections.defaultdict(lambda: {"n": 0, "raised": 0.0, "r26": 0}),
    })
    for c in companies:
        key = c["category"] or "(uncategorized)"
        d = cats[key]
        d["segment"] = c["segment"]
        d["n"] += 1
        d["raised"] += c["totalRaised"]
        if c["raised2026"]:
            d["r26"] += 1
        d["stages"][c["stage"]] += 1
        for t in c["useCases"]:
            d["themes"][t] += 1
        sg = c["subgroup"] or "Other"
        sd = d["sub"][sg]
        sd["n"] += 1
        sd["raised"] += c["totalRaised"]
        if c["raised2026"]:
            sd["r26"] += 1

    from category_taxonomy import CATEGORY_SUBGROUPS
    categories = []
    for name, d in cats.items():
        # keep taxonomy order, then Other; drop empties
        order = [n for n, _ in CATEGORY_SUBGROUPS.get(name, [])] + ["Other"]
        subgroups = []
        for sg in order:
            if sg in d["sub"] and d["sub"][sg]["n"] > 0:
                s = d["sub"][sg]
                subgroups.append({"name": sg, "companies": s["n"],
                                  "raised": round(s["raised"], 1), "raised2026": s["r26"]})
        categories.append({
            "category": name,
            "segment": d["segment"],
            "companies": d["n"],
            "raised": round(d["raised"], 1),
            "raised2026": d["r26"],
            "stages": dict(d["stages"]),
            "topThemes": d["themes"].most_common(12),
            "subgroups": subgroups,
        })

    # segment aggregates
    segs = collections.defaultdict(lambda: {"n": 0, "raised": 0.0, "r26": 0, "cats": 0})
    for cat in categories:
        s = segs[cat["segment"]]
        s["n"] += cat["companies"]
        s["raised"] += cat["raised"]
        s["r26"] += cat["raised2026"]
        s["cats"] += 1
    segments = [{"segment": k, "companies": v["n"], "raised": round(v["raised"], 1),
                 "raised2026": v["r26"], "categories": v["cats"]} for k, v in segs.items()]

    data = {
        "generated_from": SRC,
        "total_companies": len(companies),
        "segments": sorted(segments, key=lambda x: -x["companies"]),
        "categories": sorted(categories, key=lambda x: -x["companies"]),
        "companies": companies,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {OUT}: {len(companies)} companies, {len(categories)} categories, {len(segments)} segments")


if __name__ == "__main__":
    main()
