import json
import re
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

from app.config import env_settings, load_app_settings
from app.models.job import Job
from app.models.resume import ParsedResume, TailoredResumeContent, ExperienceEntry, EducationEntry
from app.services.resume_parser import _normalize_company

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))


def _render_prompt(template_name: str, **kwargs) -> str:
    tmpl = _jinja_env.get_template(template_name)
    return tmpl.render(**kwargs)


async def _call_claude(prompt: str, model: str) -> str:
    import anthropic
    # 90s timeout per call — two calls = max ~3 min total before we give up
    client = anthropic.AsyncAnthropic(
        api_key=env_settings.anthropic_api_key,
        timeout=90.0,
    )
    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def _call_ollama(prompt: str, model: str, base_url: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        res.raise_for_status()
        return res.json()["response"]


async def _complete(prompt: str) -> str:
    settings = load_app_settings()
    llm = settings.llm
    if llm.provider == "claude":
        return await _call_claude(prompt, llm.claude_model)
    else:
        return await _call_ollama(prompt, llm.ollama_model, llm.ollama_base_url)


def _parse_json_response(text: str) -> dict:
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


async def extract_keywords(job: Job) -> list[str]:
    prompt = _render_prompt("extract_keywords.j2", job=job)
    response = await _complete(prompt)
    try:
        keywords = _parse_json_response(response)
        if isinstance(keywords, list):
            return [str(k) for k in keywords]
    except Exception:
        pass
    return []


async def tailor_resume(resume: ParsedResume, job: Job) -> TailoredResumeContent:
    # Single LLM call — keywords extracted inline, structured resume replaces raw text
    prompt = _render_prompt(
        "tailor_resume.j2",
        resume=resume,
        job=job,
        secret_instructions=job.secret_instructions,
    )
    response = await _complete(prompt)
    data = _parse_json_response(response)

    experience = [
        ExperienceEntry(
            title=e.get("title", ""),
            company=_normalize_company(e.get("company", "")),
            dates=e.get("dates", ""),
            bullets=e.get("bullets", []),
        )
        for e in (data.get("experience") or [])
    ]
    education = [
        EducationEntry(
            degree=e.get("degree", ""),
            school=e.get("school", ""),
            year=str(e.get("year", "")),
        )
        for e in (data.get("education") or [])
    ]
    # Strip any skills the LLM invented that aren't in the original resume.
    # Build a lowercase token set from original skills + all bullet text.
    original_tokens = set()
    for s in resume.skills:
        original_tokens.update(re.findall(r"[a-z0-9#+.\-]+", s.lower()))
    for exp in resume.experience:
        for b in exp.bullets:
            original_tokens.update(re.findall(r"[a-z0-9#+.\-]+", b.lower()))
    original_tokens.update(re.findall(r"[a-z0-9#+.\-]+", resume.raw_text.lower()))

    clean_skills = []
    for skill in data.get("skills", []):
        skill_tokens = set(re.findall(r"[a-z0-9#+.\-]+", skill.lower()))
        if skill_tokens & original_tokens:
            clean_skills.append(skill)
        else:
            print(f"[llm_client] Removed hallucinated skill: {skill!r}")

    return TailoredResumeContent(
        job_id=job.id,
        summary=data.get("summary", ""),
        experience=experience,
        skills=clean_skills,
        education=education,
        keywords_added=data.get("keywords_added", []),
        cover_letter=data.get("cover_letter", ""),
    )
