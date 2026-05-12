"""
Integration test: tailor Shane's resume for the Axios Greenhouse job posting,
then score the result with a simple ATS keyword screener.

Requirements:
  - ANTHROPIC_API_KEY set in .env or environment
  - RESUME_PATH env var pointing to your resume PDF or DOCX

The Axios Greenhouse page is fetched live on first run and saved as a fixture
so subsequent runs work offline.

Run (from repo root, venv active):
  RESUME_PATH="C:/Users/Shane/Documents/Resume/Shane_Smith.pdf" pytest tests/test_tailor_axios.py -v -s

  Or on Windows PowerShell:
  $env:RESUME_PATH="C:\\Users\\Shane\\Documents\\Resume\\Shane_Smith.pdf"
  pytest tests/test_tailor_axios.py -v -s
"""

import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

AXIOS_URL = "https://job-boards.greenhouse.io/axios/jobs/7818788"
FIXTURE_HTML = Path(__file__).parent / "fixtures" / "pages" / "axios_greenhouse.html"
OUTPUT_DIR = Path(__file__).parent / "fixtures" / "pages"

# ---------------------------------------------------------------------------
# Page fetcher / loader
# ---------------------------------------------------------------------------

def _fetch_or_load_axios() -> str:
    if FIXTURE_HTML.exists() and FIXTURE_HTML.stat().st_size > 1000:
        return FIXTURE_HTML.read_text(encoding="utf-8", errors="replace")

    import httpx
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = httpx.get(AXIOS_URL, headers=headers, timeout=20, follow_redirects=True)
    resp.raise_for_status()
    FIXTURE_HTML.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_HTML.write_bytes(resp.content)
    print(f"\n[fixture] Saved Axios page → {FIXTURE_HTML}")
    return resp.text


# ---------------------------------------------------------------------------
# Greenhouse HTML parser
# ---------------------------------------------------------------------------

def _text(soup, *selectors) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el.get_text(" ", strip=True)
    return ""


def _parse_greenhouse(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(
        soup,
        ".app-title", "h1.job-title", ".posting-headline h2",
        "h1", "h2",
    )
    desc = _text(
        soup,
        "#content", ".content", ".job__description",
        "[class*='description']", "article", "main",
    )
    return {"title": title or "Software Engineer", "company": "Axios", "description": desc}


# ---------------------------------------------------------------------------
# ATS keyword screener (pure Python, no external service)
# ---------------------------------------------------------------------------

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


def ats_score(job_description: str, resume_text: str, top_n: int = 40) -> dict:
    """Score how well resume_text covers the key terms in job_description."""
    # Extract candidate terms: 2+ char alpha tokens, not stop words
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9#+.\-]{1,}\b", job_description.lower())
    freq = Counter(t for t in tokens if t not in _STOP)

    # Also add multi-word phrases (bigrams) that look like tech terms
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

    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "total_keywords": top_keywords,
    }


