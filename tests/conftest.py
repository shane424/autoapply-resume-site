"""
Shared fixtures and helpers for tailor integration tests.
All test_tailor_*.py files use these automatically via pytest conftest discovery.
"""

import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pages"

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

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_or_load(url: str, fixture_name: str) -> str:
    """Load fixture HTML from disk, or fetch live and save it."""
    dest = FIXTURES_DIR / fixture_name
    if dest.exists() and dest.stat().st_size > 1000:
        return dest.read_text(encoding="utf-8", errors="replace")
    import httpx
    resp = httpx.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    print(f"\n[fixture] Saved {fixture_name} ({len(resp.content):,} bytes)")
    return resp.text


def ats_score(job_description: str, resume_text: str, top_n: int = 40) -> dict:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9#+.\-]{1,}\b", job_description.lower())
    freq = Counter(t for t in tokens if t not in _STOP)
    words = job_description.lower().split()
    bigrams = [
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if words[i] not in _STOP and words[i+1] not in _STOP
        and re.match(r"[a-z]", words[i]) and re.match(r"[a-z]", words[i+1])
        and len(words[i]) > 2 and len(words[i+1]) > 2
    ]
    freq.update(Counter(bigrams))
    top_keywords = [kw for kw, _ in freq.most_common(top_n)]
    resume_lower = resume_text.lower()
    matched = [kw for kw in top_keywords if kw in resume_lower]
    missing = [kw for kw in top_keywords if kw not in resume_lower]
    score = round(len(matched) / len(top_keywords) * 100, 1) if top_keywords else 0.0
    return {"score": score, "matched": matched, "missing": missing, "total_keywords": top_keywords}


def resume_to_text(tailored) -> str:
    parts = [tailored.summary, " ".join(tailored.skills)]
    for exp in tailored.experience:
        parts += [exp.title, exp.company] + exp.bullets
    for edu in tailored.education:
        parts += [edu.degree, edu.school]
    if tailored.cover_letter:
        parts.append(tailored.cover_letter)
    return " ".join(parts)


def load_dotenv_value(key: str) -> str:
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[-1].strip().strip('"').strip("'")
    return ""


def run_tailor_pipeline(job_dict: dict, parsed_resume, job_id: str) -> object:
    """Run LLM tailor + build_resume. Returns TailoredResumeContent."""
    from app.models.job import Job
    from app.services.llm_client import tailor_resume
    from app.services.resume_builder import build_resume

    job = Job(
        id=job_id,
        source="test",
        title=job_dict["title"],
        company=job_dict["company"],
        description=job_dict["description"],
        apply_url=job_dict.get("url", ""),
        location="Remote",
    )
    result = asyncio.run(tailor_resume(parsed_resume, job))
    return build_resume(result, parsed_resume)


def print_ats_report(job_dict: dict, tailored, capsys) -> dict:
    result = ats_score(job_dict["description"], resume_to_text(tailored))
    title = tailored.experience[0].title if tailored.experience else "Role"
    with capsys.disabled():
        print(f"\n{'='*62}")
        print(f"  ATS KEYWORD SCORE  |  {job_dict['company']} — {title}")
        print(f"{'='*62}")
        print(f"  Score : {result['score']:.1f}%  ({len(result['matched'])}/{len(result['total_keywords'])} keywords)")
        print(f"\n  Matched  : {', '.join(result['matched'][:25])}")
        print(f"\n  Missing  : {', '.join(result['missing'][:15])}")
        print(f"\n  LLM added: {', '.join(tailored.keywords_added)}")
        print(f"\n  Summary  : {tailored.summary[:250]}...")
        print(f"{'='*62}\n")
    return result


@pytest.fixture(scope="module")
def parsed_resume():
    resume_path = os.getenv("RESUME_PATH") or load_dotenv_value("RESUME_PATH")
    if not resume_path:
        pytest.skip("Set RESUME_PATH in .env: RESUME_PATH=C:\\path\\to\\resume.pdf")
    from app.services.resume_parser import parse_resume
    return parse_resume(resume_path)


@pytest.fixture(scope="module")
def api_key():
    key = os.getenv("ANTHROPIC_API_KEY") or load_dotenv_value("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key
