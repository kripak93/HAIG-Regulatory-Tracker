# AI Regulatory Tracker — automation pipeline

Tracks state (and federal) AI legislation across seven domains, scores each
state's regulatory stringency, and republishes a map. The pipeline fetches from
the LegiScan public API, never auto-merges, and keeps a human review checkpoint
before anything touches the canonical dataset.

## Pipeline

```
fetch (LegiScan)
  → normalize + dedupe
    → diff vs last snapshot
      → diff_report.txt         ← STOP: human reviews
        → (re-run with --merge)
          → merge into canonical CSV
            → re-score (status_weight × severity)
              → regenerate state CSV + map HTML
```

## Files

| File | Role |
|------|------|
| `schema.py` | Single source of truth: 7 domains, mechanism severities, status pipeline + weights, LegiScan status codes, scoring formula. |
| `normalize.py` | Bill-number normalization, splitting combined rows (`HB2368 / SB1444`), dedupe on `(state, bill)`, and near-duplicate flagging. |
| `score.py` | Resolves a status-independent **severity** per bill (from mechanism tag or backed out of legacy scores), then scores as `status_weight × severity`. Regenerates the canonical + state CSVs. |
| `legiscan_scraper.py` | LegiScan fetch + normalize layer. Offline-testable via `run_search_from_fixture`. |
| `publish.py` | Splices fresh `SCORE_DATA` / `BILL_DATA` into the map HTML template. |
| `run_pipeline.py` | Orchestrator. Report-only by default; `--merge` applies the reviewed diff. |

## Scoring model

```
severity          0–4   "how strict" — from the mechanism tag, or derived once
                        from legacy domain_scores (severity = score / weight)
status_weight     0–1   how far the bill has advanced (Introduced … Enacted)
domain_score  =  severity × status_weight         (per bill, per domain)
state score   =  max(domain_score) across that state's bills
state overall =  max across domains
```

Because severity is cached (the `severity` column), a status change rescores
correctly for **every** bill — including insurance / utilization-review bills
that carry no text mechanism tag.

## Usage

```bash
pip install -r requirements.txt
set LEGISCAN_API_KEY=your_key_here        # Windows cmd
# $env:LEGISCAN_API_KEY="your_key_here"   # PowerShell

# 1. Scan + write diff_report.txt (no changes applied)
python run_pipeline.py

# 2. Review diff_report.txt by hand. New bills land UNSCORED under
#    "NEEDS CLASSIFICATION" — assign each a mechanism in the canonical CSV
#    before it counts toward any state's stringency.

# 3. Apply the reviewed diff, re-score, regenerate CSV + map
python run_pipeline.py --merge
```

### Offline / no API key

```bash
python run_pipeline.py --fixture fixture.json          # report only
python run_pipeline.py --fixture fixture.json --merge   # apply
```

A fixture is a JSON list of raw LegiScan-style hits, each with a `_domain` key.

## Scheduling

`.github/workflows/monthly-scan.yml` runs the report-only scan on the 1st of
each month and uploads `diff_report.txt` as an artifact. Set the
`LEGISCAN_API_KEY` repository secret. Merging stays manual by design.

## Design notes

- **No auto-merge.** A bad search result or API hiccup can't silently corrupt
  the dataset.
- **New bills are unscored.** Mechanism classification is interpretive; the
  pipeline flags new bills for a human (or an LLM step) rather than guessing.
- **Near-duplicates are flagged, not merged.** Prefix-alias collisions
  (RI `S2197` vs `SB2197`) and identical descriptions surface in the report for
  manual judgment, since `S`/`SB` are not always the same bill.

## Status & pending work

**Working and verified (against fixtures):**
- Full loop: fetch → normalize → dedupe → diff → report → merge → re-score → regenerate CSV + map.
- Dedupe (collapses `SB 903`/`SB903`, splits `HB2368 / SB1444`, flags near-dupes).
- Status-independent severity caching, so status changes rescore correctly across all 7 domains.
- Map republishing wired into merge.
- Corrected LegiScan status codes.

**Pending:**
1. **Live LegiScan smoke test (blocker for production).** All testing is fixture-based.
   The live `getSearch` response shape is unverified — in particular `normalize_hit`
   assumes a numeric `status` field and field names `bill_number` / `title` / `url`.
   Needs one run with a real `LEGISCAN_API_KEY` to confirm and likely a small tweak.
2. **`effective` date not pulled from LegiScan** (getSearch omits it; needs a `getBill` call).
3. **New-bill classification is manual.** New bills land unscored under
   "NEEDS CLASSIFICATION"; assigning a mechanism is a hand edit. Optional LLM
   classification step not built.
4. **No automated test suite** — verification has been manual runs.
5. **Scheduled workflow unproven** — `.github/workflows/monthly-scan.yml` needs the
   `LEGISCAN_API_KEY` repo secret and a first run in Actions.

## Interim data source: CSV import (no API key required)

While LegiScan API access is pending approval, the pipeline can be refreshed
without any credentials using the CSV-import adapter. A human gathers bill
**facts** (bill number, state, status, effective date) from primary/public
sources — the state legislature's own bill page, NCSL, or a tracker that
publishes an `llms.txt` for machine reading — and drops them into an import CSV
cited to the **primary source**, not an aggregator.

```bash
# 1. Review what the import would change (no writes)
python run_pipeline.py --source csv --file import_livecompliance.csv

# 2. Read diff_report.txt, then apply + rescore + regenerate the map
python run_pipeline.py --source csv --file import_livecompliance.csv --merge
```

Import CSV columns: `state, bill, status, effective, domains, mechs, desc, source`.
The adapter (`sources_csv_import.py`) normalizes these into the same record
shape the LegiScan path produces, so dedupe / diff / score / publish are
unchanged. The merge reconciles against the canonical dataset: a bill already
present gets a status advance; a genuinely new bill is added.

`import_livecompliance.csv` is a worked example: 44 in-scope state AI-healthcare
laws (2024–2027), each cited to its primary statute/bill page. Merging it added
20 new 2026 laws and advanced 7 existing ones.
