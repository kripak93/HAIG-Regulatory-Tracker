"""
Per-category "what are they doing" sub-group taxonomy for the healthcare-AI
market map.

For each of the 18 workflow categories, a list of (sub_group_name, [keyword
substrings]). A company is assigned to the FIRST sub-group whose keywords match
any of its lowercased use-case tokens; unmatched companies fall to "Other".
Rules are ordered specific-first. Edit freely — this is the single source of the
category detail layer.
"""

CATEGORY_SUBGROUPS = {
  "Patient Access & Contact Center": [
    ("Symptom check & triage", ["triage","symptom","navigation","digital front door"]),
    ("Voice / front-desk agents", ["voice","receptionist","phone agent","call center","call automation"]),
    ("Scheduling & booking", ["scheduling","appointment","booking","no-show","reminder","confirmation"]),
    ("Patient intake & forms", ["intake","registration","pre-visit","questionnaire"]),
    ("Referral & fax intake", ["referral","fax"]),
    ("Outreach & reactivation", ["outreach","reactivation","care gap","recall"]),
    ("Insurance & interpretation", ["insurance verification","eligibility","interpret","translation","language"]),
  ],
  "Revenue Cycle & Prior Auth": [
    ("Prior authorization", ["prior auth","authorization","preauth","gold card"]),
    ("Eligibility & benefits", ["eligibility","benefits","coverage","insurance verification"]),
    ("Denials & appeals", ["denial","appeal","underpayment","claim status","claims follow"]),
    ("Claims submission & scrubbing", ["claim","scrub","submission","rcm automation"]),
    ("Patient billing & payments", ["patient billing","patient payment","payment posting","payment reconcil","cost estimate","collection","financial"]),
    ("Payer-call voice agents", ["voice","payer call","payer phone","phone"]),
  ],
  "Coding, CDI & Chart Review": [
    ("Autonomous coding", ["autonomous coding","medical coding","coding automation","ed coding","surgical coding","radiology coding","anesthesia","charge capture"]),
    ("CDI", ["cdi","documentation compliance","documentation gaps","clinical documentation"]),
    ("Risk adjustment / HCC", ["risk adjustment","hcc","radv"]),
    ("Pre-bill & audit", ["pre-bill","audit","revenue integrity","denial prevention"]),
    ("Registry & quality abstraction", ["registry","quality reporting","abstraction","chart review","case selection"]),
    ("Utilization management", ["utilization"]),
  ],
  "Imaging & Radiology": [
    ("Breast / mammography", ["mammograph","breast"]),
    ("Chest / lung", ["chest","lung","pulmonary","nodule"]),
    ("Neuro / stroke", ["stroke","brain","neuro","head ct"]),
    ("Cardiac imaging", ["cardiac","echo","ejection","coronary","plaque","aortic","cardiovascular"]),
    ("Image acceleration / enhancement", ["acceleration","reconstruction","enhancement","low-dose","denois","throughput"]),
    ("Radiology reporting & workflow", ["reporting","worklist","foundation model","workflow","report drafting"]),
    ("Incidental findings & follow-up", ["incidental","follow-up"]),
    ("Point-of-care ultrasound", ["ultrasound","echo","pocus"]),
    ("Triage & detection", ["triage","detection","screening","measurement","risk"]),
  ],
  "Ambient Documentation": [
    ("General ambient scribe", ["ambient scribe","ambient documentation","clinical notes","visit notes","note drafting","dictation","speech"]),
    ("Behavioral health scribe", ["therapy notes","behavioral health scribe","mental health"]),
    ("Nursing / specialty docs", ["nursing","specialty notes","discharge","handoff"]),
    ("Coding-aware docs", ["coding","cdi","charge capture","e/m","hcc"]),
    ("Multilingual / letters", ["multilingual","referral letter","letters"]),
  ],
  "Clinical Decision Support": [
    ("Chart summarization", ["chart summar","summariz","discharge summ","chart review"]),
    ("Evidence & reference", ["evidence","guideline","reference","drug information","clinical reasoning","answers","knowledge"]),
    ("Clinical pathways / order support", ["pathway","decision support","order","differential","cds"]),
    ("Medication & dosing", ["medication","dosing","drug mismatch","vancomycin","glycemic","polypharmacy"]),
    ("Behavioral / mental health", ["mental health","behavioral","developmental"]),
    ("Inbox & results triage", ["inbox","lab result","rx renewal","message"]),
    ("Risk & screening", ["risk","screening","detection","care gap"]),
  ],
  "Patient Monitoring & Early Warning": [
    ("Inpatient deterioration / sepsis", ["deterioration","sepsis","early warning","cardiac arrest","surveillance","mortality"]),
    ("Remote patient monitoring", ["remote patient monitoring","remote monitoring","hospital at home","chronic"]),
    ("Virtual nursing / sitting", ["virtual nursing","virtual sitting","fall","alarm","smart hospital"]),
    ("Wearables & vitals", ["wearable","vital","blood pressure","ecg","hemodynamic","cuffless"]),
    ("Neuro / seizure", ["seizure","eeg"]),
    ("Pressure injury / HAC", ["pressure injury","hospital-acquired"]),
  ],
  "Pathology & Diagnostics": [
    ("Digital pathology AI", ["pathology","slide","tissue","cancer grading","biomarker","histolog"]),
    ("Retinal / eye screening", ["retina","retinal","diabetic retinopathy","fundus"]),
    ("Skin / dermatology", ["skin","derm"]),
    ("Cardiac diagnostics (ECG)", ["ecg","cardiac","arrhythmia","ejection","ep procedure"]),
    ("Sepsis / host-response", ["sepsis","host-response","cellular"]),
    ("Oncology / precision", ["oncology","prostate","mutational","precision","therapy selection"]),
  ],
  "Surgical & Procedural AI": [
    ("Surgical navigation", ["navigation","3d imaging","headset","overlay","perfusion"]),
    ("Surgical robotics", ["robot","robotic"]),
    ("OR video & analytics", ["video","black box","safety event","computer vision","or data"]),
    ("Perioperative efficiency", ["perioperative","efficiency","risk & quality"]),
    ("Procedure / implant planning", ["planning","implant","3d printing","digital twin","tavr","preference"]),
  ],
  "Post-Acute & Home Care": [
    ("Home health documentation / OASIS", ["oasis","home health documentation","start-of-care","clinical documentation","charting","ambient scribe","icd-10"]),
    ("Hospice documentation", ["hospice"]),
    ("Referral intake & admissions", ["referral","admission","intake","document extraction"]),
    ("Scheduling & workforce", ["scheduling","caregiver","payroll","onboarding","visit verification","front-desk"]),
    ("Remote monitoring & care planning", ["remote patient monitoring","care planning","care transition","fall detection"]),
    ("Senior living platforms", ["senior living","home care ehr"]),
  ],
  "Care Management & Virtual Care": [
    ("Remote patient monitoring", ["remote patient monitoring","remote monitoring","hospital at home"]),
    ("Chronic & transitional care", ["chronic","transitional","care transition","readmission","post-discharge"]),
    ("Virtual nursing / sitting", ["virtual nursing","virtual sitting","fall","ambient intelligence"]),
    ("Tele-specialty / virtual visits", ["telestroke","telehospitalist","tele-specialty","econsult","virtual care platform","virtual hospital","digital front door"]),
    ("Care navigation & coordination", ["navigation","coordination","care team","care management agent"]),
    ("Patient education & engagement", ["education","companion","community","engagement","outreach"]),
  ],
  "Hospital Operations & Capacity": [
    ("Patient flow & discharge", ["patient flow","discharge","length-of-stay","transfer","capacity","care transition","care orchestration","bed","inpatient psych"]),
    ("OR / perioperative scheduling", ["or computer vision","case duration","perioperative","real-time case","turnover","operating room","case tracking"]),
    ("Post-acute placement", ["post-acute","placement","referral"]),
    ("Capacity & orchestration", ["orchestration","predictive analytics","acuity","command","staffing forecast","rtls","asset track","location"]),
    ("Cost & supply analytics", ["cost","labor","supply","medication spend","operational intelligence","analytics"]),
    ("Case management automation", ["case management","authorization","eligibility","benefits","agentic"]),
    ("Voice / room assistants", ["voice assistant","room control","patient request","senior living"]),
  ],
  "Workforce & Credentialing": [
    ("Credentialing & enrollment", ["credential","payer enrollment","licens","primary source","provider data","provider operations"]),
    ("Nurse / staff scheduling", ["scheduling","shift","roster","staffing","dispatch","coverage gap"]),
    ("Recruiting & onboarding", ["recruit","interview","onboarding","candidate","sourcing"]),
    ("Burnout & workforce analytics", ["burnout","turnover","workforce analytics"]),
  ],
  "Pharmacy & Supply Chain": [
    ("Medication prior auth & access", ["prior auth","medication access","benefits investigation","copay","specialty drug","specialty pharmacy","prescription intake","appeals"]),
    ("340B & purchasing", ["340b","purchasing","diversion"]),
    ("Pharmacy call & workflow automation", ["patient call","call automation","prescription benefit","price transparency","decision support"]),
    ("OR supply & inventory", ["supply","implant","inventory","rfid","procedure card","substitute"]),
  ],
  "AI Infrastructure & Governance": [
    ("AI governance & monitoring", ["governance","model monitoring","monitoring","post-deployment","validation","risk assessment","compliance","vendor evaluation","vendor portfolio","vendor assessment","model management","ai scaling","registry","roi"]),
    ("Security (IoMT / cyber)", ["security","cyber","device risk","patching","microsegmentation","device visibility","threat"]),
    ("Data integration & NLP", ["nlp","data integration","interoperab","hl7","fhir","abstraction","medical llm","de-identif","data structuring","data labeling","search","normaliz","record retrieval"]),
    ("AI deployment platforms", ["deployment","marketplace","orchestration","agent-ready","app builder","ai agents","imaging ai","enablement","workflow","custom app","no-code","care orchestration"]),
  ],
  "Data, Quality & Value-Based Care": [
    ("Population health & analytics", ["population health","predictive analytics","cost & quality","data aggregation","benchmark"]),
    ("Risk adjustment", ["risk adjustment","risk stratification"]),
    ("Care gap & VBC enablement", ["care gap","vbc","value-based","care coordination","care management","care navigation"]),
    ("Registry & quality abstraction", ["registry","abstraction","quality reporting","perioperative analytics"]),
    ("Record retrieval", ["record retrieval","medical record"]),
    ("SDOH & specialty data", ["sdoh","genomics","biobank","women's health","surveillance","oncology navigation"]),
  ],
  "Clinical Research & Trials": [
    ("Trial patient matching", ["matching","prescreen","eligibility","patient finding"]),
    ("Site operations (eTMF/eConsent)", ["ebinder","eisf","econsent","etmf","site feasibility","remote monitoring"]),
    ("Research data & abstraction", ["chart abstraction","registry","data mining","data search","observational","de-identified","analytics"]),
    ("Oncology research", ["oncology","molecular tumor","genomic","precision oncology"]),
  ],
  "Dental AI": [
    ("Dental imaging AI", ["x-ray","cbct","radiology","caries","bone-loss","pathology detection","intraoral"]),
    ("Practice management & RCM", ["pms","practice","claims","payment posting","insurance verification","rcm","treatment acceptance","practice performance"]),
    ("Dental scribe & documentation", ["scribe","clinical documentation","perio charting","clinical q&a"]),
    ("Front office & scheduling", ["receptionist","appointment","patient engagement","virtual consult"]),
    ("Interoperability", ["interoperab","fhir","referral","connectivity"]),
    ("Orthodontic monitoring", ["orthodontic"]),
  ],
}


def subgroup_for(category, use_cases):
    rules = CATEGORY_SUBGROUPS.get(category)
    if not rules:
        return None
    toks = " ; ".join(u.lower() for u in use_cases)
    for name, kws in rules:
        for kw in kws:
            if kw in toks:
                return name
    return "Other"
