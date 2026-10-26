"""
LegiScan fetch layer for the AI Regulatory Tracker.

Responsibilities (fetch + normalize only -- diffing/merging live in
run_pipeline.py):
  - Query LegiScan's getSearch across all 50 states for each tracked domain.
  - Normalize each hit into the canonical bill record shape (shared with the
    CSV via normalize.py / schema.py).
  - Map LegiScan numeric status codes onto the canonical status pipeline.

Setup:
  1. Free API key: https://legiscan.com/legiscan  (Account -> API Key)
  2. pip install requests
  3. set LEGISCAN_API_KEY=your_key_here   (Windows: setx, or $env: in PowerShell)

Offline / testing:
  If LEGISCAN_API_KEY is unset, run_search() raises. Use
  run_search_from_fixture(path) to drive the rest of the pipeline from a saved
  JSON fixture instead, so dedupe/diff/score can be tested without network.
"""

from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime, timezone

import schema
import normalize

try:
    import requests
except ImportError:
    requests = None

API_KEY = os.environ.get("LEGISCAN_API_KEY")
BASE_URL = "https://api.legiscan.com/"

# Each query maps to one canonical domain. getSearch is full-text over
# title + description. Tune freely -- this is the scope control.
SEARCH_QUERIES = {
    "Behavioral & Mental Health AI": [
        "artificial intelligence therapy",
        "artificial intelligence psychotherapy chatbot",
        "AI mental health counseling",
    ],
    "Utilization Review & Prior Auth": [
        "artificial intelligence utilization review",
        "AI prior authorization insurance denial",
        "algorithm adverse determination health insurance",
    ],
    "Clinical Decision Making": [
        "artificial intelligence clinical decision diagnosis",
        "AI downcoding medical claims",
    ],
    "Provider Disclosure": [
        "artificial intelligence disclosure health care provider",
    ],
    "Reimbursement & Coverage": [
        "artificial intelligence remote patient monitoring reimbursement",
    ],
    "Telehealth Operations & Consumer Protection": [
        "artificial intelligence telehealth prescribing",
    ],
    "Clinical AI Oversight (Professional Bodies)": [
        "artificial intelligence medical board physician supervision",
    ],
}


def api_call(op, **params):
    if requests is None:
        sys.exit("pip install requests first.")
    if not API_KEY:
        sys.exit("Set LEGISCAN_API_KEY first -- see the setup note at the top of this file.")
    params.update({"key": API_KEY, "op": op})
    r = requests.get(BASE_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK":
        print(f"  [warn] LegiScan non-OK for op={op}: {data.get('alert', data)}", file=sys.stderr)
    return data


def search_bills(query, state="ALL"):
    """getSearch across all states; returns a list of raw result dicts."""
    data = api_call("getSearch", state=state, query=query)
    results = data.get("searchresult", {})
    return [v for k, v in results.items() if k != "summary"]


def _legiscan_status(raw) -> str:
    """LegiScan may return a numeric status id or a text last_action."""
    try:
        return schema.LEGISCAN_STATUS.get(int(raw), "Unknown")
    except (TypeError, ValueError):
        return schema.normalize_status(raw)


def normalize_hit(raw: dict, domain: str) -> dict:
    """Map one LegiScan search hit into a canonical bill record."""
    state = str(raw.get("state", "")).strip().upper()
    bill = normalize.normalize_bill_number(raw.get("bill_number", ""))
    return {
        "state": state,
        "bill": bill,
        "status": _legiscan_status(raw.get("status")),
        "status_raw": str(raw.get("last_action", "")).strip(),
        "effective": "",  # getSearch omits it; getBill would be needed
        "domains": [domain] if domain in schema.DOMAINS else [],
        "mechs": [],       # intentionally empty: classification is a human/LLM step
        "desc": str(raw.get("title", "")).strip(),
        "source": raw.get("url") or raw.get("text_url") or "",
        "flag": False,
        "domain_scores": {},     # unscored until a mechanism is assigned
        "legiscan_id": raw.get("bill_id"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def run_search() -> dict:
    """Live search across every tracked domain. Returns {(state,bill): record}."""
    print("Searching LegiScan across all tracked domains...")
    found: dict[tuple, dict] = {}
    for domain, queries in SEARCH_QUERIES.items():
        for q in queries:
            print(f"  [{domain}] query: {q!r}")
            try:
                hits = search_bills(q)
            except Exception as e:  # noqa: BLE001 - network/parse errors shouldn't abort the run
                print(f"    [error] {e}", file=sys.stderr)
                continue
            for raw in hits:
                rec = normalize_hit(raw, domain)
                if not rec["state"] or not rec["bill"]:
                    continue
                key = (rec["state"], rec["bill"])
                if key in found:
                    for d in rec["domains"]:
                        if d not in found[key]["domains"]:
                            found[key]["domains"].append(d)
                else:
                    found[key] = rec
            time.sleep(1)  # polite: free tier is rate-limited
    print(f"Total distinct bills found: {len(found)}")
    return found


def run_search_from_fixture(path: str) -> dict:
    """
    Offline driver: load a saved list of raw LegiScan hits (each annotated with
    a '_domain' key) and run them through the same normalizer. Lets the rest of
    the pipeline be exercised with no network / no API key.
    """
    with open(path, encoding="utf-8") as f:
        raw_hits = json.load(f)
    found: dict[tuple, dict] = {}
    for raw in raw_hits:
        rec = normalize_hit(raw, raw.get("_domain", ""))
        if not rec["state"] or not rec["bill"]:
            continue
        found[(rec["state"], rec["bill"])] = rec
    print(f"[fixture] loaded {len(found)} bills from {path}")
    return found
