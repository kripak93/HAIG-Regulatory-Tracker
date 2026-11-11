"""
Build stakeholder value-chain pathways from provider_table.txt -> pathways.json.

Produces, for each of three stakeholder lenses (Provider, Patient, Payer), a set
of ordered value-chain STAGES, with every company placed on the stage(s) it
occupies in that pathway. Also produces an OVERVIEW that quantifies how skewed
the market is toward the provider (the headline finding).

Stage assignment is driven primarily by the clean workflow Category (defensible),
refined by use-case keywords where needed. A company can appear on different
stages in different pathways (e.g. a prior-auth tool = "Bill & Collect" for the
provider but "Utilization & Claims" for the payer).

Usage: python build_pathways.py
"""

from __future__ import annotations
import csv, json, os, collections

from category_taxonomy import subgroup_for

SRC = "provider_table.txt"
OUT = "pathways.json"
ATTRIBUTION = "attribution.json"  # LLM/rule funding-attribution (primary stage, patient-facing)


def num(x):
    try: return float(str(x).strip())
    except Exception: return 0.0

def lst(s): return [p.strip() for p in str(s or "").split(";") if p.strip()]


# ---- Provider journey: category -> stage ----
PROVIDER_STAGE = {
    "Patient Access & Contact Center": "1. Access & Intake",
    "Imaging & Radiology": "2. Diagnose",
    "Pathology & Diagnostics": "2. Diagnose",
    "Clinical Decision Support": "3. Clinical Decision",
    "Patient Monitoring & Early Warning": "3. Clinical Decision",
    "Surgical & Procedural AI": "4. Treat",
    "Ambient Documentation": "5. Document",
    "Coding, CDI & Chart Review": "6. Code",
    "Revenue Cycle & Prior Auth": "7. Bill & Collect",
    "Care Management & Virtual Care": "8. Ongoing Care",
    "Post-Acute & Home Care": "8. Ongoing Care",
    "Hospital Operations & Capacity": "Ops & Infrastructure",
    "Workforce & Credentialing": "Ops & Infrastructure",
    "Pharmacy & Supply Chain": "Ops & Infrastructure",
    "AI Infrastructure & Governance": "Ops & Infrastructure",
    "Data, Quality & Value-Based Care": "Ops & Infrastructure",
    "Clinical Research & Trials": "Ops & Infrastructure",
    "Dental AI": "2. Diagnose",
}
PROVIDER_ORDER = ["1. Access & Intake","2. Diagnose","3. Clinical Decision","4. Treat",
    "5. Document","6. Code","7. Bill & Collect","8. Ongoing Care","Ops & Infrastructure"]

