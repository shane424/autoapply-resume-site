from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Job(BaseModel):
    id: str                          # e.g. "remoteok_98234" or "wwr_slug"
    source: str                      # "remoteok" or "wwr"
    title: str
    company: str
    description: str
    apply_url: str
    location: Optional[str] = "Remote"
    salary: Optional[str] = None
    tags: list[str] = []
    posted_at: Optional[datetime] = None


class JobApplyStatus(BaseModel):
    job_id: str
    mode: str                        # "auto" or "semiauto"
    status: str                      # "pending" | "running" | "applied" | "failed" | "opened"
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
