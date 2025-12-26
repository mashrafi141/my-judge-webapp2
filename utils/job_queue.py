"""
utils/job_queue.py

In-memory async job queue for judging submissions.
✅ Fixed: start_worker_once now supports multiple workers safely.

- create_job(payload) -> job_id
- get_job(job_id) -> job dict
- start_worker_once(process_fn, workers=3) -> starts background workers (only once)
"""

from __future__ import annotations

import time
import uuid
import queue
import threading
from typing import Any, Callable, Dict, Optional


# ---------------------------
# In-memory job store + queue
# ---------------------------
_jobs: Dict[str, Dict[str, Any]] = {}
_job_queue: "queue.Queue[str]" = queue.Queue()

_worker_started = False
_worker_lock = threading.Lock()


# ---------------------------
# Public API
# ---------------------------
def create_job(payload: dict) -> str:
    """
    Enqueue a job and return its id
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "payload": payload,
        "result": None,
        "error": None,
        "created_at": time.time(),
    }
    _job_queue.put(job_id)
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def start_worker_once(process_fn: Callable[[dict], dict], workers: int = 3):
    """
    ✅ Starts job worker threads only once.
    Backward compatible:
      start_worker_once(fn)          -> uses default workers=3
      start_worker_once(fn, workers=2)
    """
    global _worker_started

    # ✅ Thread-safe: prevent multiple starts
    with _worker_lock:
        if _worker_started:
            return

        # Workers sanity (Render free plan friendly)
        if not isinstance(workers, int) or workers < 1:
            workers = 1
        if workers > 4:  # safe cap
            workers = 4

        for i in range(workers):
            t = threading.Thread(
                target=_worker_loop,
                args=(process_fn,),
                daemon=True,
                name=f"job-worker-{i+1}"
            )
            t.start()

        _worker_started = True


# ---------------------------
# Worker loop
# ---------------------------
def _worker_loop(process_fn: Callable[[dict], dict]):
    """
    Continuously processes queued jobs.
    """
    while True:
        job_id = _job_queue.get()
        job = _jobs.get(job_id)
        if not job:
            _job_queue.task_done()
            continue

        job["status"] = "running"
        try:
            result = process_fn(job["payload"])
            job["result"] = result
            job["status"] = "done"
        except Exception as e:
            job["error"] = str(e)
            job["status"] = "error"
        finally:
            _job_queue.task_done()
