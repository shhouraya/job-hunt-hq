"""
careerjet.py — Careerjet API client
=====================================
Fallback job source used automatically when JSearch exceeds its monthly quota.

How it fits in:
  search.py calls fetch_jobs_careerjet() and parse_job_careerjet() exactly as
  it calls fetch_jobs() and parse_job() for JSearch.  The returned dicts are
  shaped identically so tracker.py / database.py / app.py never need to know
  which source was used.

Registration:
  Get a free Affiliate ID at https://www.careerjet.co.in/partners/api
  Add to .env:  CAREERJET_APP_ID=your_id_here
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

CAREERJET_APP_ID = os.getenv("CAREERJET_APP_ID")
CAREERJET_URL    = "http://public.api.careerjet.net/search"


def fetch_jobs_careerjet(titles, location):
    """
    Search Careerjet for jobs matching any of the given titles in a location.

    Parameters
    ----------
    titles   : list[str]  e.g. ["Associate Product Manager", "APM", "Junior PM"]
    location : str        e.g. "Bangalore"

    Returns
    -------
    (jobs, error)
        jobs  — list of raw Careerjet job dicts (empty list on failure)
        error — error string if something went wrong, otherwise None
    """
    if not CAREERJET_APP_ID:
        return [], "CAREERJET_APP_ID not set in .env — see careerjet.py for setup instructions"

    # Careerjet uses simple keyword search, not Boolean OR.
    # Joining titles with spaces tells the engine to find jobs containing
    # any of these words, which is close enough for our purpose.
    keywords = " ".join(titles)

    params = {
        "affid":       CAREERJET_APP_ID,
        "keywords":    keywords,
        "location":    location,
        "locale_code": "en_IN",   # India English
        "sort":        "date",    # newest first
        "pagesize":    20,        # match typical JSearch result count
        "page":        1,
    }

    try:
        response = requests.get(CAREERJET_URL, params=params, timeout=10)
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            return [], error_msg

        data = response.json()

        # Careerjet returns {"type": "ERROR", "message": "..."} for bad requests
        if data.get("type") == "ERROR":
            return [], f"Careerjet error: {data.get('message', 'Unknown error')}"

        return data.get("jobs", []), None

    except requests.exceptions.Timeout:
        return [], "Careerjet request timed out after 10s"
    except Exception as e:
        return [], str(e)


def parse_job_careerjet(job):
    """
    Normalise a raw Careerjet job dict into the same shape that parse_job()
    produces in search.py.

    Careerjet field → Standard field
    ---------------------------------
    title           → job_title
    company         → company
    locations       → location
    url             → link
    (none)          → experience  (Careerjet doesn't return structured exp data)
    """
    return {
        "job_title":  job.get("title",     "N/A"),
        "company":    job.get("company",   "N/A") or "N/A",   # can be None
        "location":   job.get("locations", "N/A"),
        "link":       job.get("url",       "N/A"),
        "experience": None,
    }
