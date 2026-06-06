"""
database.py — SQLite layer for Job Hunt HQ
==========================================
Creates and manages jobs.db in the project folder.

Tables
------
  jobs          Every job listing found by the search engine.
  preferences   Your search settings (single row, always id = 1).
  run_history   One row per automated run — used for analytics.

Usage
-----
  Run directly to create / verify the database:
      python database.py

  Import from other modules:
      from database import init_db, get_all_jobs, save_jobs, ...
"""

import sqlite3
import json
import os
from datetime import datetime

# ── Path ────────────────────────────────────────────────────────────────────
# Resolve relative to this file so imports work regardless of working directory
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jobs.db')


# ── Connection ───────────────────────────────────────────────────────────────

def get_connection():
    """
    Open and return a database connection.
    row_factory = sqlite3.Row makes columns accessible by name (row['title'])
    as well as by index, which is much more readable than plain tuples.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema ───────────────────────────────────────────────────────────────────

def init_db():
    """
    Create all three tables if they do not already exist.
    Safe to call on every app start — CREATE TABLE IF NOT EXISTS is a no-op
    when the table is already there, so it never overwrites existing data.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""

        -- ── jobs ──────────────────────────────────────────────────────────
        -- One row per unique job listing.
        -- 'link' has a UNIQUE constraint so the same URL can never be
        --  inserted twice — this replaces the duplicate-check we currently
        --  do by reading all links from Google Sheets before each run.
        -- 'status' defaults to 'New' and will be updatable from the web UI
        --  in a later stage (replaces editing the Google Sheet manually).
        -- 'source' records which location query surfaced this listing,
        --  useful for analytics ("Delhi returns the most APM roles").

        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date_found  TEXT    NOT NULL,
            job_title   TEXT    NOT NULL,
            company     TEXT    NOT NULL,
            location    TEXT    NOT NULL,
            link        TEXT    NOT NULL UNIQUE,
            status      TEXT    NOT NULL DEFAULT 'New',
            source      TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );


        -- ── preferences ───────────────────────────────────────────────────
        -- Single-row table — there is always exactly one row with id = 1.
        -- Lists (job_titles, locations, skills) are stored as JSON strings,
        --  e.g. '["APM", "Product Manager", "Associate PM"]'
        -- This replaces config.json.  A later stage will let you edit these
        --  fields directly from the web UI instead of running main.py.
        -- Use INSERT OR REPLACE to update (see save_preferences below).

        CREATE TABLE IF NOT EXISTS preferences (
            id          INTEGER PRIMARY KEY DEFAULT 1
                                CHECK (id = 1),   -- enforce single-row
            job_titles  TEXT,
            locations   TEXT,
            experience  TEXT,
            skills      TEXT,
            salary      TEXT,
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );


        -- ── run_history ───────────────────────────────────────────────────
        -- One row per automated run (tracker.py execution).
        -- 'details' is a JSON string holding the per-location breakdown,
        --  e.g. {"Delhi": {"found": 12, "new": 3}, "Bangalore": {...}}
        -- This replaces tracker_log.txt with something queryable —
        --  "how many jobs found this week?" becomes a simple SQL query
        --  rather than parsing a text file.

        CREATE TABLE IF NOT EXISTS run_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            jobs_found   INTEGER NOT NULL DEFAULT 0,
            jobs_added   INTEGER NOT NULL DEFAULT 0,
            jobs_skipped INTEGER NOT NULL DEFAULT 0,
            details      TEXT
        );

    """)

    conn.commit()
    conn.close()


# ── Jobs ─────────────────────────────────────────────────────────────────────

def get_all_jobs():
    """
    Return every job row as a list of dicts, newest first.
    Used by the /jobs route in app.py.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY date_found DESC, id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_existing_links():
    """
    Return a set of all job links already in the database.
    Used by tracker.py to skip duplicates before inserting — replaces the
    Google Sheets link-scan that currently runs before every save.
    """
    conn = get_connection()
    rows = conn.execute("SELECT link FROM jobs").fetchall()
    conn.close()
    return {row['link'] for row in rows}


