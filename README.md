# Job Hunt HQ

A personal job search tool that automatically finds relevant listings across multiple cities, saves them to a local database, and lets you track your application status — all from a web app running on your laptop.

---

## Features

- **Automated job search** — searches JSearch (via RapidAPI) across multiple locations in one run; automatically falls back to Remotive if the monthly quota is hit
- **Relevance filtering** — scores each result against your target titles and drops poor keyword matches before saving
- **Local SQLite database** — all jobs stored in `jobs.db` on your machine; Google Sheets used as a backup
- **Live progress tracker** — browser shows a dino walking through each city as it's searched, powered by Server-Sent Events
- **Status management** — update each job's status (New / Applied / Interviewing / Rejected / Offer) directly from the browser table
- **Editable preferences** — update job titles, locations, and skills from the ⚙️ Settings panel; no terminal needed
- **Search analytics** — bar charts showing jobs added per run and top locations by results

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Database | SQLite (`sqlite3`) |
| Job search | JSearch API (RapidAPI), Remotive API |
| Backup store | Google Sheets (`gspread`) |
| Frontend | Vanilla HTML/CSS/JS (single `index.html`) |
| Auth | Google service account (`google-auth`) |

---

## Screenshots

<img width="1898" height="856" alt="image" src="https://github.com/user-attachments/assets/6c9d4f49-bdc4-43ee-9775-9e96c3a30594" />

<img width="1898" height="857" alt="image" src="https://github.com/user-attachments/assets/b19c4d77-1243-48e8-a9c6-7e4b132819d7" />

![Uploading image.png…]()

## Running Locally

### 1. Clone the repo

```bash
git clone https://github.com/shhouraya/job-hunt-hq.git
cd job-hunt-hq
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1       # Windows PowerShell
pip install -r requirements.txt
```

### 3. Set up your `.env` file

Create a `.env` file in the project root with the following:

```
RAPIDAPI_KEY=your_rapidapi_key
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_SHEET_ID=your_google_sheet_id
```

### 4. Add your Google credentials

Download a service account key from Google Cloud Console and save it as `credentials.json` in the project root. The service account needs Editor access to your Google Sheet.

### 5. Set up the database

```bash
python database.py
```

### 6. Configure your job preferences

```bash
python main.py
```

Or skip this and use the ⚙️ Settings panel in the web app after starting it.

### 7. Start the web app

```bash
python app.py
```

Then open `http://localhost:5000` in your browser.

---

## Required API Keys

This is a personal tool and requires you to supply your own credentials:

| Service | Where to get it |
|---|---|
| JSearch (RapidAPI) | [rapidapi.com](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) — free tier, 200 requests/month |
| Google Sheets API | [Google Cloud Console](https://console.cloud.google.com/) — create a service account and download the JSON key |

---

## Notes

- `jobs.db`, `.env`, and `credentials.json` are gitignored and never committed
- The JSearch free tier allows ~28 full runs per month (200 requests ÷ 7 locations). Quota resets on the 1st of each month
- When JSearch quota is hit, the tool automatically falls back to Remotive for the remainder of that run
