import asyncio
import traceback
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.api.resume import get_active_resume
from app.api.jobs import get_job_by_id
from app.services.llm_client import tailor_resume
from app.services.resume_builder import build_resume
from app.services.resume_parser import parse_resume_text
from app.services.scraper import _enrich_job
from app.models.job import Job
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


# ── Extension inline endpoint ─────────────────────────────────────────────────

class InlineTailorRequest(BaseModel):
    resume_text: str
    job_title: str = ""
    job_company: str = ""
    job_description: str = ""
    job_url: str = ""


@router.post("/inline")
async def tailor_inline(body: InlineTailorRequest):
    """
    Called by the Chrome extension. Accepts raw resume text + job data,
    runs the full tailor pipeline, and returns the result.
    The PDF is written to the configured output_dir (Shane's Documents folder).
    """
    if not body.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text is required.")
    if not body.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required.")

    job_id = f"ext_{uuid.uuid4().hex[:8]}"
    job = Job(
        id=job_id,
        source="extension",
        title=body.job_title or "Unknown Position",
        company=body.job_company or "Unknown Company",
        description=body.job_description,
        apply_url=body.job_url or "",
        location="",
    )
    job = _enrich_job(job)  # secret detection, location, us_remote

    resume = parse_resume_text(body.resume_text)

    try:
        tailored = await asyncio.wait_for(
            tailor_resume(resume, job),
            timeout=TAILOR_TIMEOUT_SECS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"LLM timed out after {TAILOR_TIMEOUT_SECS}s. Check your API key.",
        )

    tailored = build_resume(tailored, resume)

    # Build a plain-text version of the tailored resume for the extension to display/copy
    lines = []
    if resume.contact.get("name"):
        lines.append(resume.contact["name"])
    contact_parts = [v for k, v in resume.contact.items() if k != "name" and v]
    if contact_parts:
        lines.append(" · ".join(contact_parts))
    lines.append("")
    if tailored.summary:
        lines += ["SUMMARY", tailored.summary, ""]
    if tailored.skills:
        lines += ["SKILLS", ", ".join(tailored.skills), ""]
    if tailored.experience:
        lines.append("EXPERIENCE")
        for exp in tailored.experience:
            lines.append(f"{exp.title} | {exp.company} | {exp.dates}")
            for b in exp.bullets:
                lines.append(f"  • {b}")
            lines.append("")
    if tailored.education:
        lines.append("EDUCATION")
        for edu in tailored.education:
            lines.append(f"{edu.degree} — {edu.school} ({edu.year})")

    return {
        "success": True,
        "job_id": job_id,
        "resume_text": "\n".join(lines),
        "cover_letter": tailored.cover_letter,
        "keywords_added": tailored.keywords_added,
        "secret_instructions": job.secret_instructions,
        "pdf_path": tailored.pdf_path,
        "docx_path": tailored.docx_path,
        "match_score": min(100, 50 + len(tailored.keywords_added) * 5),
    }