def save_jobs(job_list):
    """
    Insert a list of job dicts into the jobs table.
    Silently ignores any row whose link already exists (INSERT OR IGNORE)
    so it is safe to call even if deduplication was done upstream.

    Each dict in job_list should have keys:
        date_found, job_title, company, location, link, source
    Status defaults to 'New' at the database level.

    Returns the number of rows actually inserted.
    """
    conn = get_connection()
    inserted = 0
    for job in job_list:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (date_found, job_title, company, location, link, source)
            VALUES
                (:date_found, :job_title, :company, :location, :link, :source)
            """,
            job
        )
        inserted += cursor.rowcount
    conn.commit()
    conn.close()
    return inserted


def update_job_status(job_id, new_status):
    """
    Update the status of a single job by its id.
    Called by the /update-status route added in a later stage.
    Valid values: 'New', 'Applied', 'Interviewing', 'Rejected', 'Offer'
    """
    valid = {'New', 'Applied', 'Interviewing', 'Rejected', 'Offer'}
    if new_status not in valid:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid}")
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET status = ? WHERE id = ?",
        (new_status, job_id)
    )
    conn.commit()
    conn.close()


# ── Preferences ──────────────────────────────────────────────────────────────

def get_preferences():
    """
    Return the preferences row as a dict, or None if never set.
    Lists (job_titles, locations, skills) are returned as Python lists —
    this function handles the JSON decode so callers never see raw strings.
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM preferences WHERE id = 1").fetchone()
    conn.close()
    if row is None:
        return None
    prefs = dict(row)
    # Decode JSON-stored lists back into Python lists
    for field in ('job_titles', 'locations', 'skills'):
        if prefs.get(field):
            try:
                prefs[field] = json.loads(prefs[field])
            except (json.JSONDecodeError, TypeError):
                prefs[field] = []
    return prefs


def save_preferences(job_titles, locations, experience, skills, salary):
    """
    Write (or overwrite) the single preferences row.
    Lists are serialised to JSON strings for storage.
    Called by the settings panel added in a later stage — replaces main.py.
    """
    conn = get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO preferences
            (id, job_titles, locations, experience, skills, salary, updated_at)
        VALUES
            (1, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        """,
        (
            json.dumps(job_titles) if isinstance(job_titles, list) else job_titles,
            json.dumps(locations)  if isinstance(locations,  list) else locations,
            experience,
            json.dumps(skills)     if isinstance(skills,     list) else skills,
            salary,
        )
    )
    conn.commit()
    conn.close()


# ── Run History ───────────────────────────────────────────────────────────────

def log_run(jobs_found, jobs_added, jobs_skipped, details=None):
    """
    Append a row to run_history after every tracker.py execution.
    'details' should be a dict like:
        {"Delhi": {"found": 12, "new": 3, "error": False}, ...}
    It is serialised to JSON for storage.
    """
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO run_history (jobs_found, jobs_added, jobs_skipped, details)
        VALUES (?, ?, ?, ?)
        """,
        (
            jobs_found,
            jobs_added,
            jobs_skipped,
            json.dumps(details) if details else None,
        )
    )
    conn.commit()
    conn.close()


def get_run_history(limit=30):
    """
    Return the most recent 'limit' run rows as a list of dicts, newest first.
    'details' is decoded from JSON back to a dict if present.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM run_history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    history = []
    for row in rows:
        entry = dict(row)
        if entry.get('details'):
            try:
                entry['details'] = json.loads(entry['details'])
            except (json.JSONDecodeError, TypeError):
                pass
        history.append(entry)
    return history


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Initialising database at: {DB_PATH}")
    init_db()
    print()
    print("Tables created successfully:")

    # Quick verification — list the tables and their column names
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    for table in tables:
        name = table['name']
        cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
        col_names = [c['name'] for c in cols]
        print(f"  {name}: {', '.join(col_names)}")

    conn.close()
    print()
    print("Done. Open jobs.db in DB Browser for SQLite to inspect visually.")
