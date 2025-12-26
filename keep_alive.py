"""keep_alive.py

Extended Flask server:
 - Health endpoints: / , /ping
 - Telegram WebApp: /webapp  (serves a static SPA)
 - REST API: /api/*

This keeps your existing architecture intact:
 - Problem JSON format unchanged
 - MongoDB user db unchanged (user_utils.py)
 - Local code execution unchanged (handlers/submit.py)
 - Render free plan compatible (single web service, no Docker)
"""

from __future__ import annotations

import os
from threading import Thread
from flask import Flask, jsonify, request, send_from_directory

# Reuse existing logic
from utils.problem_utils import load_all_problems, find_problem_by_id
import user_utils
from handlers.submit import run_code
from utils.job_queue import create_job, get_job, start_worker_once


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")

app = Flask(__name__, static_folder=WEBAPP_DIR)


# ---------------------------
# Async job processor (in-memory)
# ---------------------------
def _process_submission_job(payload: dict):
    """Background worker: judge code using existing local runner."""
    pid = int(payload["problem_id"])
    lang = payload["lang"]
    code = payload.get("code","")
    uid = payload.get("user_id")

    prob = find_problem_by_id(pid)
    if not prob:
        return {"ok": False, "error": "Problem not found"}

    allow_unordered = bool(prob.get("allow_unordered_output", False))

    for tc in prob.get("test_cases", []):
        out = run_code(lang, code, tc.get("input",""))
        if isinstance(out, str) and out.startswith(("⚠️","⏰","❗")):
            return {"ok": False, "verdict": out}
        expected = (tc.get("output","") or "").strip()
        actual = (out or "").strip()
        if allow_unordered:
            expected_set = sorted([x.strip() for x in expected.splitlines() if x.strip()])
            actual_set = sorted([x.strip() for x in actual.splitlines() if x.strip()])
            if expected_set != actual_set:
                return {"ok": True, "status": "WA", "expected": expected, "actual": actual}
        else:
            if expected != actual:
                return {"ok": True, "status": "WA", "expected": expected, "actual": actual}
    # AC
    user_utils.update_user_score(uid, prob.get("points",1))
    user_utils.add_solved_problem(uid, pid)
    return {"ok": True, "status": "AC"}


# ---------------------------
# Basic health checks
# ---------------------------
@app.route("/")
def home():
    return "I am alive!", 200


@app.route("/ping")
def ping():
    return "pong", 200


# ---------------------------
# WebApp (static SPA)
# ---------------------------
@app.route("/webapp")
def webapp_index():
    """Serve the WebApp index.html"""
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.route("/webapp/<path:path>")
def webapp_assets(path: str):
    """Serve static assets (js/css/icons)."""
    return send_from_directory(WEBAPP_DIR, path)


# ---------------------------
# Helpers (auth)
# ---------------------------
def get_user_id_from_request() -> int | None:
    """WebApp requests should send Telegram user id.

    For local testing you can pass:
      - Header: X-User-Id
      - Query : ?user_id=

    In production, you can enhance with Telegram initData verification.
    """
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
        # For WebApp, Telegram will always have a user.
        # But to keep things smooth, return 401 with a clear message.
        raise ValueError("Missing user id")
    return uid


# ---------------------------
# API: Problems
# ---------------------------
@app.get("/api/problems")
def api_problems():
    problems = load_all_problems()
    # Keep original JSON structure but remove heavy test cases for list view
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
    # For safety, do not expose hidden testcases to client.
    # Only show sample or statement fields. Keep server-side testcases intact.
    safe_prob = dict(prob)
    safe_prob.pop("test_cases", None)
    return jsonify({"ok": True, "problem": safe_prob})


# ---------------------------
# API: Profile / History / Rankings
# ---------------------------
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
    # Public endpoint (no auth needed)
    rankings = user_utils.get_rankings(limit=50)
    return jsonify({"ok": True, "rankings": rankings})


# ---------------------------
# API: Run (custom input) & Submit (judge using hidden tests)
# ---------------------------
@app.post("/api/run")
def api_run():
    """Run code against custom input (no judging).
    This uses the same local runner as your bot.
    """
    try:
        payload = request.get_json(force=True)
        lang = payload.get("lang")
        code = payload.get("code", "")
        stdin = payload.get("input", "")

        # Reuse the same runner by invoking judge_code with a fake single test.
        # But better: call handlers.submit.run_code_async — it is internal.
        from handlers.submit import run_code
        out = run_code(lang, code, stdin)
        return jsonify({"ok": True, "output": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/submit")
def api_submit():
    """Judge submission against server-side tests.
    Logic is identical to Telegram bot submit workflow.
    """
    try:
        uid = require_user()
        user_utils.ensure_user_initialized(uid)

        payload = request.get_json(force=True)
        pid = int(payload.get("problem_id"))
        lang = payload.get("lang")
        code = payload.get("code", "")

        prob = find_problem_by_id(pid)
        if not prob:
            return jsonify({"ok": False, "error": "Problem not found"}), 404

        # Run judge (async function) inside sync Flask route
        import asyncio
        verdict = asyncio.run(judge_code(code, lang, prob))

        submission_record = {
            "problem_id": pid,
            "problem_name": prob.get("name", "Unknown Problem"),
            "verdict": verdict,
            "lang": lang,
        }
        user_utils.save_submission(uid, submission_record)
        user_utils.update_user_rating(uid, prob.get("level", "Easy"), pid, submission=submission_record, verdict=verdict)

        return jsonify({"ok": True, "verdict": verdict})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# ---------------------------
# Server runner
# ---------------------------
def run():
    print("[*] Starting Flask server (keep-alive + WebApp + API)...")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
