from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.api.jobs import get_job_by_id
from app.services.apply_semiauto import open_in_browser
from app.services.apply_playwright import auto_apply
from app.config import load_app_settings

router = APIRouter()

_apply_status: dict[str, dict] = {}  # job_id -> {status, mode, error}


class ApplyRequest(BaseModel):
    mode: str = "semiauto"   # "auto" or "semiauto"


async def _run_auto_apply(job_id: str) -> None:
    _apply_status[job_id]["status"] = "running"
    try:
        job = get_job_by_id(job_id)
        if not job:
            raise ValueError("Job not found.")
        settings = load_app_settings()
        await auto_apply(job, settings.user_profile)
        _apply_status[job_id]["status"] = "applied"
    except Exception as e:
        _apply_status[job_id]["status"] = "failed"
        _apply_status[job_id]["error"] = str(e)


@router.post("/{job_id}")
async def apply_to_job(job_id: str, req: ApplyRequest, background_tasks: BackgroundTasks):
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if req.mode == "semiauto":
        try:
            open_in_browser(job)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to open browser: {e}")
        _apply_status[job_id] = {"status": "opened", "mode": "semiauto", "error": None}
        return {"message": "Job URL opened in your browser.", "status": "opened"}

    # Full auto mode
    _apply_status[job_id] = {"status": "pending", "mode": "auto", "error": None}
    background_tasks.add_task(_run_auto_apply, job_id)
    return {"message": "Auto-apply started.", "status": "pending"}


@router.get("/{job_id}/status")
async def get_apply_status(job_id: str):
    s = _apply_status.get(job_id, {"status": "not_started", "mode": None, "error": None})
    return {"job_id": job_id, **s}
