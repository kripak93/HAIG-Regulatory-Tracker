"""
Source adapters for the AI Regulatory Tracker.

Each module parses one external source (a saved HTML page, an API response,
etc.) into the canonical bill-record shape the pipeline consumes. New sources
drop in here and get merged by build_archive.py.

A source adapter exposes:
    SOURCE_ID    : short stable id (e.g. "ailawsbystate")
    parse(path)  -> dict[(state, bill)] -> record
"""
