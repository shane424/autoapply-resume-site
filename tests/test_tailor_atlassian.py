"""
Integration test: tailor resume for the Atlassian Staff IT Systems Engineer
posting on RemoteJobs.com.

Run:
  .venv\\Scripts\\python.exe -m pytest tests/test_tailor_atlassian.py -v -s
"""

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from tests.conftest import fetch_or_load, run_tailor_pipeline, print_ats_report, ats_score, resume_to_text

JOB_URL = "https://www.remotejobs.com/jobs/staff-it-systems-engineer-atlassian-d9838335"
FIXTURE_HTML = Path(__file__).parent / "fixtures" / "pages" / "remotejobs_atlassian.html"
OUTPUT_DIR   = Path(__file__).parent / "fixtures" / "pages"
JOB_ID       = "remotejobs_atlassian"


# ---------------------------------------------------------------------------
# RemoteJobs.com detail page parser
# ---------------------------------------------------------------------------

def _dig_job(obj, depth=0):
    if depth > 10:
        return None
    if isinstance(obj, dict):
        if {"title", "description"} & set(obj.keys()) and obj.get("title"):
            return obj
        for v in obj.values():
            r = _dig_job(v, depth + 1)
            if r:
                return r
    if isinstance(obj, list):
        for item in obj:
            r = _dig_job(item, depth + 1)
            if r:
                return r
    return None


def _parse_remotejobs_detail(html: str) -> dict:
    import json as _json
    from app.services.scraper import _strip_html

    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if tag and tag.string:
        try:
            data = _json.loads(tag.string)
            job = _dig_job(data)
            if job:
                return {
                    "title":       job.get("title") or job.get("name") or "",
                    "company":     job.get("company") or job.get("companyName") or "Atlassian",
                    "description": _strip_html(job.get("description") or job.get("body") or ""),
                    "url":         job.get("url") or job.get("applyUrl") or JOB_URL,
                }
        except Exception:
            pass

    # Fallback: pull from HTML elements
    title   = (soup.select_one("h1") or soup.select_one("h2") or "")
    company = soup.select_one("[class*='company']") or ""
    desc    = soup.select_one("[class*='description']") or soup.select_one("main") or ""
    return {
        "title":       title.get_text(strip=True) if title else "",
        "company":     company.get_text(strip=True) if company else "Atlassian",
        "description": desc.get_text(" ", strip=True) if desc else "",
        "url":         JOB_URL,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def atlassian_job():
    try:
        html = fetch_or_load(JOB_URL, "remotejobs_atlassian.html")
    except Exception as e:
        pytest.skip(f"Could not load page: {e}")
    job = _parse_remotejobs_detail(html)
    if not job["description"] or len(job["description"]) < 100:
        pytest.skip(
            "RemoteJobs.com page returned no description — likely JS-rendered.\n"
            f"Save manually: open {JOB_URL} in Chrome → Ctrl+S → save to {FIXTURE_HTML}"
        )
    return job


@pytest.fixture(scope="module")
def tailored_result(atlassian_job, parsed_resume, api_key):
    result = run_tailor_pipeline(atlassian_job, parsed_resume, JOB_ID)
    out = OUTPUT_DIR / "atlassian_tailored_output.json"
    out.write_text(json.dumps(result.model_dump(), indent=2, default=str), encoding="utf-8")
    print(f"\n[output] JSON  → {out}")
    if result.pdf_path:
        print(f"[output] PDF   → {result.pdf_path}")
    if result.docx_path:
        print(f"[output] DOCX  → {result.docx_path}")
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_page_has_title(atlassian_job):
    assert atlassian_job["title"], "Could not extract job title"


def test_page_has_description(atlassian_job):
    assert len(atlassian_job["description"]) > 100


def test_company_is_atlassian(atlassian_job):
    assert "atlassian" in atlassian_job["company"].lower() or \
           "atlassian" in atlassian_job["title"].lower()


def test_tailor_returns_summary(tailored_result):
    assert tailored_result.summary and len(tailored_result.summary) > 50


def test_tailor_returns_experience(tailored_result):
    assert len(tailored_result.experience) > 0
    for exp in tailored_result.experience:
        assert exp.title and exp.company and exp.bullets


def test_tailor_returns_skills(tailored_result):
    assert len(tailored_result.skills) >= 5


def test_no_invented_companies(parsed_resume, tailored_result):
    original = {e.company.lower() for e in parsed_resume.experience}
    for exp in tailored_result.experience:
        assert exp.company.lower() in original, \
            f"Invented company: '{exp.company}'"


def test_pdf_was_built(tailored_result, capsys):
    from pathlib import Path as P
    assert tailored_result.pdf_path, "pdf_path is None"
    pdf = P(tailored_result.pdf_path)
    assert pdf.exists()
    assert pdf.read_bytes()[:4] == b"%PDF"
    with capsys.disabled():
        print(f"\n  PDF: {tailored_result.pdf_path}  ({pdf.stat().st_size:,} bytes)")


def test_ats_score(atlassian_job, tailored_result, capsys):
    result = print_ats_report(atlassian_job, tailored_result, capsys)
    assert result["score"] >= 35, \
        f"ATS score too low: {result['score']:.1f}%  Missing: {result['missing'][:8]}"
