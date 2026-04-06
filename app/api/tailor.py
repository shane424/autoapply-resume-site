import asyncio
import traceback
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.api.resume import get_active_resume
from app.api.jobs import get_job_by_id
from app.services.llm_client import tailor_resume
from app.services.resume_builder import build_resume
from app.models.resume import TailoredResumeContent

router = APIRouter()

# In-memory tailor task status
_tailor_status: dict[str, dict] = {}  # job_id -> {"status": ..., "result": ..., "error": ...}

# Total timeout for the entire tailor pipeline (LLM + PDF build), in seconds
TAILOR_TIMEOUT_SECS = 120


def _get_status(job_id: str) -> dict:
    return _tailor_status.get(job_id, {"status": "not_started"})


async def _run_tailor(job_id: str) -> None:
    _tailor_status[job_id] = {"status": "running", "result": None, "error": None}
    try:
        resume = get_active_resume()
        if not resume:
            raise ValueError("No resume uploaded.")
        job = get_job_by_id(job_id)
        if not job:
            raise ValueError("Job not found.")

        try:
            tailored = await asyncio.wait_for(
                tailor_resume(resume, job),
                timeout=TAILOR_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"LLM call timed out after {TAILOR_TIMEOUT_SECS}s. "
                "Check your API key and network connection."
            )

        tailored = build_resume(tailored, resume)
        _tailor_status[job_id] = {
            "status": "done",
            "result": tailored,
            "error": None,
            "keywords_added": tailored.keywords_added,
            "cover_letter": tailored.cover_letter,
        }
    except Exception as e:
        # Print full traceback to server console so you can diagnose locally
        traceback.print_exc()
        _tailor_status[job_id] = {"status": "failed", "result": None, "error": str(e)}


@router.post("/{job_id}")
async def trigger_tailor(job_id: str, background_tasks: BackgroundTasks):
    if not get_active_resume():
        raise HTTPException(status_code=400, detail="No resume uploaded. Upload a resume first.")
    if not get_job_by_id(job_id):
        raise HTTPException(status_code=404, detail="Job not found.")

    _tailor_status[job_id] = {"status": "pending", "result": None, "error": None}
    background_tasks.add_task(_run_tailor, job_id)
    return {"message": "Tailoring started.", "job_id": job_id}


@router.get("/{job_id}/status")
async def get_tailor_status(job_id: str):
    s = _get_status(job_id)
    return {
        "job_id": job_id,
        "status": s.get("status", "not_started"),
        "error": s.get("error"),
        "keywords_added": s.get("keywords_added", []),
        "cover_letter": s.get("cover_letter", ""),
    }
