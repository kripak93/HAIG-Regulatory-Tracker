"""
Enrichment step for Source1 (ailawsbystate).

The tracker's table rows carry only a generic one-liner ("Regulates AI in
healthcare"). Each bill's /law/ detail page, however, has a real title, a
plain-English "In one paragraph" summary, and the OFFICIAL legislature bill-text
URL. This script visits each bill's detail page and harvests those into
enrichment_ailawsbystate.csv, which build_archive.py merges over the generic text.

Responsible fetching:
  - Every page is cached to cache/ailawsbystate/<STATE>_<BILL>.html; cached
    pages are reused and never re-fetched.
  - Live fetches are throttled (THROTTLE seconds apart).
  - The OFFICIAL bill-text URL is recorded as the primary source. The harvested
    summary is the aggregator's AI-assisted text; the caveat is preserved in a
    column and surfaced in the UI.

Usage:
    python enrich_ailawsbystate.py                 # fetch (cached) + write CSV
    python enrich_ailawsbystate.py --refresh        # ignore cache, re-fetch all
"""

from __future__ import annotations

import os
import re
import sys
import csv
import time
from html import unescape

import requests

from sources import source1_ailawsbystate as src1

BASE = "https://www.ailawsbystate.com"
CACHE_DIR = os.path.join("cache", "ailawsbystate")
OUT_CSV = "enrichment_ailawsbystate.csv"
SOURCE_HTML = "10-31_Source1.html"
THROTTLE = 1.5  # seconds between live fetches
HEADERS = {"User-Agent": "AIRegTracker/1.0 (research; contact via repo)"}

_TAG_RE = re.compile(r"<[^>]+>")
_LEAD_RE = re.compile(r'<p class="cz-article__lead">(.*?)</p>', re.S)
_TITLE_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
_CODE_RE = re.compile(r'<span class="cz-law-title__code">.*?</span>', re.S)
_OFFICIAL_RE = re.compile(r'href="([^"]+)"[^>]*>\s*Official bill text', re.S)


def _clean(html_fragment: str) -> str:
    txt = _TAG_RE.sub("", html_fragment)
    return unescape(re.sub(r"\s+", " ", txt)).strip()


def _title(html: str) -> str:
    m = _TITLE_RE.search(html)
    if not m:
        return ""
    inner = _CODE_RE.sub("", m.group(1))  # drop the "CA SB1120:" code span
    return _clean(inner)


def _summary(html: str) -> str:
    m = _LEAD_RE.search(html)
    return _clean(m.group(1)) if m else ""


def _official_url(html: str) -> str:
    m = _OFFICIAL_RE.search(html)
    return unescape(m.group(1)).strip() if m else ""


def fetch(detail_path: str, state: str, bill: str, refresh: bool) -> str | None:
    """Return the page HTML, from cache if present."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{state}_{bill}.html")
    if not refresh and os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return f.read()
    url = BASE + detail_path
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"    [error] {state} {bill}: {e}", file=sys.stderr)
        return None
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(r.text)
    time.sleep(THROTTLE)  # throttle only on a real network hit
    return r.text


def main(argv):
    refresh = "--refresh" in argv
    records = src1.parse(SOURCE_HTML)
    print(f"Enriching {len(records)} bills (cache: {CACHE_DIR})...")

    rows = []
    hit = miss = 0
    for (state, bill), rec in sorted(records.items()):
        path = rec.get("detail_path")
        if not path:
            miss += 1
            continue
        html = fetch(path, state, bill, refresh)
        if not html:
            miss += 1
            continue
        title = _title(html)
        summary = _summary(html)
        official = _official_url(html)
        if summary:
            hit += 1
        rows.append({
            "state": state,
            "bill": bill,
            "title": title,
            "desc": summary,
            "official_source": official,
            "summary_caveat": "AI-assisted summary (ailawsbystate); official text controls",
        })
        print(f"  {state} {bill:<10} {'OK' if summary else 'no-summary':<10} {title[:60]}")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["state", "bill", "title", "desc",
                                          "official_source", "summary_caveat"])
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {OUT_CSV}: {len(rows)} rows, {hit} with summaries, {miss} skipped.")


if __name__ == "__main__":
    main(sys.argv[1:])