# ---- Sub-steps within each provider stage ----
# Each sub-step is (name, [keyword substrings]). A company is placed on the FIRST
# sub-step whose keywords match any of its use-case tokens; unmatched -> "Other".
# Keep rules specific-first so e.g. "triage" wins over generic "scheduling".
SUBSTEPS = {
  "1. Access & Intake": [
    ("Symptom check & triage", ["triage","symptom","navigation"]),
    ("Voice / front-desk agents", ["voice","receptionist","phone agent","call center","call automation"]),
    ("Scheduling & booking", ["scheduling","appointment","booking","no-show","reminder","confirmation"]),
    ("Patient intake & forms", ["intake","registration","pre-visit","questionnaire","forms"]),
    ("Referral & fax intake", ["referral","fax"]),
    ("Outreach & reactivation", ["outreach","reactivation","care gap","recall"]),
    ("Interpretation & access", ["interpret","translation","language","eligibility","insurance verification"]),
  ],
  "2. Diagnose": [
    ("Radiology imaging AI", ["x-ray","radiology","ct","mri","mammograph","imaging","nodule","fracture","stroke","image"]),
    ("Pathology & lab AI", ["pathology","biopsy","cell","blood smear","histolog","lab"]),
    ("Cardiac / ECG / echo", ["ecg","echo","cardiac","ejection","arrhythmia","coronary","heart"]),
    ("Ophthalmology / retina", ["retina","retinal","diabetic retinopathy","eye","fundus"]),
    ("Diagnostic decision support", ["diagnos","screening","risk","detection","triage"]),
  ],
  "3. Clinical Decision": [
    ("Deterioration & early warning", ["deterioration","sepsis","early warning","monitoring","vital"]),
    ("Evidence & reference", ["evidence","guideline","reference","knowledge","literature","answers"]),
    ("Clinical pathways & CDS", ["pathway","decision support","order","differential","reasoning","diagnosis"]),
    ("Medication & dosing", ["medication","dosing","drug","prescrib","polypharmacy"]),
  ],
  "4. Treat": [
    ("Surgical navigation", ["navigation","surgical","intraoperative","ar ","3d"]),
    ("Surgical robotics", ["robot","robotic"]),
    ("OR video & analytics", ["video","computer vision","or ","perfusion","instrument"]),
  ],
  "5. Document": [
    ("Ambient scribe", ["ambient","scribe","notes","dictation","documentation"]),
    ("Coding-aware docs", ["coding","cdi","e/m","hcc","charge"]),
    ("Specialty / nursing docs", ["nursing","specialty","discharge","referral letter","handoff"]),
  ],
  "6. Code": [
    ("Autonomous coding", ["autonomous coding","coding","charge capture","e/m","cpt","icd"]),
    ("CDI & chart review", ["cdi","chart review","documentation","abstraction"]),
    ("Risk adjustment / HCC", ["risk adjustment","hcc","radv"]),
    ("Audit & compliance", ["audit","compliance","pre-bill","quality"]),
  ],
  "7. Bill & Collect": [
    ("Prior authorization", ["prior auth","authorization","preauth","gold card"]),
    ("Eligibility & benefits", ["eligibility","benefits","coverage","insurance verification","verification"]),
    ("Denials & appeals", ["denial","appeal","underpayment","claim status","claims follow"]),
    ("Claims & coding submission", ["claim","coding","scrub","submission"]),
    ("Patient billing & payments", ["patient billing","patient payment","payment posting","estimate","collection","financial"]),
    ("Payer-call voice agents", ["voice","phone","payer call"]),
  ],
  "8. Ongoing Care": [
    ("Remote patient monitoring", ["remote patient monitoring","rpm","monitoring","wearable","vitals"]),
    ("Virtual nursing & sitting", ["virtual nursing","virtual sitting","fall","telesitter","observation"]),
    ("Chronic & care management", ["chronic","care management","care coordination","care navigation","transition","readmission"]),
    ("Hospital-at-home", ["hospital at home","hospital-at-home","home health","home care","hospice","oasis"]),
    ("Patient engagement & companion", ["engagement","companion","education","check-in","outreach"]),
  ],
  "Ops & Infrastructure": [
    ("AI governance & monitoring", ["governance","monitoring","validation","model","compliance","registry"]),
    ("Data & interoperability", ["data","interoperab","fhir","hl7","integration","de-identif","record retrieval"]),
    ("Workforce & scheduling", ["scheduling","staffing","credential","nurse","workforce","recruit"]),
    ("Capacity & patient flow", ["capacity","patient flow","throughput","bed","operating room","or "]),
    ("Pharmacy & supply chain", ["pharmacy","340b","supply","medication","diversion","inventory"]),
    ("Value-based & population health", ["value-based","population health","quality","risk","registry"]),
    ("Research & trials", ["trial","research","registry","real-world"]),
  ],
}


def substep_for(stage, use_cases):
    rules = SUBSTEPS.get(stage)
    if not rules:
        return None
    toks = " ; ".join(u.lower() for u in use_cases)
    for name, kws in rules:
        for kw in kws:
            if kw in toks:
                return name
    return "Other"

# ---- Patient journey: category -> stage (patient's lived experience) ----
PATIENT_STAGE = {
    "Patient Access & Contact Center": "1. Find & Book Care",
    "Care Management & Virtual Care": "5. Live With Condition",
    "Post-Acute & Home Care": "5. Live With Condition",
    "Imaging & Radiology": "2. Get Diagnosed",
    "Pathology & Diagnostics": "2. Get Diagnosed",
    "Clinical Decision Support": "2. Get Diagnosed",
    "Patient Monitoring & Early Warning": "5. Live With Condition",
    "Surgical & Procedural AI": "3. Get Treated",
    "Ambient Documentation": "3. Get Treated",
    "Revenue Cycle & Prior Auth": "4. Understand the Bill",
    "Coding, CDI & Chart Review": "4. Understand the Bill",
    "Pharmacy & Supply Chain": "3. Get Treated",
    "Dental AI": "2. Get Diagnosed",
    # behind-the-scenes stages don't map to a patient-visible step
}
PATIENT_ORDER = ["1. Find & Book Care","2. Get Diagnosed","3. Get Treated",
    "4. Understand the Bill","5. Live With Condition"]

# ---- Payer pathway: only companies touching payer workflows; stage by use-case/category ----
PAYER_ORDER = ["1. Enrollment & Eligibility","2. Prior Authorization",
    "3. Utilization & Claims","4. Risk & Quality","5. Payment Integrity"]

PROVIDER_BUYERS = {"Health systems","Physician groups","Specialty practices",
    "Post-acute & home care","Imaging centers & radiology groups","FQHCs & community health",
    "Behavioral health","Oncology practices","Dental practices","Pharmacies"}
PHARMA_HINT = ("pharma","life science","life-science","clinical trial","real-world evidence",
    "rwe","biopharma","drug development")


