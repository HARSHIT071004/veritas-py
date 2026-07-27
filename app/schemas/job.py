from pydantic import BaseModel
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Job(BaseModel):
    job_id: str
    video_id: str
    user_id: str
    status: JobStatus = JobStatus.queued
    result: Optional[dict] = None
    error: Optional[str] = None
    progress: str = ""
    created_at: Optional[str] = None


class JobSubmitResponse(BaseModel):
    success: bool
    job_id: Optional[str] = None
    status: str = "queued"
    error: Optional[str] = None


class JobResultResponse(BaseModel):
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
