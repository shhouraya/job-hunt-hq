"""
relevance.py — Job title relevance scoring
==========================================
Scores an incoming job title against the user's target titles and returns
a float 0.0–1.0.  Used by search.py to drop poor keyword matches before
they reach the save pipeline.

Scoring rules (highest wins):
  1. Any target phrase is a substring of the job title  → 1.0 (instant pass)
  2. Approximate word overlap ratio — how many words of a target title
     appear in the job title, using 5-char prefix matching so
     "manager" and "management" count as the same root.
     Score = matched_words / total_target_words, best across all targets.

Threshold: 0.6  (at least 60 % of any target title's words must be present)

Examples
--------
  "Senior Product Manager"        vs ["Product Manager", "APM"]  →  1.0  ✓
  "Product Management Lead"       vs same                        →  0.67 ✓
  "Portfolio Manager"             vs same                        →  0.33 ✗
  "Business Development Manager"  vs same                        →  0.33 ✗
  "APM – Associate Product Mgr"   vs same                        →  1.0  ✓
"""

import re

THRESHOLD = 0.6


def _words(text):
    """Lowercase and tokenise, stripping punctuation."""
    return re.sub(r'[^a-z0-9 ]', '', text.lower()).split()


def score_job(job_title, target_titles):
    """
    Return a relevance score 0.0–1.0.
    target_titles should be the full list: [primary] + alternate_titles.
    """
    job_title_lower = job_title.lower()
    job_words       = set(_words(job_title))

    best = 0.0
    for target in target_titles:
        # Rule 1 — target phrase contained verbatim in job title
        if target.lower() in job_title_lower:
            return 1.0

        target_words = _words(target)
        if not target_words:
            continue

        # Rule 2 — approximate word overlap (prefix-5 handles manager/management etc.)
        matched = sum(
            1 for tw in target_words
            if any(
                tw == jw or (len(tw) >= 5 and len(jw) >= 5 and tw[:5] == jw[:5])
                for jw in job_words
            )
        )
        best = max(best, matched / len(target_words))

    return best


def is_relevant(job_title, target_titles, threshold=THRESHOLD):
    """Return True if the job title is relevant enough to keep."""
    return score_job(job_title, target_titles) >= threshold