# ---- map attribution.json SHORT stage names -> this view's stage labels ----
ATTR_PROVIDER_TO_STAGE = {
    "Access & Intake":"1. Access & Intake","Diagnose":"2. Diagnose",
    "Clinical Decision":"3. Clinical Decision","Treat":"4. Treat",
    "Document":"5. Document","Code":"6. Code","Bill & Collect":"7. Bill & Collect",
    "Ongoing Care":"8. Ongoing Care","Operations":"Ops & Infrastructure",
    "Infrastructure":"Ops & Infrastructure",
}
ATTR_PATIENT_TO_STAGE = {
    "Find & Book Care":"1. Find & Book Care","Get Diagnosed":"2. Get Diagnosed",
    "Get Treated":"3. Get Treated","Understand the Bill":"4. Understand the Bill",
    "Live With Condition":"5. Live With Condition",
}
ATTR_PAYER_TO_STAGE = {
    "Enrollment & Eligibility":"1. Enrollment & Eligibility",
    "Prior Authorization":"2. Prior Authorization",
    "Utilization & Claims":"3. Utilization & Claims",
    "Risk & Quality":"4. Risk & Quality","Payment Integrity":"5. Payment Integrity",
}


def payer_stage(text):
    t = text.lower()
    if "eligibility" in t or "enrollment" in t or "benefit" in t:
        return "1. Enrollment & Eligibility"
    if "prior auth" in t or "authorization" in t or "preauth" in t:
        return "2. Prior Authorization"
    if "denial" in t or "claim" in t or "utilization" in t or "appeal" in t:
        return "3. Utilization & Claims"
    if "risk adjustment" in t or "hcc" in t or "quality" in t or "stars" in t or "hedis" in t:
        return "4. Risk & Quality"
    if "payment integrity" in t or "underpayment" in t or "payment" in t:
        return "5. Payment Integrity"
    return None


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    attribution = {}
    if os.path.exists(ATTRIBUTION):
        attribution = json.load(open(ATTRIBUTION, encoding="utf-8"))
    else:
        print(f"  [warn] {ATTRIBUTION} not found — run classify_attribution.py first. Falling back to keyword mapping.")
    companies = []
    for r in rows:
        buyers = set(lst(r.get("Buyers", "")))
        text = " ".join([r.get("Description",""), r.get("Notes",""), " ".join(lst(r.get("Use cases","")))])
        low = text.lower()
        is_provider = bool(buyers & PROVIDER_BUYERS) or True  # effectively all
        is_pharma = any(h in low for h in PHARMA_HINT)
        payer_hit = ("payer" in low or "health plan" in low or "insurer" in low
                     or "prior auth" in low or "denial" in low or "risk adjustment" in low
                     or "eligibility" in low)
        c = {
            "name": r["Company"].strip(),
            "category": r["Category"].strip(),
            "segment": r["Segment"].strip(),
            "stage_name": r["Stage"].strip(),
            "hq": r.get("HQ","").strip(), "country": r.get("Country","").strip(),
            "raised": num(r.get("Total raised ($M)")),
            "latestRound": num(r.get("Latest round ($M)")),
            "raised2026": r.get("Raised in 2026","").strip().lower()=="yes",
            "useCases": lst(r.get("Use cases","")),
            "description": r.get("Description","").strip(),
            "buyers": sorted(buyers),
            "providerStage": PROVIDER_STAGE.get(r["Category"].strip(), "Ops & Infrastructure"),
            "patientStage": PATIENT_STAGE.get(r["Category"].strip()),
            "payerStage": payer_stage(text) if payer_hit else None,
            "subStep": None,  # filled below
            "isPharma": is_pharma,
            "isPayer": payer_hit,
        }
        c["subStep"] = substep_for(c["providerStage"], c["useCases"])
        c["subgroup"] = subgroup_for(c["category"], c["useCases"])  # shared taxonomy with market map
        # dollars raised in 2026 (latest round if flagged this year) for the momentum view
        c["round2026"] = c["latestRound"] if c["raised2026"] else 0.0

        # ---- apply attribution (primary stage, patient-facing, payer) ----
        # attribution.json uses SHORT stage names ("Diagnose"); the pathways view
        # uses NUMBERED stage names ("2. Diagnose"). Map short -> numbered here.
        a = attribution.get(c["name"])
        if a:
            ps = a.get("primaryStage")
            c["providerStage"] = ATTR_PROVIDER_TO_STAGE.get(ps, c["providerStage"])
            if a.get("patientFacing"):
                pat = a.get("patientStage")
                c["patientStage"] = ATTR_PATIENT_TO_STAGE.get(pat, c["patientStage"])
            else:
                c["patientStage"] = None
            pay = a.get("payerStage")
            c["payerStage"] = ATTR_PAYER_TO_STAGE.get(pay, c["payerStage"]) if pay else c["payerStage"]
            c["patientFacing"] = a.get("patientFacing", False)
            c["isPayer"] = a.get("payerParticipant", c["isPayer"])
            c["attrConfidence"] = a.get("confidence")
            c["attrSource"] = a.get("source")
        else:
            c["patientFacing"] = c["patientStage"] is not None
            c["attrConfidence"] = None
            c["attrSource"] = None
        # recompute sub-step against the (possibly attribution-updated) provider stage
        c["subStep"] = substep_for(c["providerStage"], c["useCases"])
        companies.append(c)

    # sub-step aggregates per provider stage
    # Each bucket carries BOTH lifetime `raised` and 2026 `raised26` dollars, plus r26 count.
    substeps = {}
    for stage in PROVIDER_ORDER:
        order = [name for name, _ in SUBSTEPS.get(stage, [])] + ["Other"]
        buckets = {s: {"subStep": s, "companies": 0, "raised": 0.0, "raised26": 0.0, "r26": 0} for s in order}
        for c in companies:
            if c["providerStage"] != stage:
                continue
            s = c["subStep"] or "Other"
            if s not in buckets:
                buckets[s] = {"subStep": s, "companies": 0, "raised": 0.0, "raised26": 0.0, "r26": 0}
            b = buckets[s]
            b["companies"] += 1
            b["raised"] += c["raised"]
            b["raised26"] += c["round2026"]
            if c["raised2026"]:
                b["r26"] += 1
        # drop empty sub-steps, keep order
        out = []
        for s in order:
            if buckets[s]["companies"] > 0:
                buckets[s]["raised"] = round(buckets[s]["raised"], 1)
                buckets[s]["raised26"] = round(buckets[s]["raised26"], 1)
                out.append(buckets[s])
        substeps[stage] = out

    def agg(stage_key, order):
        # Carries lifetime `raised`, 2026 `raised26`, company count, and 2026 count `r26`.
        buckets = {s: {"stage": s, "companies": 0, "raised": 0.0, "raised26": 0.0, "r26": 0, "names": []} for s in order}
        for c in companies:
            s = c[stage_key]
            if not s or s not in buckets:
                continue
            b = buckets[s]
            b["companies"] += 1
            b["raised"] += c["raised"]
            b["raised26"] += c["round2026"]
            if c["raised2026"]: b["r26"] += 1
        for b in buckets.values():
            b["raised"] = round(b["raised"], 1)
            b["raised26"] = round(b["raised26"], 1)
        return [buckets[s] for s in order]

    provider = agg("providerStage", PROVIDER_ORDER)
    patient = agg("patientStage", PATIENT_ORDER)
    payer = agg("payerStage", PAYER_ORDER)

    # overview: stakeholder reach (overlapping sets). Patient reach uses the
    # attribution patientFacing flag (honest — clinician tools excluded).
    prov_n = len(companies)
    payer_n = sum(1 for c in companies if c["isPayer"])
    pharma_n = sum(1 for c in companies if c["isPharma"])
    patient_n = sum(1 for c in companies if c.get("patientFacing"))
    prov_r = round(sum(c["raised"] for c in companies), 1)
    payer_r = round(sum(c["raised"] for c in companies if c["isPayer"]), 1)
    pharma_r = round(sum(c["raised"] for c in companies if c["isPharma"]), 1)
    patient_r = round(sum(c["raised"] for c in companies if c.get("patientFacing")), 1)

    data = {
        "source": SRC,
        "total": len(companies),
        "overview": {
            "stakeholders": [
                {"name":"Provider","companies":prov_n,"raised":prov_r},
                {"name":"Patient","companies":patient_n,"raised":patient_r},
                {"name":"Payer","companies":payer_n,"raised":payer_r},
                {"name":"Pharma","companies":pharma_n,"raised":pharma_r},
            ]
        },
        "substeps": substeps,
        "pathways": {
            "provider": {"label":"Provider journey","order":PROVIDER_ORDER,"stages":provider},
            "patient":  {"label":"Patient journey (only patient-facing products — clinician tools like OpenEvidence excluded)","order":PATIENT_ORDER,"stages":patient},
            "payer":    {"label":"Payer pathway (partial — 215 touch payer workflows)","order":PAYER_ORDER,"stages":payer},
        },
        "companies": companies,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {OUT}: {len(companies)} companies")
    print("  provider stages:", [(s['stage'], s['companies']) for s in provider])
    print("  patient stages :", [(s['stage'], s['companies']) for s in patient])
    print("  payer stages   :", [(s['stage'], s['companies']) for s in payer])
    print(f"  reach -> provider {prov_n}, payer {payer_n}, pharma {pharma_n}")


if __name__ == "__main__":
    main()
