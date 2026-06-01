from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional
from uuid import uuid4


class JobService:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def create_job(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        job_id = str(uuid4())
        job = {
            "job_id": job_id,
            "status": "queued",
            "progress": {"current_category": None, "collected_rows": 0, "total_rows": 0},
            "output_file": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._jobs[job_id] = job
        return deepcopy(job)

    def set_running(self, job_id: str) -> None:
        self._update(job_id, status="running", error=None)

    def update_progress(
        self,
        job_id: str,
        current_category: Optional[str] = None,
        collected_rows: Optional[int] = None,
        total_rows: Optional[int] = None,
    ) -> None:
        with self._lock:
            job = self._require_job(job_id)
            progress = job["progress"]
            if current_category is not None:
                progress["current_category"] = current_category
            if collected_rows is not None:
                progress["collected_rows"] = collected_rows
            if total_rows is not None:
                progress["total_rows"] = total_rows
            job["updated_at"] = datetime.now(timezone.utc)

    def set_completed(self, job_id: str, output_file: str, total_rows: int) -> None:
        with self._lock:
            job = self._require_job(job_id)
            job["status"] = "completed"
            job["progress"]["current_category"] = None
            job["progress"]["collected_rows"] = total_rows
            job["progress"]["total_rows"] = total_rows
            job["output_file"] = output_file
            job["error"] = None
            job["updated_at"] = datetime.now(timezone.utc)

    def set_failed(self, job_id: str, error: str) -> None:
        self._update(job_id, status="failed", error=error)

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            job = self._require_job(job_id)
            job.update(values)
            job["updated_at"] = datetime.now(timezone.utc)

    def _require_job(self, job_id: str) -> dict[str, Any]:
        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")
        return self._jobs[job_id]


job_service = JobService()
