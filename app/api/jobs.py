from fastapi import APIRouter, HTTPException
from app.models.job import Job
from app.services.scraper import scrape_all
from app.config import load_app_settings

router = APIRouter()

# In-memory job cache (single-user session)
_job_cache: list[Job] = []
_job_index: dict[str, Job] = {}


def _rebuild_index(jobs: list[Job]) -> None:
    global _job_index
    _job_index = {j.id: j for j in jobs}


@router.get("", response_model=list[Job])
async def list_jobs():
    return _job_cache


@router.post("/refresh", response_model=list[Job])
async def refresh_jobs():
    global _job_cache
    settings = load_app_settings()
    try:
        jobs = await scrape_all(settings.filters)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraping failed: {e}")
    _job_cache = jobs
    _rebuild_index(jobs)
    return jobs


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str):
    job = _job_index.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def get_job_by_id(job_id: str) -> Job | None:
    return _job_index.get(job_id)