def _resume_to_text(tailored) -> str:
    """Flatten a TailoredResumeContent into a single string for scoring."""
    parts = [tailored.summary, " ".join(tailored.skills)]
    for exp in tailored.experience:
        parts.append(exp.title)
        parts.append(exp.company)
        parts.extend(exp.bullets)
    for edu in tailored.education:
        parts.append(edu.degree)
        parts.append(edu.school)
    if tailored.cover_letter:
        parts.append(tailored.cover_letter)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Fixtures (module-scoped so the LLM is called once for all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def axios_job():
    try:
        html = _fetch_or_load_axios()
    except Exception as e:
        pytest.skip(f"Could not load Axios page: {e}")
    job = _parse_greenhouse(html)
    assert job["description"], (
        "Greenhouse page returned no description text. "
        "The page may require JavaScript rendering. "
        "Save it manually: open the URL in Chrome → Ctrl+S → "
        f"save to {FIXTURE_HTML}"
    )
    return job


@pytest.fixture(scope="module")
def parsed_resume():
    resume_path = os.getenv("RESUME_PATH") or _load_dotenv_value("RESUME_PATH")
    if not resume_path:
        pytest.skip(
            "Set RESUME_PATH in .env or environment.\n"
            "  .env:        RESUME_PATH=C:\\path\\to\\resume.pdf\n"
            "  PowerShell:  $env:RESUME_PATH='C:\\path\\to\\resume.pdf'"
        )
    from app.services.resume_parser import parse_resume
    return parse_resume(resume_path)


@pytest.fixture(scope="module")
def tailored_result(axios_job, parsed_resume):
    api_key = os.getenv("ANTHROPIC_API_KEY") or _load_dotenv_key()
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set — cannot call tailor pipeline")

    from app.models.job import Job
    from app.services.llm_client import tailor_resume

    job = Job(
        id="axios_7818788",
        source="greenhouse",
        title=axios_job["title"],
        company=axios_job["company"],
        description=axios_job["description"],
        apply_url=AXIOS_URL,
        location="Remote",
    )

    result = asyncio.run(tailor_resume(parsed_resume, job))

    # Build PDF + DOCX (same step the API runs after the LLM call)
    from app.services.resume_builder import build_resume
    result = build_resume(result, parsed_resume)

    # Save JSON output for inspection
    out = OUTPUT_DIR / "axios_tailored_output.json"
    out.write_text(
        json.dumps(result.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n[output] Tailored resume saved → {out}")
    if result.pdf_path:
        print(f"[output] PDF → {result.pdf_path}")
    if result.docx_path:
        print(f"[output] DOCX → {result.docx_path}")
    return result


def _load_dotenv_value(key: str) -> str:
    """Read any key from .env without requiring python-dotenv."""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[-1].strip().strip('"').strip("'")
    return ""


def _load_dotenv_key() -> str:
    return _load_dotenv_value("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_axios_page_has_title(axios_job):
    assert axios_job["title"], "Could not extract job title from Greenhouse page"


def test_axios_page_has_description(axios_job):
    assert len(axios_job["description"]) > 200, (
        f"Description too short ({len(axios_job['description'])} chars). "
        "Page may need JS rendering — save manually from Chrome."
    )


def test_tailor_returns_summary(tailored_result):
    assert tailored_result.summary, "Tailored resume has no summary"
    assert len(tailored_result.summary) > 50


def test_tailor_returns_experience(tailored_result):
    assert len(tailored_result.experience) > 0, "Tailored resume has no experience entries"
    for exp in tailored_result.experience:
        assert exp.title
        assert exp.company
        assert len(exp.bullets) > 0


def test_tailor_returns_skills(tailored_result):
    assert len(tailored_result.skills) >= 5, "Expected at least 5 skills in tailored resume"


def test_tailor_returns_keywords(tailored_result):
    assert len(tailored_result.keywords_added) > 0, "LLM reported no keywords added"


def test_tailor_no_invented_companies(parsed_resume, tailored_result):
    """All companies in tailored resume must exist in the original parsed resume."""
    original_companies = {exp.company.lower() for exp in parsed_resume.experience}
    for exp in tailored_result.experience:
        assert exp.company.lower() in original_companies, (
            f"Tailored resume contains invented company: '{exp.company}'"
        )


def test_ats_score(axios_job, tailored_result, capsys):
    resume_text = _resume_to_text(tailored_result)
    result = ats_score(axios_job["description"], resume_text)

    with capsys.disabled():
        print(f"\n{'='*62}")
        print(f"  ATS KEYWORD SCORE  |  Axios — {tailored_result.experience[0].title if tailored_result.experience else 'Role'}")
        print(f"{'='*62}")
        print(f"  Score : {result['score']:.1f}%  ({len(result['matched'])}/{len(result['total_keywords'])} keywords matched)")
        print(f"\n  Matched  ({len(result['matched'])}): {', '.join(result['matched'][:20])}")
        if result["matched"][20:]:
            print(f"           {', '.join(result['matched'][20:])}")
        print(f"\n  Missing  ({len(result['missing'])}): {', '.join(result['missing'][:20])}")
        if result["missing"][20:]:
            print(f"           {', '.join(result['missing'][20:])}")
        print(f"\n  Keywords LLM added: {', '.join(tailored_result.keywords_added)}")
        print(f"{'='*62}")
        print(f"\n  Tailored Summary:\n  {tailored_result.summary[:300]}...")
        print(f"{'='*62}\n")

    # Threshold: at least 35% keyword coverage (generous — resume can't stuff every keyword)
    assert result["score"] >= 35, (
        f"ATS keyword coverage too low: {result['score']:.1f}%. "
        f"Missing: {', '.join(result['missing'][:10])}"
    )


def test_cover_letter_present(tailored_result):
    assert tailored_result.cover_letter, "Expected a cover letter in the tailored output"
    assert len(tailored_result.cover_letter) > 100


def test_pdf_was_built(tailored_result, capsys):
    assert tailored_result.pdf_path, "pdf_path is None — build_resume() did not run or failed"
    pdf = Path(tailored_result.pdf_path)
    assert pdf.exists(), f"PDF file not found at {tailored_result.pdf_path}"
    assert pdf.stat().st_size > 2_000, f"PDF looks too small ({pdf.stat().st_size} bytes)"
    assert pdf.read_bytes()[:4] == b"%PDF", "File does not appear to be a valid PDF"
    with capsys.disabled():
        print(f"\n  PDF: {tailored_result.pdf_path}  ({pdf.stat().st_size:,} bytes)")
        print(f"  DOCX: {tailored_result.docx_path}")


def test_titles_were_reframed(tailored_result, parsed_resume):
    """LLM should reframe obscure titles to industry-standard equivalents."""
    obscure = {"hvr application engineer", "sql developer"}
    original_titles = {exp.title.lower() for exp in parsed_resume.experience}
    tailored_titles = {exp.title.lower() for exp in tailored_result.experience}
    reframed = obscure & original_titles  # titles that were obscure in the original
    if not reframed:
        pytest.skip("No obscure titles found in parsed resume to check")
    # At least one obscure title should be different in the tailored output
    still_obscure = reframed & tailored_titles
    assert still_obscure != reframed, (
        f"LLM did not reframe any obscure titles. Still present: {still_obscure}"
    )
