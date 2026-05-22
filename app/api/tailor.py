import asyncio
import re
import traceback
import uuid
from collections import Counter
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.api.resume import get_active_resume, get_career_pool
from app.api.jobs import get_job_by_id
from app.services.llm_client import tailor_resume
from app.services.resume_builder import build_resume
from app.services.resume_parser import parse_resume_text
from app.services.scraper import _enrich_job
from app.models.job import Job
from app.models.resume import TailoredResumeContent

router = APIRouter()

_STOP = {
    "the","a","an","in","on","at","to","for","of","and","or","is","are","will",
    "with","this","that","we","you","your","our","all","be","has","have","do",
    "not","can","may","must","should","would","could","been","they","their",
    "from","by","as","but","if","it","its","into","also","about","more","when",
    "who","what","how","any","each","both","other","than","then","so","up",
    "out","were","was","had","did","just","like","some","over","use","used",
    "using","work","working","team","able","help","include","including",
    "across","within","through","experience","years","year","strong",
    "role","position","job","opportunity","looking","great","good","well",
    "new","high","key","make","build","ensure","provide","support","manage",
    "part","play","based","day","per","ability","skills","skill","knowledge",
}


def _ats_score(job_description: str, resume_text: str, top_n: int = 50) -> tuple[int, list[str], list[str]]:
    """Return (score 0-100, matched keywords, missing keywords) for the top_n JD keywords."""
    # Normalize common aliases so postgres == postgresql, etc.
    _aliases = {
        "postgresql": "postgres", "pg": "postgres",
        "javascript": "js", "typescript": "ts",
        "kubernetes": "k8s", "amazon": "aws",
        "github": "git", "gitlab": "git",
    }
    def _norm(w: str) -> str:
        return _aliases.get(w, w)

    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9#+.\-]{1,}\b", job_description.lower())
    freq = Counter(_norm(t) for t in tokens if t not in _STOP)
    words = [_norm(w) for w in job_description.lower().split()]
    bigrams = [
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if words[i] not in _STOP and words[i+1] not in _STOP
        and re.match(r"[a-z]", words[i]) and re.match(r"[a-z]", words[i+1])
        and len(words[i]) > 2 and len(words[i+1]) > 2
    ]
    freq.update(Counter(bigrams))
    top_kw = [kw for kw, _ in freq.most_common(top_n)]
    if not top_kw:
        return 0, [], []
    resume_lower = resume_text.lower()
    # Normalize resume text the same way
    for orig, norm in _aliases.items():
        resume_lower = resume_lower.replace(orig, norm)
    matched  = [kw for kw in top_kw if kw in resume_lower]
    missing  = [kw for kw in top_kw if kw not in resume_lower]
    score = round(len(matched) / len(top_kw) * 100)
    return score, matched, missing

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
                tailor_resume(resume, job, career_pool=get_career_pool()),
                timeout=TAILOR_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"LLM call timed out after {TAILOR_TIMEOUT_SECS}s. "
                "Check your API key and network connection."
            )

        tailored = build_resume(tailored, resume, job_company=job.company)
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


# ── Extension inline endpoint (must be before /{job_id} to avoid route shadowing) ──

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
    If resume_text is empty, falls back to the resume uploaded via the dashboard.
    """
    if not body.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required.")

    # Use pasted text if provided, otherwise fall back to server-side uploaded resume
    if body.resume_text.strip():
        resume = parse_resume_text(body.resume_text)
    else:
        resume = get_active_resume()
        if not resume:
            raise HTTPException(
                status_code=400,
                detail="No resume found. Upload one at http://localhost:8000 or paste it in the extension popup."
            )

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
    job = _enrich_job(job)

    # Always pass career pool if available — gives LLM more bullets to work with
    career_pool = get_career_pool()

    try:
        tailored = await asyncio.wait_for(
            tailor_resume(resume, job, career_pool=career_pool),
            timeout=TAILOR_TIMEOUT_SECS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"LLM timed out after {TAILOR_TIMEOUT_SECS}s. Check your API key.",
        )

    tailored = build_resume(tailored, resume, job_company=job.company)

    # Build plain-text resume for extension display and ATS scoring
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

    resume_text = "\n".join(lines)
    match_score, kw_matched, kw_missing = _ats_score(job.description, resume_text)

    return {
        "success": True,
        "job_id": job_id,
        "resume_text": resume_text,
        "cover_letter": tailored.cover_letter,
        "keywords_added": tailored.keywords_added,
        "secret_instructions": job.secret_instructions,
        "pdf_path": tailored.pdf_path,
        "docx_path": tailored.docx_path,
        "match_score": match_score,
        "keywords_matched": kw_matched,
        "keywords_missing": kw_missing,
    }


# ── Dashboard / background tailor endpoints ───────────────────────────────────

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
