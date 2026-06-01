import json
import sqlite3
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Optional
from uuid import uuid4

from app.config.settings import settings


class JobService:
    def __init__(self) -> None:
        self._lock = RLock()
        settings.output_path.mkdir(parents=True, exist_ok=True)
        self._db_path = settings.output_path / "jobs.sqlite3"
        self._init_db()

    def create_job(self) -> dict[str, Any]:
        now = self._now()
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
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        job_id,
                        status,
                        progress,
                        output_file,
                        error,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job["job_id"],
                        job["status"],
                        json.dumps(job["progress"]),
                        job["output_file"],
                        job["error"],
                        job["created_at"],
                        job["updated_at"],
                    ),
                )
        return job

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
            self._write_job(job)

    def set_completed(self, job_id: str, output_file: str, total_rows: int) -> None:
        with self._lock:
            job = self._require_job(job_id)
            job["status"] = "completed"
            job["progress"]["current_category"] = None
            job["progress"]["collected_rows"] = total_rows
            job["progress"]["total_rows"] = total_rows
            job["output_file"] = output_file
            job["error"] = None
            self._write_job(job)

    def set_failed(self, job_id: str, error: str) -> None:
        self._update(job_id, status="failed", error=error)

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._row_to_job(row) if row else None

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            job = self._require_job(job_id)
            job.update(values)
            self._write_job(job)

    def _require_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        return job

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress TEXT NOT NULL,
                    output_file TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _write_job(self, job: dict[str, Any]) -> None:
        job["updated_at"] = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    progress = ?,
                    output_file = ?,
                    error = ?,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    job["status"],
                    json.dumps(job["progress"]),
                    job.get("output_file"),
                    job.get("error"),
                    job["updated_at"],
                    job["job_id"],
                ),
            )

    def _row_to_job(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "status": row["status"],
            "progress": json.loads(row["progress"]),
            "output_file": row["output_file"],
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


job_service = JobService()
