
import threading
import queue
import time
import uuid

# In-memory async job queue (Render free friendly)
_job_q = queue.Queue()
_job_store = {}
_lock = threading.Lock()
_worker_started = False

def create_job(payload: dict) -> str:
    """Create a job and enqueue it. Returns job_id."""
    job_id = uuid.uuid4().hex
    with _lock:
        _job_store[job_id] = {
            "status": "queued",
            "created_at": time.time(),
            "updated_at": time.time(),
            "payload": payload,
            "result": None,
            "error": None,
        }
    _job_q.put(job_id)
    return job_id

def get_job(job_id: str):
    with _lock:
        return _job_store.get(job_id)

def update_job(job_id: str, **kwargs):
    with _lock:
        job = _job_store.get(job_id)
        if not job:
            return
        job.update(kwargs)
        job["updated_at"] = time.time()

def _worker_loop(process_fn):
    while True:
        job_id = _job_q.get()
        if job_id is None:
            break
        job = get_job(job_id)
        if not job:
            continue
        update_job(job_id, status="running")
        try:
            res = process_fn(job["payload"])
            update_job(job_id, status="done", result=res, error=None)
        except Exception as e:
            update_job(job_id, status="error", error=str(e))
        finally:
            _job_q.task_done()

def start_worker_once(process_fn):
    global _worker_started
    if _worker_started:
        return
    t = threading.Thread(target=_worker_loop, args=(process_fn,), daemon=True)
    t.start()
    _worker_started = True
