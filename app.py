import os
import queue
import threading
import json
from flask import Flask, render_template, jsonify, Response, stream_with_context, request
from search import load_config, search_all
from tracker import save_results, get_last_run
from database import get_all_jobs as db_get_all_jobs, update_job_status, save_preferences, get_run_history

app = Flask(__name__)

_ICON_NAMES = ['cloud', 'dino', 'flower', 'leaf', 'plant', 'rocket', 'star', 'star2', 'moon']
_ICONS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')

def _load_svg_icons():
    icons = {}
    for name in _ICON_NAMES:
        path = os.path.join(_ICONS_DIR, f'{name}.svg')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                icons[name] = f.read()
        except Exception:
            icons[name] = ''
    return icons

@app.route("/")
def home():
    last_run  = get_last_run()
    svg_icons = _load_svg_icons()
    return render_template("index.html", last_run=last_run, svg_icons=svg_icons)

@app.route("/run-stream")
def run_stream():
    q = queue.Queue()

    def on_progress(msg):
        q.put({"type": "progress", "message": msg})

    def run_in_thread():
        try:
            config                     = load_config()
            results, location_stats    = search_all(config, on_progress=on_progress)
            added_jobs, added, skipped = save_results(results, location_stats, on_progress=on_progress)
            q.put({"type": "done", "jobs": added_jobs, "added": added, "skipped": skipped})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})

    thread = threading.Thread(target=run_in_thread)
    thread.start()

    def generate():
        while True:
            item = q.get()
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("done", "error"):
                break

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route("/jobs", methods=["GET"])
def all_jobs():
    try:
        rows = db_get_all_jobs()
        jobs = [
            {
                "id":        row["id"],
                "date":      row["date_found"],
                "job_title": row["job_title"],
                "company":   row["company"],
                "location":  row["location"],
                "link":      row["link"],
                "status":    row["status"],
            }
            for row in rows
        ]
        return jsonify({"status": "success", "jobs": jobs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/preferences", methods=["GET"])
def get_preferences():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), "r", encoding="utf-8") as f:
            config = json.load(f)
        return jsonify({"status": "success", "preferences": config})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/preferences", methods=["POST"])
def save_prefs():
    try:
        data = request.get_json()
        config = {
            "job_title":        data["job_title"].strip(),
            "alternate_titles": [t.strip() for t in data["alternate_titles"] if t.strip()],
            "location":         [l.strip() for l in data["location"]         if l.strip()],
            "experience":       data["experience"].strip(),
            "skills":           [s.strip() for s in data["skills"]           if s.strip()],
            "salary_range":     data["salary_range"].strip(),
        }
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        save_preferences(
            job_titles  = [config["job_title"]] + config["alternate_titles"],
            locations   = config["location"],
            experience  = config["experience"],
            skills      = config["skills"],
            salary      = config["salary_range"],
        )
        return jsonify({"status": "success"})
    except (KeyError, ValueError) as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/analytics", methods=["GET"])
def analytics():
    try:
        history = get_run_history(limit=50)

        # Last 10 runs in chronological order for the bar chart
        recent = list(reversed(history[:10]))
        runs_chart = [
            {
                "label": row["timestamp"][:10],
                "added": row["jobs_added"],
                "found": row["jobs_found"],
            }
            for row in recent
        ]

        # Aggregate new jobs per city across all runs
        location_totals = {}
        for row in history:
            details = row.get("details") or {}
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except Exception:
                    continue
            for city, stats in details.items():
                if isinstance(stats, dict):
                    location_totals[city] = location_totals.get(city, 0) + stats.get("new", 0)

        by_location = sorted(
            [{"location": k, "total_new": v} for k, v in location_totals.items()],
            key=lambda x: x["total_new"],
            reverse=True,
        )

        return jsonify({
            "status":      "success",
            "runs":        runs_chart,
            "by_location": by_location,
            "total_runs":  len(history),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/update-status", methods=["POST"])
def update_status():
    try:
        data       = request.get_json()
        job_id     = int(data["job_id"])
        new_status = data["new_status"]
        update_job_status(job_id, new_status)
        return jsonify({"status": "success"})
    except (ValueError, KeyError) as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
