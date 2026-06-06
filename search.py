import json
import requests
import argparse
import time
from dotenv import load_dotenv
import os

from remotive import fetch_jobs_remotive, parse_job_remotive
from relevance import is_relevant

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
JSEARCH_URL  = "https://jsearch.p.rapidapi.com/search"
HEADERS      = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": "jsearch.p.rapidapi.com"
}


def load_config(path="config.json"):
    with open(path) as f:
        return json.load(f)


def build_title_query(config):
    all_titles = [config["job_title"]] + config.get("alternate_titles", [])
    return " OR ".join(f'"{t}"' for t in all_titles)


def fetch_jobs(title_query, location, num_pages=1):
    query  = f"{title_query} in {location}"
    params = {
        "query":       query,
        "num_pages":   num_pages,
        "date_posted": "all",
    }
    try:
        response = requests.get(JSEARCH_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"  Error {error_msg}")
            return [], error_msg
        return response.json().get("data", []), None
    except Exception as e:
        error_msg = str(e)
        print(f"  Exception: {error_msg}")
        return [], error_msg


def parse_job(job):
    return {
        "job_title":  job.get("job_title", "N/A"),
        "company":    job.get("employer_name", "N/A"),
        "location":   f"{job.get('job_city', '') or ''}, {job.get('job_country', '') or ''}".strip(", "),
        "experience": job.get("job_required_experience", {}).get("required_experience_in_months"),
        "link":       job.get("job_apply_link") or job.get("job_google_link", "N/A"),
    }


def format_experience(months):
    if months is None:
        return "Not specified"
    years = months // 12
    rem   = months % 12
    if years and rem:
        return f"{years}y {rem}m"
    if years:
        return f"{years} year{'s' if years > 1 else ''}"
    return f"{rem} month{'s' if rem > 1 else ''}"


def search_all(config, limit=None, on_progress=None):
    title_query = build_title_query(config)
    all_titles  = [config["job_title"]] + config.get("alternate_titles", [])
    locations   = config.get("location", ["Remote"])

    print(f"Title query : {title_query}")
    print(f"Locations   : {', '.join(locations)}\n")

    seen_links     = set()
    results        = []
    location_stats = []

    # Once JSearch returns a 429, switch to Remotive for all remaining
    # locations in this run so we don't waste time hitting a known-dead API.
    jsearch_quota_hit = False

    for i, loc in enumerate(locations):

        # ── Choose source ──────────────────────────────────────────────────
        if jsearch_quota_hit:
            print(f"Searching '{loc}' (Remotive)...")
            if on_progress:
                on_progress(f"Searching {loc}...")
            jobs, error = fetch_jobs_remotive(all_titles, loc)
            parse_fn    = parse_job_remotive
            source      = "Remotive"

        else:
            print(f"Searching '{loc}' (JSearch)...")
            if on_progress:
                on_progress(f"Searching {loc}...")
            jobs, error = fetch_jobs(title_query, loc)
            parse_fn    = parse_job
            source      = "JSearch"

            # If JSearch quota exceeded, retry this location with Remotive
            if error and "429" in error:
                jsearch_quota_hit = True
                print("  JSearch quota exceeded — switching to Remotive for remaining locations...")
                jobs, error = fetch_jobs_remotive(all_titles, loc)
                parse_fn    = parse_job_remotive
                source      = "Remotive"

        # ── Process results ────────────────────────────────────────────────
        raw_count      = len(jobs)
        new_count      = 0
        dupe_count     = 0
        filtered_count = 0

        for job in jobs:
            parsed = parse_fn(job)
            if not is_relevant(parsed["job_title"], all_titles):
                filtered_count += 1
                continue
            if parsed["link"] not in seen_links:
                seen_links.add(parsed["link"])
                results.append(parsed)
                new_count += 1
            else:
                dupe_count += 1

        location_stats.append({
            "location":   loc,
            "returned":   raw_count,
            "new":        new_count,
            "duplicates": dupe_count,
            "filtered":   filtered_count,
            "error":      error,
            "source":     source,
        })

        if on_progress:
            if error:
                on_progress(f"{loc}: error — {error[:60]}")
            else:
                filter_note = f", {filtered_count} filtered" if filtered_count else ""
                on_progress(f"{loc}: found {raw_count} result{'s' if raw_count != 1 else ''}{filter_note}")

        if i < len(locations) - 1:
            time.sleep(1)

    return (results[:limit] if limit else results), location_stats


def print_results(results):
    if not results:
        print("\nNo results found.")
        return
    print(f"\n=== Top {len(results)} Results ===\n")
    for i, job in enumerate(results, 1):
        print(f"[{i}] {job['job_title']}")
        print(f"    Company    : {job['company']}")
        print(f"    Location   : {job['location']}")
        print(f"    Experience : {format_experience(job.get('experience'))}")
        print(f"    Link       : {job['link']}")
        print()


def main():
    if not RAPIDAPI_KEY:
        print("Error: RAPIDAPI_KEY not found in .env file.")
        return

    parser = argparse.ArgumentParser(description="Search jobs via JSearch API")
    parser.add_argument("--test", action="store_true", help="Run without saving anything")
    args = parser.parse_args()

    if args.test:
        print("[TEST MODE] Nothing will be saved.\n")

    config     = load_config()
    results, _ = search_all(config)
    print_results(results)


if __name__ == "__main__":
    main()
