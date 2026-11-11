"""
Attribution classifier for the healthcare-AI funding map.

Goal: attribute each company's FUNDING to a single PRIMARY stakeholder + stage
(so capital-per-stage sums without double counting), plus flag SECONDARY
participation (tracked, never summed). Also decides patient-facing yes/no so the
patient journey only shows products patients actually experience.

Pipeline:
  1. rule-based first pass over all 948 companies -> primary stakeholder+stage,
     patient-facing flag, confidence (0-1).
  2. manual overrides (attribution_overrides.csv) take precedence — this is where
     human/LLM judgment corrects the high-dollar and low-confidence cases.

Outputs attribution.json (per-company) + prints a REVIEW LIST = low-confidence
OR high-funding companies, i.e. the ones that must be right for the money map.
"""

from __future__ import annotations
import csv, json, os, collections

SRC = "provider_table.txt"
OUT = "attribution.json"
OVERRIDES = "attribution_overrides.csv"

def num(x):
    try: return float(str(x).strip())
    except Exception: return 0.0
def lst(s): return [p.strip() for p in str(s or "").split(";") if p.strip()]

# Provider stages (the backbone — nearly every company has a provider role)
PROVIDER_STAGE = {
    "Patient Access & Contact Center":"Access & Intake","Imaging & Radiology":"Diagnose",
    "Pathology & Diagnostics":"Diagnose","Clinical Decision Support":"Clinical Decision",
    "Patient Monitoring & Early Warning":"Clinical Decision","Surgical & Procedural AI":"Treat",
    "Ambient Documentation":"Document","Coding, CDI & Chart Review":"Code",
    "Revenue Cycle & Prior Auth":"Bill & Collect","Care Management & Virtual Care":"Ongoing Care",
    "Post-Acute & Home Care":"Ongoing Care","Hospital Operations & Capacity":"Operations",
    "Workforce & Credentialing":"Operations","Pharmacy & Supply Chain":"Operations",
    "AI Infrastructure & Governance":"Infrastructure","Data, Quality & Value-Based Care":"Infrastructure",
    "Clinical Research & Trials":"Infrastructure","Dental AI":"Diagnose",
}

# Which categories can be genuinely PATIENT-FACING (patient directly interacts)?
# Default: NOT patient-facing. A clinician evidence tool (OpenEvidence) is NOT.
PATIENT_FACING_CATS = {
    "Patient Access & Contact Center",   # scheduling, symptom checkers, patient comms
    "Care Management & Virtual Care",     # virtual visits, companions, RPM apps
}
# phrases that signal a genuinely patient-directed product even outside those cats
PATIENT_SIGNALS = ("patient-facing","symptom checker","companion","patient app","patient portal",
    "chatbot","direct-to-consumer","patient engagement","self-service","patient education",
    "advance care planning","remote patient monitoring")
# phrases that signal clinician-only / back-office (NOT patient)
CLINICIAN_ONLY = ("clinician","radiologist","physician decision","provider decision","back-office",
    "coding","cdi","prior auth","denial","utilization review","credentialing","governance",
    "evidence","decision support","pathology","registry")

PAYER_SIGNALS = ("payer","health plan","insurer","prior auth","denial","risk adjustment",
    "eligibility","utilization review","claims","hcc","payment integrity")

def payer_stage(low):
    if "eligibility" in low or "enrollment" in low or "benefit" in low: return "Enrollment & Eligibility"
    if "prior auth" in low or "authorization" in low: return "Prior Authorization"
    if "denial" in low or "claim" in low or "utilization" in low or "appeal" in low: return "Utilization & Claims"
    if "risk adjustment" in low or "hcc" in low or "quality" in low or "stars" in low or "hedis" in low: return "Risk & Quality"
    if "payment integrity" in low or "underpayment" in low: return "Payment Integrity"
    return None


def patient_stage(cat, low, is_patient):
    if not is_patient: return None
    if cat=="Patient Access & Contact Center": return "Find & Book Care"
    if cat=="Care Management & Virtual Care": return "Live With Condition"
    if "monitoring" in low or "chronic" in low: return "Live With Condition"
    if "symptom" in low or "triage" in low or "navigation" in low: return "Find & Book Care"
    if "education" in low or "companion" in low: return "Live With Condition"
    return "Find & Book Care"


