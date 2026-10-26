"""
Single source of truth for the AI Regulatory Tracker.

Everything downstream (normalize, score, scraper) imports from here so the
taxonomy, status pipeline, and scoring formula are defined in exactly one place.

Scoring model (unchanged from the existing dataset):
    domain_score = status_weight * mechanism_severity   (per domain, per bill)
    state domain score = max(domain_score) across that state's bills
    state overall       = max across domains
A 0-4 stringency score falls out of this because the max mechanism severity is
4.0 and the max status weight is 1.0.
"""

from __future__ import annotations

# --- The seven tracked domains -------------------------------------------------
DOMAINS = [
    "Behavioral & Mental Health AI",
    "Utilization Review & Prior Auth",
    "Clinical Decision Making",
    "Provider Disclosure",
    "Reimbursement & Coverage",
    "Telehealth Operations & Consumer Protection",
    "Clinical AI Oversight (Professional Bodies)",
]

# --- Regulatory mechanism axis -------------------------------------------------
# Severity is the "how strict" weight (1-4 scale) applied before status weighting.
# Ordered loosely from most to least restrictive.
MECHANISM_SEVERITY = {
    "Outright Ban": 4.0,
    "Representation Restriction": 3.0,
    "Minor Safeguard": 3.0,
    "Privacy Safeguard": 2.0,
    "Disclosure Requirement": 2.0,
    "Advertising Restriction": 2.0,
    "Informed Consent": 1.0,
    "Study / Non-Binding": 0.5,
    "Unrelated (flagged)": 0.0,
}

# Domains that use the insurance/clinical-oversight angle often carry no explicit
# mechanism tag in the source data; they are scored directly via domain_scores.
# A bill with no mechanism tag keeps its pre-computed domain_scores as-is.

# --- Status pipeline -----------------------------------------------------------
# Canonical ordered pipeline. Dead/Failed/Vetoed are terminal and score ~0.
STATUS_PIPELINE = [
    "Introduced",
    "In Committee",
    "Passed One Chamber",
    "Passed Both Chambers",
    "Enacted",
    "Effective",
]
TERMINAL_STATUSES = ["Dead", "Failed", "Vetoed"]

# Status weight: how much "live" progress discounts the severity.
STATUS_WEIGHT = {
    "Introduced": 0.3,
    "In Committee": 0.4,
    "Passed One Chamber": 0.6,
    "Passed Both Chambers": 0.7,
    "House Passed": 0.6,
    "Senate Passed": 0.6,
    "Enacted": 1.0,
    "Effective": 1.0,
    "Vetoed": 0.05,
    "Dead": 0.05,
    "Failed": 0.05,
    "Unknown": 0.2,
    "Proposed Rule": 0.35,
    "Enforcement Action": 0.75,
    "Non-Binding Guidance": 0.15,
}

# Map free-text / inconsistent source statuses onto the canonical set.
# Values on the right MUST be keys in STATUS_WEIGHT.
STATUS_NORMALIZE = {
    "introduced": "Introduced",
    "in committee": "In Committee",
    "passed one chamber": "Passed One Chamber",
    "house passed": "House Passed",
    "senate passed": "Senate Passed",
    "passed both chambers": "Passed Both Chambers",
    "enacted": "Enacted",
    "effective": "Effective",
    "vetoed": "Vetoed",
    "dead": "Dead",
    "failed": "Failed",
    "unknown": "Unknown",
    "proposed rule": "Proposed Rule",
    "enforcement action": "Enforcement Action",
    "non-binding guidance": "Non-Binding Guidance",
    # Aliases for external compliance-tracker vocabulary (status mapped to pipeline)
    "in effect": "Enacted",
    "in effect (pilot)": "Enacted",
    "in effect (existing law)": "Enacted",
    "effective soon": "Passed Both Chambers",
    "applies": "Passed Both Chambers",
    "proposed": "Proposed Rule",
    "draft": "Proposed Rule",
    "final guidance": "Non-Binding Guidance",
    "guidance": "Non-Binding Guidance",
    "guidance adopted": "Non-Binding Guidance",
    "enforcement": "Enforcement Action",
    "rescinded": "Dead",
    "withdrawn": "Dead",
    "repealed": "Dead",
    "failed 99-1": "Failed",
}

# LegiScan numeric status codes -> canonical status.
# Verified against LegiScan's documented BILL_STATUS enum:
#   1 Introduced, 2 Engrossed, 3 Enrolled, 4 Passed, 5 Vetoed, 6 Failed/Dead
LEGISCAN_STATUS = {
    1: "Introduced",
    2: "Passed One Chamber",   # Engrossed = cleared chamber of origin
    3: "Passed Both Chambers", # Enrolled = passed both, awaiting signature
    4: "Enacted",              # Passed = signed into law
    5: "Vetoed",
    6: "Dead",                 # Failed/Dead
}

# Columns in the canonical CSV (bills_detailed_dataset.csv), in order.
# `severity` holds the stable per-domain 0-4 "how strict" value so status
# changes rescore correctly for every bill, tagged or not. `domain_scores`
# remains the derived output (status_weight x severity).
CSV_COLUMNS = [
    "state",
    "bill",
    "status",
    "effective",
    "domains",
    "mechs",
    "desc",
    "source",
    "flag",
    "status_weight",
    "severity",
    "domain_scores",
]

# Stringency buckets for the 0-4 overall score (used by the map legend).
STRINGENCY_BANDS = [
    (0.0, "None"),
    (0.01, "Non-binding / early"),
    (1.5, "Disclosure / advertising"),
    (2.5, "Restricted"),
    (3.5, "Prohibited"),
]


def normalize_status(raw: str) -> str:
    """Map any source status string onto the canonical pipeline."""
    if raw is None:
        return "Unknown"
    key = str(raw).strip().lower()
    # strip parenthetical year notes like "Enacted (2026)" or "Enacted (Ch. 747, 2025)"
    if "(" in key:
        key = key.split("(")[0].strip()
    return STATUS_NORMALIZE.get(key, "Unknown")


def status_weight(status: str) -> float:
    return STATUS_WEIGHT.get(status, STATUS_WEIGHT["Unknown"])


def mechanism_severity(mech: str) -> float:
    return MECHANISM_SEVERITY.get(mech.strip(), 0.0)


def stringency_band(score: float) -> str:
    label = "None"
    for threshold, name in STRINGENCY_BANDS:
        if score >= threshold:
            label = name
    return label
