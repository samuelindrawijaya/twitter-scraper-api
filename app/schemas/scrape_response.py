from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel

JobStatus = Literal["queued", "running", "completed", "failed"]


class StartScrapeResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobProgress(BaseModel):
    current_category: Optional[str] = None
    collected_rows: int = 0
    total_rows: int = 0


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: JobProgress
    output_file: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PreviewQueryResponse(BaseModel):
    queries: dict[str, str]


class ErrorResponse(BaseModel):
    detail: Any