def classify(r):
    cat = r["Category"].strip()
    buyers = set(lst(r.get("Buyers","")))
    text = " ".join([r.get("Description",""), r.get("Notes",""), " ".join(lst(r.get("Use cases","")))])
    low = text.lower()

    # patient-facing judgment
    is_patient = cat in PATIENT_FACING_CATS or any(s in low for s in PATIENT_SIGNALS)
    # strong clinician-only override pulls it back out (unless clearly a patient app)
    if is_patient and cat not in PATIENT_FACING_CATS:
        if any(s in low for s in CLINICIAN_ONLY) and not any(s in low for s in
               ("symptom checker","companion","patient app","patient portal","direct-to-consumer")):
            is_patient = False

    is_payer = any(s in low for s in PAYER_SIGNALS)

    # PRIMARY attribution: nearly all companies' funding is a PROVIDER-side bet.
    # Primary stakeholder = Provider unless the product is overwhelmingly payer-native
    # (a judgment best left to overrides); default primary = provider.
    primary_stakeholder = "Provider"
    primary_stage = PROVIDER_STAGE.get(cat, "Infrastructure")

    # confidence: lower it where the call is genuinely ambiguous
    conf = 0.9
    if cat in ("AI Infrastructure & Governance","Data, Quality & Value-Based Care"):
        conf = 0.7  # these straddle provider/payer/pharma
    if is_payer and cat in ("Revenue Cycle & Prior Auth","Coding, CDI & Chart Review"):
        conf = 0.65  # could be primarily payer-attributed
    if is_patient and cat not in PATIENT_FACING_CATS:
        conf = min(conf, 0.6)  # patient call is a stretch

    return {
        "primaryStakeholder": primary_stakeholder,
        "primaryStage": primary_stage,
        "patientFacing": is_patient,
        "patientStage": patient_stage(cat, low, is_patient),
        "payerParticipant": is_payer,
        "payerStage": payer_stage(low) if is_payer else None,
        "confidence": conf,
        "source": "rule",
    }


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    overrides = {}
    if os.path.exists(OVERRIDES):
        for o in csv.DictReader(open(OVERRIDES, encoding="utf-8")):
            overrides[o["company"].strip()] = o

    out = {}
    for r in rows:
        name = r["Company"].strip()
        a = classify(r)
        a["raised"] = num(r.get("Total raised ($M)"))
        a["raised2026Flag"] = r.get("Raised in 2026","").strip().lower()=="yes"
        a["latestRound"] = num(r.get("Latest round ($M)"))
        a["category"] = r["Category"].strip()
        o = overrides.get(name)
        if o:
            for k_json, k_csv in [("primaryStakeholder","primary_stakeholder"),
                                  ("primaryStage","primary_stage"),
                                  ("patientStage","patient_stage"),
                                  ("payerStage","payer_stage")]:
                if o.get(k_csv,"").strip():
                    a[k_json] = o[k_csv].strip()
            if o.get("patient_facing","").strip():
                a["patientFacing"] = o["patient_facing"].strip().lower() in ("yes","true","1")
            a["confidence"] = 1.0
            a["source"] = "reviewed"
        out[name] = a

    json.dump(out, open(OUT,"w",encoding="utf-8"), indent=2)
    print(f"Wrote {OUT}: {len(out)} companies ({sum(1 for a in out.values() if a['source']=='reviewed')} reviewed)")

    # REVIEW LIST: anything low-confidence OR high-funding (drives the totals)
    review = [(n,a) for n,a in out.items()
              if a["source"]!="reviewed" and (a["confidence"]<0.75 or a["raised"]>=100)]
    review.sort(key=lambda x:-x[1]["raised"])
    print(f"\n=== REVIEW LIST: {len(review)} companies (low-confidence or >= $100M raised) ===")
    print(f"{'company':<26}{'$raised':>9}  {'conf':>5}  primary -> stage   patient?")
    for n,a in review[:45]:
        print(f"{n[:25]:<26}{round(a['raised']):>9}  {a['confidence']:>5.2f}  {a['primaryStakeholder']}/{a['primaryStage'][:14]:<14} pf={a['patientFacing']}")


if __name__ == "__main__":
    main()
