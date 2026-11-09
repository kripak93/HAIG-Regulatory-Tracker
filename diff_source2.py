"""
Cross-check: diff Source2 (Transparency Coalition enacted-law list) against the
current archive (Source1 = ailawsbystate, in bills.json). Shows what a second,
independent source would add or where the two disagree.
"""
from __future__ import annotations
import csv, json
import normalize

def load_source2(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            st = row["state"].strip().upper()
            bill = normalize.normalize_bill_number(row["bill"])
            out[(st, bill)] = row
    return out

def load_archive(path):
    d = json.load(open(path, encoding="utf-8"))
    out = {}
    for b in d["bills"]:
        out[(b["state"], normalize.normalize_bill_number(b["bill"]))] = b
    return out

s2 = load_source2("sources/source2_transparencycoalition.csv")
arc = load_archive("bills.json")

missing = sorted(set(s2) - set(arc))
present = sorted(set(s2) & set(arc))

print(f"Source2 (Transparency Coalition) laws: {len(s2)}")
print(f"  already in our archive: {len(present)}")
print(f"  NOT in our archive:     {len(missing)}")
print()
print("=== In Source2 but MISSING from our data ===")
for k in missing:
    r = s2[k]
    print(f"  {k[0]} {k[1]:<8} [{r['status']}] {r['category']} -- {r['desc'][:70]}")
print()
print("=== In both — status agreement check ===")
for k in present:
    a, r = arc[k], s2[k]
    flag = "" if a["bucket"] in ("Enacted","Effective") or r["status"]!="Enacted" else "  <-- source2 says enacted"
    print(f"  {k[0]} {k[1]:<8} ours={a['bucket']:<12} source2={r['status']}{flag}")
