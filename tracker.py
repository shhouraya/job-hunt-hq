import os
import argparse
from datetime import datetime, date
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import database

LOG_FILE = "tracker_log.txt"

def write_log(location_stats, added, skipped, test_mode):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append(f"\n{'='*55}")
    lines.append(f"Run at : {timestamp}{'  [TEST MODE]' if test_mode else ''}")
    lines.append(f"{'='*55}")
    lines.append(f"{'Location':<20} {'Source':<12} {'Returned':>8} {'Filtered':>8} {'New':>6} {'Dupes':>6} {'Error'}")
    lines.append(f"{'-'*78}")
    for s in location_stats:
        error_text  = s["error"] if s["error"] else "-"
        source_text = s.get("source", "JSearch")
        lines.append(
            f"{s['location']:<20} {source_text:<12} {s['returned']:>8} {s.get('filtered', 0):>8} {s['new']:>6} {s['duplicates']:>6}  {error_text}"
        )
    lines.append(f"{'-'*78}")
    lines.append(f"{'TOTAL':<20} {'':12} {sum(s['returned'] for s in location_stats):>8} "
                 f"{sum(s.get('filtered', 0) for s in location_stats):>8} "
                 f"{sum(s['new'] for s in location_stats):>6} "
                 f"{sum(s['duplicates'] for s in location_stats):>6}")
    lines.append(f"\nSaved           : Added {added} (SQLite + Sheet), Skipped {skipped} (already existed)")
    if test_mode:
        lines.append("No rows written — test mode.")

    log_text = "\n".join(lines)
    print(log_text)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_text + "\n")

load_dotenv()

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
SHEET_ID         = os.getenv("GOOGLE_SHEET_ID")
SCOPES           = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
HEADERS = ["Date Found", "Job Title", "Company", "Location", "Link", "Status", "Notes"]

def connect_to_sheet():
    creds  = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

def ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if first_row[:len(HEADERS)] != HEADERS:
        sheet.insert_row(HEADERS, index=1)

def get_existing_links(sheet):
    # Column 5 is the Link column — skip the header row with [1:]
    return set(sheet.col_values(5)[1:])

def get_all_jobs():
    sheet    = connect_to_sheet()
    rows     = sheet.get_all_records(expected_headers=HEADERS)
    jobs     = []
    for row in rows:
        jobs.append({
            "date":      row.get("Date Found", ""),
            "job_title": row.get("Job Title", ""),
            "company":   row.get("Company", ""),
            "location":  row.get("Location", ""),
            "link":      row.get("Link", ""),
            "status":    row.get("Status", ""),
        })
    return jobs

def get_last_run():
    if not os.path.exists(LOG_FILE):
        return None
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in reversed(lines):
        if line.strip().startswith("Run at :"):
            return line.strip().replace("Run at : ", "").replace("  [TEST MODE]", "").strip()
    return None

def save_results(results, location_stats, test_mode=False, limit=5, on_progress=None):
    if not results:
        write_log(location_stats, added=0, skipped=0, test_mode=test_mode)
        return [], 0, 0

    # ── Deduplication ─────────────────────────────────────────────────────
    # We check both stores so that jobs already saved to Google Sheets
    # (before SQLite existed) are not re-added to either destination.
    # Once the sheet and the database are fully in sync this union is
    # redundant, but it is always safe to leave in place.
    if on_progress:
        on_progress("Connecting to Google Sheet...")
    sheet          = connect_to_sheet()
    ensure_headers(sheet)
    sheet_links    = get_existing_links(sheet)
    sqlite_links   = database.get_existing_links()
    existing_links = sqlite_links | sheet_links   # union — skip if in either

    today         = date.today().strftime("%Y-%m-%d")
    skipped       = 0
    added_jobs    = []
    rows_to_write = []   # for Google Sheets  — list of lists
    db_rows       = []   # for SQLite         — list of dicts

    for job in results:
        link = job.get("link", "")
        if link in existing_links:
            skipped += 1
            continue

        if len(added_jobs) >= limit:
            break

        # Google Sheets row (list, matches HEADERS column order)
        rows_to_write.append([
            today,
            job.get("job_title", ""),
            job.get("company", ""),
            job.get("location", ""),
            link,
            "New",
            "",
        ])

        # SQLite row (dict, matches database.save_jobs schema)
        db_rows.append({
            "date_found": today,
            "job_title":  job.get("job_title", ""),
            "company":    job.get("company", ""),
            "location":   job.get("location", ""),
            "link":       link,
            "source":     None,   # source location tag wired up in a later stage
        })

        # Frontend / return value row (dict, matches app.py /jobs response shape)
        added_jobs.append({
            "date":      today,
            "job_title": job.get("job_title", ""),
            "company":   job.get("company", ""),
            "location":  job.get("location", ""),
            "link":      link,
            "status":    "New",
        })

    if rows_to_write:
        if on_progress:
            on_progress(f"Saving {len(rows_to_write)} new job{'s' if len(rows_to_write) != 1 else ''} to database + sheet...")
        if not test_mode:
            # Primary store — SQLite
            database.save_jobs(db_rows)
            # Backup store — Google Sheets (single batch API call)
            sheet.append_rows(rows_to_write)

    # Record this run in run_history (skipped in test mode — no real data was saved)
    if not test_mode:
        details = {
            s["location"]: {
                "found":    s["returned"],
                "new":      s["new"],
                "filtered": s.get("filtered", 0),
                "error":    bool(s["error"]),
            }
            for s in location_stats
        }
        database.log_run(
            jobs_found   = sum(s["returned"] for s in location_stats),
            jobs_added   = len(added_jobs),
            jobs_skipped = skipped,
            details      = details,
        )

    added = len(added_jobs)
    write_log(location_stats, added, skipped, test_mode)
    if on_progress:
        on_progress(f"Done! Added {added}, skipped {skipped} already in database.")
    return added_jobs, added, skipped

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save job results to Google Sheets")
    parser.add_argument("--test", action="store_true", help="Run without writing to the sheet")
    args = parser.parse_args()

    # Import here to avoid circular dependency if run standalone
    from search import load_config, search_all

    config                 = load_config()
    results, location_stats = search_all(config)
    save_results(results, location_stats, test_mode=args.test)
