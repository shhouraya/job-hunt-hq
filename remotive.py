"""
remotive.py — Remotive API client
===================================
Zero-auth fallback for when JSearch exceeds its monthly quota.
No API key, no signup, no IP whitelist — just call it.

Remotive only returns remote jobs, so results are not city-specific.
For testing the full pipeline (search → SQLite → Google Sheet → frontend)
this is fine — real job data flows through all the same code paths.

API docs: https://remotive.com/api/remote-jobs
"""

import requests

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


def fetch_jobs_remotive(titles, location):
    """
    Fetch remote job listings matching the given titles from Remotive.

    Parameters
    ----------
    titles   : list[str]  e.g. ["Associate Product Manager", "APM", "Junior PM"]
                          Used to build a keyword search query.
    location : str        Not used — Remotive is remote-only. Kept so this
                          function has the same signature as fetch_jobs_careerjet,
                          meaning search.py's fallback logic needs no changes.

    Returns
    -------
    (jobs, error)
        jobs  — list of raw Remotive job dicts (empty on failure)
        error — error string if something went wrong, otherwise None
    """
    # Join the two most specific titles into a keyword search.
    # "Associate Product Manager APM" hits both senior and abbreviated forms.
    search_query = " ".join(titles[:2])

    params = {
        "search": search_query,
        "limit":  20,
    }

    try:
        response = requests.get(REMOTIVE_URL, params=params, timeout=10)
        if response.status_code != 200:
            return [], f"HTTP {response.status_code}: {response.text[:200]}"

        data = response.json()
        return data.get("jobs", []), None

    except requests.exceptions.Timeout:
        return [], "Remotive request timed out after 10s"
    except Exception as e:
        return [], str(e)


def parse_job_remotive(job):
    """
    Normalise a raw Remotive job dict into the same shape that parse_job()
    produces in search.py so tracker.py / database.py / the frontend see
    no difference between a JSearch result and a Remotive result.

    Remotive field                   → Standard field
    ---------------------------------------------------
    title                            → job_title
    company_name                     → company
    candidate_required_location      → location
    url                              → link
    (not provided)                   → experience  (always None for Remotive)
    """
    return {
        "job_title":  job.get("title",                        "N/A"),
        "company":    job.get("company_name",                 "N/A"),
        "location":   job.get("candidate_required_location",  "Remote"),
        "link":       job.get("url",                          "N/A"),
        "experience": None,
    }
