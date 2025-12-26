"""
keep_alive.py (PRODUCTION / Render Ready)
- Flask WebApp + API
- Background job queue (non-blocking submissions)
- Telegram bot runs in background thread (when running under gunicorn)
- Compatible with Render Free Plan (single service)
"""

from __future__ import annotations
import os
import threading
from flask import Flask, jsonify, request, send_from_directory

# Existing logic
from utils.problem_utils import load_all_problems, find_problem_by_id
import user_utils
from handlers.submit import run_code

# Job queue
from utils.job_queue import create_job, get_job, start_worker_once

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")

app = Flask(__name__, static_folder=WEBAPP_DIR)

# =========================
# ✅ Background Worker logic
# =========================
def _process_submission_job(payload: dict):
    """
    Judge code using hidden testcases (same logic as telegram bot submit)
    """
    pid = int(payload["problem_id"])
    lang = payload["language"]
    code = payload.get("code", "")
    uid = payload.get("user_id")

    prob = find_problem_by_id(pid)
    if not prob:
        return {"ok": False, "verdict": "Problem not found"}

    allow_unordered = bool(prob.get("allow_unordered_output", False))

    for tc in prob.get("test_cases", []):
        out = run_code(lang, code, tc.get("input", ""))

        # runner error
        if isinstance(out, str) and out.startswith(("⚠️", "⏰", "❗")):
            return {"ok": False, "verdict": out}

        expected = (tc.get("output", "") or "").strip()
        actual = (out or "").strip()

        if allow_unordered:
            expected_set = sorted([x.strip() for x in expected.splitlines() if x.strip()])
            actual_set = sorted([x.strip() for x in actual.splitlines() if x.strip()])
            if expected_set != actual_set:
                return {
                    "ok": True,
                    "verdict": "WA",
                    "expected": expected,
                    "actual": actual
                }
        else:
            if expected != actual:
                return {
                    "ok": True,
                    "verdict": "WA",
                    "expected": expected,
                    "actual": actual
                }

    # ✅ AC update
    user_utils.update_user_score(uid, prob.get("points", 1))
    user_utils.add_solved_problem(uid, pid)

    return {"ok": True, "verdict": "AC"}


# ✅ Start worker only once (safe with gunicorn threads)
_WORKER_STARTED = False
def ensure_workers():
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    start_worker_once(_process_submission_job, num_workers=3)
    _WORKER_STARTED = True
    print("🚀 Judge workers started!")


# =========================
# ✅ Telegram Bot background
# =========================
_BOT_STARTED = False
def start_bot_background():
    """
    Start bot polling in a background thread.
    Only runs when LOCAL_MODE != 1
    """
    global _BOT_STARTED
    if _BOT_STARTED:
        return

    if os.getenv("LOCAL_MODE", "0") == "1":
        print("✅ LOCAL_MODE=1 -> Bot disabled (WebApp only)")
        return

    def runner():
        try:
            from my_bot_runner import run_bot
            run_bot()
        except Exception as e:
            print("❌ Bot crashed:", e)

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    _BOT_STARTED = True
    print("🤖 Bot started in background thread!")


# =========================
# Health
# =========================
@app.route("/")
def home():
    return "I am alive!", 200

@app.route("/ping")
def ping():
    return "pong", 200


# =========================
# WebApp
# =========================
@app.route("/webapp")
def webapp_index():
    return send_from_directory(WEBAPP_DIR, "index.html")

@app.route("/webapp/<path:path>")
def webapp_assets(path: str):
    return send_from_directory(WEBAPP_DIR, path)


# =========================
# Auth Helper
# =========================
def get_user_id_from_request() -> int | None:
    uid = request.headers.get("X-User-Id") or request.args.get("user_id")
    if not uid:
        return None
    try:
        return int(uid)
    except Exception:
        return None

def require_user() -> int:
    uid = get_user_id_from_request()
    if uid is None:
        raise ValueError("Missing user id")
    return uid


# =========================
# Problems API (sorted ✅)
# =========================
@app.get("/api/problems")
def api_problems():
    problems = load_all_problems()
    problems.sort(key=lambda x: int(x.get("id", 0)))  # ✅ sort ascending

    lite = []
    for p in problems:
        pp = dict(p)
        pp.pop("test_cases", None)
        lite.append(pp)

    return jsonify({"ok": True, "problems": lite})


@app.get("/api/problem/<int:pid>")
def api_problem(pid: int):
    prob = find_problem_by_id(pid)
    if not prob:
        return jsonify({"ok": False, "error": "Problem not found"}), 404

    safe_prob = dict(prob)
    safe_prob.pop("test_cases", None)
    return jsonify({"ok": True, "problem": safe_prob})


# =========================
# Profile/History/Rankings
# =========================
@app.get("/api/profile")
def api_profile():
    try:
        uid = require_user()
        user_utils.ensure_user_initialized(uid)
        profile = user_utils.get_user_profile(uid)
        return jsonify({"ok": True, "profile": profile})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 401


@app.get("/api/history")
def api_history():
    try:
        uid = require_user()
        user_utils.ensure_user_initialized(uid)
        history = user_utils.get_user_submissions(uid)
        return jsonify({"ok": True, "history": history})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 401


@app.get("/api/rankings")
def api_rankings():
    rankings = user_utils.get_rankings(limit=50)
    return jsonify({"ok": True, "rankings": rankings})


# =========================
# Run + Submit (Non Blocking ✅)
# =========================
@app.post("/api/run")
def api_run():
    """
    Run code with custom input (no judge).
    Frontend sends: { language, code, stdin }
    """
    try:
        payload = request.get_json(force=True)
        lang = payload.get("language") or payload.get("lang")
        code = payload.get("code", "")
        stdin = payload.get("stdin") or payload.get("input") or ""

        out = run_code(lang, code, stdin)
        return jsonify({"ok": True, "output": out, "verdict": "OK"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/submit")
def api_submit():
    """
    Non-blocking submit:
    - enqueue a job
    - return job_id immediately
    """
    try:
        ensure_workers()
        uid = require_user()
        user_utils.ensure_user_initialized(uid)

        payload = request.get_json(force=True)
        pid = int(payload.get("problem_id"))
        lang = payload.get("language") or payload.get("lang")
        code = payload.get("code", "")

        prob = find_problem_by_id(pid)
        if not prob:
            return jsonify({"ok": False, "error": "Problem not found"}), 404

        job_id = create_job({
            "user_id": uid,
            "problem_id": pid,
            "language": lang,
            "code": code,
        })

        # Save submission record as queued
        user_utils.save_submission(uid, {
            "problem_id": pid,
            "problem_name": prob.get("name", "Unknown Problem"),
            "verdict": "QUEUED",
            "lang": lang,
        })

        return jsonify({"ok": True, "job_id": job_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.get("/api/job/<job_id>")
def api_job(job_id: str):
    """
    Job polling endpoint
    """
    j = get_job(job_id)
    if not j:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    return jsonify({"ok": True, "status": j["status"], "result": j.get("result"), "error": j.get("error")})


# =========================
# Start bot + workers on import (gunicorn)
# =========================
ensure_workers()
start_bot_background()
