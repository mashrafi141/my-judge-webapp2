"""
keep_alive.py (FINAL - Render + Gunicorn + Telegram WebApp + Bot Thread)

Features:
- Health endpoints: / , /ping
- Telegram WebApp SPA: /webapp + /webapp/<assets>
- REST API: /api/*
- Non-blocking submissions: background job queue + polling
- Telegram bot runs in background thread (works with gunicorn)
- Problems sorted by ID ascending
- MongoDB user db logic unchanged (user_utils.py)
- Problem JSON format unchanged
- Render free plan compatible (single web service, no Docker)
"""

from __future__ import annotations

import os
import threading
from flask import Flask, jsonify, request, send_from_directory

# Reuse existing logic
from utils.problem_utils import load_all_problems, find_problem_by_id
import user_utils

from handlers.submit import run_code  # existing local runner

# Job queue utilities (your existing module)
from utils.job_queue import create_job, get_job, start_worker_once


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")

app = Flask(__name__, static_folder=WEBAPP_DIR)

# =====================================
# ✅ Background worker: judge submissions
# =====================================
def _process_submission_job(payload: dict):
    """
    Judge code using existing runner + hidden testcases.
    Same logic as telegram submit.
    Runs in background queue worker (non-blocking).
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

        # runtime error/timeouts (your runner returns ⚠️ / ⏰ etc)
        if isinstance(out, str) and out.startswith(("⚠️", "⏰", "❗")):
            return {"ok": False, "verdict": out}

        expected = (tc.get("output", "") or "").strip()
        actual = (out or "").strip()

        if allow_unordered:
            expected_set = sorted([x.strip() for x in expected.splitlines() if x.strip()])
            actual_set = sorted([x.strip() for x in actual.splitlines() if x.strip()])
            if expected_set != actual_set:
                return {"ok": True, "verdict": "WA", "expected": expected, "actual": actual}
        else:
            if expected != actual:
                return {"ok": True, "verdict": "WA", "expected": expected, "actual": actual}

    # ✅ Accepted
    user_utils.update_user_score(uid, prob.get("points", 1))
    user_utils.add_solved_problem(uid, pid)

    return {"ok": True, "verdict": "AC"}


# =====================================
# ✅ Ensure workers start only once
# =====================================
_WORKER_STARTED = False

def ensure_workers():
    """
    Starts job queue worker threads once.
    IMPORTANT: use positional arguments for compatibility
    because start_worker_once signature may differ.
    """
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return

    # ✅ FIX: don't use num_workers kwarg (your error)
    start_worker_once(_process_submission_job, 3)

    _WORKER_STARTED = True
    print("🚀 Judge workers started!")


# =====================================
# ✅ Telegram bot background thread
# =====================================
_BOT_STARTED = False

def start_bot_background():
    """
    Starts Telegram bot polling in background thread.
    Requires my_bot_runner.py with run_bot().
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


# =====================================
# ✅ Basic health checks
# =====================================
@app.route("/")
def home():
    return "I am alive!", 200

@app.route("/ping")
def ping():
    return "pong", 200


# =====================================
# ✅ WebApp (static SPA)
# =====================================
@app.route("/webapp")
def webapp_index():
    return send_from_directory(WEBAPP_DIR, "index.html")

@app.route("/webapp/<path:path>")
def webapp_assets(path: str):
    return send_from_directory(WEBAPP_DIR, path)


# =====================================
# ✅ Helpers (auth)
# =====================================
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


# =====================================
# ✅ API: Problems (sorted by id)
# =====================================
@app.get("/api/problems")
def api_problems():
    problems = load_all_problems()
    problems.sort(key=lambda x: int(x.get("id", 0)))  # ✅ ascending

    lite = []
    for p in problems:
        pp = dict(p)
        pp.pop("test_cases", None)  # remove hidden testcases
        lite.append(pp)

    return jsonify({"ok": True, "problems": lite})


@app.get("/api/problem/<int:pid>")
def api_problem(pid: int):
    prob = find_problem_by_id(pid)
    if not prob:
        return jsonify({"ok": False, "error": "Problem not found"}), 404

    safe_prob = dict(prob)
    safe_prob.pop("test_cases", None)  # don't expose hidden testcases
    return jsonify({"ok": True, "problem": safe_prob})


# =====================================
# ✅ API: Profile / History / Rankings
# =====================================
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


# =====================================
# ✅ API: Run (custom input)
# =====================================
@app.post("/api/run")
def api_run():
    """
    Frontend sends:
      { user_id, language, code, stdin }
    Support also old keys:
      { lang, input }
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


# =====================================
# ✅ API: Submit (non-blocking queue)
# =====================================
@app.post("/api/submit")
def api_submit():
    """
    Non-blocking submit:
    - enqueue job
    - return job_id immediately
    Frontend will poll /api/job/<id>
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

        # ✅ enqueue job
        job_id = create_job({
            "user_id": uid,
            "problem_id": pid,
            "language": lang,
            "code": code,
        })

        # save queued submission in DB
        user_utils.save_submission(uid, {
            "problem_id": pid,
            "problem_name": prob.get("name", prob.get("title", "Unknown Problem")),
            "verdict": "QUEUED",
            "lang": lang,
        })

        return jsonify({"ok": True, "job_id": job_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# =====================================
# ✅ API: Job polling
# =====================================
@app.get("/api/job/<job_id>")
def api_job(job_id: str):
    j = get_job(job_id)
    if not j:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    return jsonify({
        "ok": True,
        "status": j["status"],
        "result": j.get("result"),
        "error": j.get("error")
    })


# =====================================
# ✅ Run these when keep_alive is imported (gunicorn)
# =====================================
ensure_workers()
start_bot_background()
