# Job Search Tool — Project Summary

## Purpose
A job search tool that finds listings matching your preferences, saves them to a local SQLite database (primary store) and Google Sheet (backup), and provides a friendly web frontend to run searches and review results. The "Find My Jobs" button in the web app is the only way to trigger a search.

---

## Project File Reference

| File | Purpose |
|---|---|
| `main.py` | Original one-time setup script — **retired**. Preferences are now edited directly in the web app via the ⚙️ Settings panel, which writes to both `config.json` and the `preferences` SQLite table. |
| `config.json` | Stores your job search preferences. Read by `search.py` and `tracker.py` on every run. Never edited manually. |
| `search.py` | Core search engine. Reads `config.json`, builds an OR query from all job titles, and searches each location. Tries JSearch first — if JSearch returns a 429 (quota exceeded), sets a `jsearch_quota_hit` flag and automatically retries that location and all remaining ones using Remotive. Per-location results include a `source` field (`"JSearch"` or `"Remotive"`) visible in the run log. |
| `remotive.py` | Remotive API client. Zero-auth fallback — no API key or signup required. Calls `https://remotive.com/api/remote-jobs` with a keyword query built from job titles. Returns the same normalised dict shape as JSearch results so the rest of the pipeline sees no difference between sources. |
| `careerjet.py` | Careerjet API client — **built but not in use**. Was built as a fallback before Remotive. Rejected during setup because Careerjet's registration requires a business website URL and a whitelisted static IP address, making it impractical for a personal tool on a home connection with a dynamic IP. File kept for reference. |
| `tracker.py` | Save engine. Imports and calls `search.py`, then deduplicates new jobs against **both** the SQLite database and Google Sheet (union check — transition safety so jobs saved before SQLite existed are not re-added). Writes new jobs to SQLite first (primary), then Google Sheets (backup), both in a single call each. Logs every run to `run_history` table in SQLite and to `tracker_log.txt`. Run log now includes a `Source` column showing which API served each location. Has a `--test` flag that runs the full search without writing anything. |
| `database.py` | SQLite layer. Creates and manages `jobs.db` in the project folder. Defines three tables: `jobs` (every saved listing, deduplicated by link), `preferences` (search settings, written by the Settings panel in the web app), and `run_history` (one row per tracker run, with per-location breakdown stored as JSON). Exposes clean functions used by `tracker.py` and `app.py`: `get_existing_links()`, `save_jobs()`, `log_run()`, `get_all_jobs()`, `get_run_history()`, `update_job_status()`, `save_preferences()`. Run directly (`python database.py`) to create or verify the database. |
| `jobs.db` | SQLite database file created automatically on first run of `database.py`. Contains the `jobs`, `preferences`, and `run_history` tables. Can be opened visually in DB Browser for SQLite. Never commit this file. |
| `app.py` | Flask web server. Exposes six routes: `/` (serves the frontend), `/run-stream` (runs the search and streams live progress via SSE), `/jobs` (fetches all saved jobs from SQLite), `/update-status` (updates a job's status in SQLite), `/preferences` (GET/POST search preferences to/from `config.json` and SQLite), `/analytics` (returns run history and per-location stats for the analytics charts). Also reads all 9 SVG files from `icons/` on each page load. |
| `templates/index.html` | The entire frontend — HTML, CSS, and JavaScript in one file. Communicates with `app.py` via fetch and EventSource. |
| `.env` | Stores secrets: `RAPIDAPI_KEY`, `GOOGLE_CREDENTIALS_PATH`, `GOOGLE_SHEET_ID`. Never share or commit this file. |
| `credentials.json` | Google service account key downloaded from Google Cloud Console. Allows the script to authenticate with Google Sheets API. Never share or commit this file. |
| `tracker_log.txt` | Appended to on every run. Records timestamp, source API, results per location (returned / new / duplicates / errors), and total added vs skipped. Being superseded by the `run_history` SQLite table but kept as a plain-text backup. |
| `.venv/` | Isolated Python virtual environment. Contains all installed libraries for this project only. |

> **Note on `sheets.py`:** There is no separate `sheets.py` file. All Google Sheets logic (connect, read headers, get existing links, append rows) lives inside `tracker.py`. Google Sheets is now write-only (backup) — all reads go through SQLite.

---

## Key Libraries

| Library | Used For |
|---|---|
| `requests` | HTTP calls to JSearch API and Remotive API |
| `sqlite3` | Built into Python — no install needed. Powers `database.py` and `jobs.db`. |
| `python-dotenv` | Reads the `.env` file at runtime |
| `gspread` | Reads and writes to Google Sheets (backup store) |
| `google-auth` | Authenticates with Google using the service account credentials |
| `flask` | Web server for the frontend |
| `feedparser` | Installed but no longer used (was used for RSS feeds before switching to JSearch) |
| `openpyxl` | Installed but not yet used (reserved for potential Excel export feature) |

---

## Key Decisions and Why

**Why JSearch instead of RSS feeds?**
We started with Indeed and RemoteOK RSS feeds but both were either blocked or returned irrelevant results. JSearch (via RapidAPI) is a proper API that aggregates job listings from multiple sources and returns structured data reliably.

**Why not JobSpy?**
JobSpy (a local scraper for Indeed and LinkedIn) was trialled but abandoned. Indeed consistently returned 403 blocks, and the scraping was slow even when it worked. JSearch + Remotive is more reliable for this use case.

**Why a virtual environment?**
Keeps all project libraries isolated from the rest of the system. Prevents version conflicts if other Python projects are ever added to the laptop.

**Why separate `search.py` and `tracker.py`?**
Flexibility. `search.py` can be run standalone to preview results without touching the Google Sheet. `tracker.py` imports `search.py` and adds the save logic on top. This separation also makes it easy for the Flask frontend to call them independently.

**Why OR queries instead of one query per title?**
Reduces API calls from (titles × locations) to just (locations). With 5 titles and 7 locations that would be 35 calls per run — well over the free tier limit. OR queries collapse all titles into one call per location, so 7 calls total.

**Why a 1-second pause between API calls?**
The free JSearch tier rate-limits aggressive requests. A pause between calls keeps the tool within limits and avoids 429 errors.

**Why does JSearch hit a monthly quota — and when does it reset?**
The free JSearch BASIC plan on RapidAPI allows 200 requests/month. At 7 locations per run, that is ~28 full runs before the cap is hit. The quota resets on the 1st of each month.

**Why Remotive as the fallback?**
Remotive's API requires zero authentication — no signup, no API key, no IP whitelist, no quota cap. The only trade-off is that it only returns remote jobs, so results are not city-specific. The fallback is automatic: `search.py` detects the 429 on the first affected location, sets a `jsearch_quota_hit` flag, and switches all remaining locations to Remotive in the same run.

**Why apply the limit after deduplication against the sheet?**
Early versions applied the limit before checking the sheet, so if the top 5 results were already saved, nothing new was ever added. Fixing this means the tool collects all unique results first, removes ones already in the sheet, and then saves up to 5 genuinely new ones.

**Why Server-Sent Events (SSE) for progress updates?**
The search takes 20–30 seconds. Without feedback the page looked frozen. SSE lets the server push live messages to the browser ("Searching Gurgaon...", "Found 10 results") as they happen, without needing WebSockets or page refreshes.

**Why batch Google Sheet writes (`append_rows`) instead of one row at a time?**
Each `append_row` call is a separate HTTP request to the Google Sheets API taking ~2 seconds. Saving 5 jobs one at a time = ~10 extra seconds. `append_rows` sends all rows in one call, saving ~8–10 seconds per run.

---

## Current State of the Frontend (Stage 3 Complete)

The frontend is a single-page Flask app with a clean, professional tool aesthetic — inspired by the Polaris dashboard layout and the Renew colour palette (sky blue, cobalt, orange).

**Visual design:**
- Overall feel: crisp and professional, data-forward. Inter font (400 body / 500 labels / 600 headings / 700 page title), cool blue palette, subtle shadows, low-radius corners.
- Sky blue background (`#E8F4FD`). Content cards are pure white (`#FFFFFF`), `border-radius: 10px`, `1px` border (`#D1E5F5`), and a two-layer shadow with a faint cobalt tint.
- Navigation header: flat cobalt blue `#2B4FBF` — no gradient. Pixel art Chrome-style T-rex dino (`icons/dino-new.svg`, 32px, white, `image-rendering: pixelated`) replaces the old emoji; "Job Hunt HQ" in bold white, subtitle at 65% opacity. Header has a cobalt-tinted drop shadow.
- Table header row: light sky blue `#EBF4FD` with dark text — reads as a structural element without competing with the cobalt nav header.
- ~64 decorative icons scattered across the full scrollable page height using an 8-column grid with one icon per cell, jittered randomly inside each cell. Icons are drawn from 9 real SVG files in `icons/` (cloud, dino, flower, leaf, plant, rocket, star, star2, moon). Each icon is sized randomly between 20–50 px, rotated randomly, and coloured using the CSS `color` property (8 shades of cobalt-to-sky blue) so the SVGs' `currentColor` references inherit the right shade. All icons render at **15% opacity** so they feel like a whisper in the background. The CSS `rotate` and `translate` individual transform properties are used separately so a static random tilt and a vertical float animation compose without conflicting. A `ResizeObserver` on `document.body` watches for page height growth and calls `addStrip(oldHeight, newHeight)` to fill only the newly revealed area — existing icons are never re-generated.

**Colour tokens (`:root`):**
| Token | Value | Used for |
|---|---|---|
| `--bg` | `#E8F4FD` | Page background |
| `--card` | `#FFFFFF` | Card backgrounds |
| `--cobalt` | `#2B4FBF` | Header, secondary button, links, tracker accent |
| `--cobalt-dark` | `#1E3A9A` | Hover/active cobalt shade, status badge text |
| `--cobalt-light` | `#EBF1FF` | Status badge background |
| `--orange` | `#E8651A` | Primary action button |
| `--orange-dark` | `#C7521A` | Hover/error dark shade |
| `--sage` | `#2E7D32` | Milestone done state, success alerts |
| `--sage-dark` | `#1B5E20` | Success text |
| `--yellow` | `#F59E0B` | Milestone searching/pulsing dot |
| `--header-bg` | `#2B4FBF` | Nav header background |
| `--text` | `#1E1E1E` | Primary text |
| `--text-light` | `#6B7280` | Secondary / muted text |
| `--border` | `#D1E5F5` | Card and table borders |
| `--track-line` | `#B8D4F0` | Progress tracker inactive dot border |

**Buttons:**
- 🔍 Find My Jobs — warm orange `#E8651A`; triggers the search and save flow
- 📋 Browse My Saved Jobs — cobalt blue `#2B4FBF`; loads all saved jobs from SQLite
- ⚙️ Settings — light cobalt; toggles the preferences panel open/closed
- All use `border-radius: 6px` (slightly rounded rectangle, not pill), `font-weight: 500`, and a `filter: brightness` hover effect with a subtle lift shadow

**Dino progress tracker:**
- Appears while a search is running, hides when done
- The pixel art Chrome-style T-rex (`icons/dino-new.svg` inlined, 36px, cobalt `#2B4FBF`, `image-rendering: pixelated`) walks along a milestone path
- One milestone dot per location — amber/yellow and pulsing (with cobalt pulse ring) while searching, green when complete, orange-tinted on error
- Dino moves forward with a bouncy CSS transition (`cubic-bezier(0.34, 1.56, 0.64, 1)`) after each city completes
- Happy bounce animation plays when all searches finish

**Results table:**
- Shows Date Found, Job Title, Company, Location, Link (opens in new tab), Status
- Status column is an interactive dropdown — select New / Applied / Interviewing / Rejected / Offer to update directly in the browser; colour-coded and persisted to SQLite immediately
- Dates displayed in human-readable format ("6th June 2026")
- Populated after a search run with newly added jobs, or with all saved jobs via Browse button
- Empty state shows friendly message

**Summary / error banners:**
- Green banner on success: "Woohoo! Found X fresh jobs for you!"
- Confetti burst fires when at least 1 new job is added — colours are orange, cobalt, amber, and sky blue to match the palette
- Orange-toned banner on error (`#FFF4EE` background, `#F5C4A0` border, `--orange-dark` text) with descriptive message

**Last Run timestamp:**
- Displayed below the buttons, loaded from `tracker_log.txt` on page load
- Updates live in the browser after each search run

---

## How to Run

**Start the web frontend:**
```
cd C:\Users\lenovo\job-search-tool
.venv\Scripts\Activate.ps1
python app.py
```
Then open `http://localhost:5000` in a browser.

**Run search from terminal only:**
```
python tracker.py          # search and save to SQLite + Google Sheet
python tracker.py --test   # search only, no saving
python search.py           # preview results in terminal
```

**Update job preferences:**
Use the ⚙️ Settings panel in the web app. `main.py` is retired.

---

## Stage 3 — Complete ✅

### Completed in Stage 3

**SQLite database layer (`database.py` + `jobs.db`)**
Three tables: `jobs` (primary store, deduplicated by link), `preferences` (future replacement for `config.json`), `run_history` (queryable log replacing `tracker_log.txt`). All reads and writes go through clean functions in `database.py`.

**Dual-write save pipeline (`tracker.py`)**
Jobs now write to SQLite first (primary), then Google Sheets (backup) in the same run. Deduplication checks both stores (union) for transition safety. Run log includes a `Source` column showing which API served each location.

**Remotive fallback (`remotive.py` + `search.py`)**
Zero-auth automatic fallback. When JSearch returns 429, `search.py` detects it on the first affected location, sets a flag, and routes all remaining locations through Remotive for the rest of that run. No manual intervention needed.

**SQLite read layer wired into `app.py`**
The `/jobs` route now calls `db_get_all_jobs()` from `database.py` directly instead of `get_all_jobs()` from `tracker.py`. Google Sheets is now write-only (backup) — no reads hit the sheet at runtime. `get_all_jobs` removed from the `tracker` import in `app.py`.

**Status management in the frontend**
Status column is now an interactive dropdown in the browser table. Selecting a value POSTs to a new `/update-status` route in `app.py`, which calls `database.update_job_status()`. Colour-coded per status: cobalt (New), orange (Applied), amber (Interviewing), red (Rejected), green (Offer). Change is persisted to `jobs.db` immediately and survives page refresh.

**Editable preferences via the frontend**
A collapsible ⚙️ Settings panel in the action card lets you view and edit all search preferences in the browser. Fields: primary job title, alternate titles, locations, experience level, skills, salary range. Pre-populated from `config.json` on page load. Saving POSTs to a new `GET/POST /preferences` route in `app.py`, which writes both `config.json` (so the search pipeline keeps working unchanged) and the `preferences` SQLite table. `main.py` is now retired for normal use.

**Search history / analytics**
A 📊 Search Analytics card at the bottom of the page shows two CSS bar charts (no external libraries): jobs added per run (last 10 runs, cobalt bars) and top locations by total new jobs across all runs (orange bars). Data served by a new `GET /analytics` route that queries `run_history`. Charts animate in on load and refresh automatically after each search run. Dates displayed in human-readable format ("6th June 2026") everywhere via a `formatDate()` JS helper.

**Relevance filtering (`relevance.py`)**
A new `relevance.py` module scores each incoming job title against the user's target titles (0.0–1.0). Two-step scoring: (1) if any target phrase appears verbatim in the job title → instant 1.0 pass; (2) approximate word overlap using 5-character prefix matching so "manager" and "management" count as the same root. Threshold: 0.6. Filtering runs in `search.py` after parsing each job, before deduplication. Filtered count tracked in `location_stats`, shown in the live progress message, logged to `run_history` details JSON and `tracker_log.txt`. A `test_relevance.py` script lets you verify scoring against sample titles without running the full search.

**JobSpy trialled and reverted**
`python-jobspy` was installed and wired in as a replacement for JSearch. Indeed consistently returned 403 blocks across all city locations, and scraping was slow even when LinkedIn responded. JSearch + Remotive restored as the working setup. `python-jobspy` left installed but unused.

**Remotive fallback behaviour confirmed**
When JSearch quota is hit, all locations fall back to Remotive. Testing confirmed Remotive does not carry APM/product manager roles — its listings skew heavily towards engineering, writing, and sales. The relevance filter correctly drops all Remotive results (scoring below 0.6), so no irrelevant jobs are saved. This is correct behaviour: 0 new jobs when JSearch quota is exhausted is better than saving irrelevant results. JSearch quota resets on the 1st of each month.

**Test scripts**
- `test_relevance.py` — scores a set of sample job titles against your targets to verify the relevance filter
- `test_remotive.py` — fetches live Remotive results and prints the score for each title, useful for diagnosing fallback behaviour

