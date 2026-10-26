# AI Regulatory Tracker — integration summary for the web team

## What this is
A pipeline that tracks state + federal AI legislation across 7 domains, dedupes
and scores each state's regulatory stringency (0–4), and outputs a clean data
file. We want your website to render that data in your own UI.

## Proposed architecture (decoupled)

```
GitHub Actions (scheduled or manual trigger)   ← the automation runs here
   → run_pipeline.py  (fetch LegiScan → normalize → dedupe → diff → score)
   → produces a single data artifact: bills.json
   → publishes it to a location your site can read
        │
        ▼
   your website fetches bills.json and renders it (your stack, your UI)
```

Key point: **the website runs no Python.** It just consumes a JSON file the
pipeline keeps fresh. The data layer and the frontend are fully decoupled — you
can change the UI anytime without touching the pipeline.

## The one decision we need from you
How should your site receive `bills.json`? Options:

1. **Raw from the repo** — Actions commits `bills.json`; site fetches it from a
   GitHub raw URL / GitHub Pages. Zero infra, but a runtime dependency on GitHub.
2. **Pushed to storage you own** — Actions pushes `bills.json` to your bucket /
   CDN (S3, GCS, etc.); site fetches from your own domain. *(Our recommendation.)*
3. **Small data API** — Actions writes to a store, an endpoint serves it. More
   than needed for now.

## What we'd deliver
- `bills.json`: deduped, scored dataset — list of bills + per-state aggregates,
  with `generated_at` timestamp and a schema version. (Schema doc to follow.)
- A GitHub Actions workflow that regenerates and publishes it on trigger.

## Questions for you
1. Preferred delivery method above (1/2/3)? If 2, what's the target (bucket/CDN)
   and who owns the credentials?
2. Any preferred JSON shape, or is "bills + state aggregates in one file" fine?
3. Public-facing view, internal staff view, or both? (Affects nothing in the
   pipeline — just helps us document the contract.)
