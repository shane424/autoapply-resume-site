"""
Scraper tests driven by saved fixtures (no network calls).

Fixture files live under tests/fixtures/:
  remotive/jobs.json   — subset of https://remotive.com/api/remote-jobs
  jobicy/feed.xml      — subset of https://jobicy.com/?feed=job_feed
  remotejobs/page.html — full HTML of https://www.remotejobs.com/jobs

Run:  pytest tests/test_scraper_fixtures.py -v
"""

import json
import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.models.settings import FilterConfig
from app.services.scraper import (
    RemotiveScraper,
    JobicyScraper,
    RemoteJobsDotComScraper,
    _matches_filters,
    _strip_html,
    _us_remote_status,
    _extract_location,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def no_filters() -> FilterConfig:
    return FilterConfig(keywords=[], roles=[], exclude_keywords=[])


# ---------------------------------------------------------------------------
# Remotive — JSON fixture
# ---------------------------------------------------------------------------

REMOTIVE_FIXTURE = FIXTURES / "remotive" / "jobs.json"


@pytest.mark.skipif(not REMOTIVE_FIXTURE.exists(), reason="fixture not yet saved")
def test_remotive_parses_fixture():
    from app.services.scraper import _enrich_job
    from app.models.job import Job

    data = json.loads(REMOTIVE_FIXTURE.read_text())
    raw = data.get("jobs", data) if isinstance(data, dict) else data
    jobs = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        desc = _strip_html(item.get("description", ""))
        job = Job(
            id=f"remotive_{item.get('id', abs(hash(item.get('url', ''))) % 1_000_000)}",
            source="remotive",
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            description=desc,
            apply_url=item.get("url", "https://remotive.com"),
            location=item.get("candidate_required_location") or "Remote",
            salary=item.get("salary") or None,
            tags=[t for t in (item.get("tags") or []) if t],
        )
        jobs.append(_enrich_job(job))

    assert len(jobs) >= 1, "Expected at least one job from fixture"
    j = jobs[0]
    assert j.source == "remotive"
    assert j.title
    assert j.company
    assert j.apply_url.startswith("http")
    assert j.us_remote in ("yes", "no")


@pytest.mark.skipif(not REMOTIVE_FIXTURE.exists(), reason="fixture not yet saved")
def test_remotive_filter_by_keyword():
    data = json.loads(REMOTIVE_FIXTURE.read_text())
    raw = data.get("jobs", data) if isinstance(data, dict) else data
    first = next((x for x in raw if isinstance(x, dict) and x.get("title")), None)
    if not first:
        pytest.skip("no job items in fixture")
    keyword = first["title"].split()[0]
    filters = FilterConfig(keywords=[keyword], roles=[], exclude_keywords=[])
    assert _matches_filters(first["title"], filters)


# ---------------------------------------------------------------------------
# Jobicy — RSS XML fixture
# ---------------------------------------------------------------------------

JOBICY_FIXTURE = FIXTURES / "jobicy" / "feed.xml"


@pytest.mark.skipif(not JOBICY_FIXTURE.exists(), reason="fixture not yet saved")
def test_jobicy_parses_fixture():
    from app.services.scraper import _enrich_job
    from app.models.job import Job

    soup = BeautifulSoup(JOBICY_FIXTURE.read_text(), "xml")
    items = soup.find_all("item")
    assert len(items) >= 1, "Expected at least one <item> in RSS fixture"

    jobs = []
    for item in items:
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        guid_el = item.find("guid")
        company_el = item.find("jobicy:hiringOrganization") or item.find("hiringOrganization")

        title = title_el.text.strip() if title_el else ""
        link = link_el.text.strip() if link_el else (guid_el.text.strip() if guid_el else "")
        desc_raw = _strip_html(desc_el.text if desc_el else "")
        company = company_el.text.strip() if company_el else ""

        if not company and ": " in title:
            company, title = title.split(": ", 1)

        slug = re.sub(r"[^\w-]", "-", title.lower())[:60]
        job_id = f"jobicy_{slug}_{abs(hash(link)) % 100000}"

        job = Job(
            id=job_id,
            source="jobicy",
            title=title.strip(),
            company=company.strip(),
            description=desc_raw,
            apply_url=link,
            location="Remote",
            tags=[],
        )
        jobs.append(_enrich_job(job))

    assert len(jobs) >= 1
    j = jobs[0]
    assert j.source == "jobicy"
    assert j.title
    assert j.apply_url


@pytest.mark.skipif(not JOBICY_FIXTURE.exists(), reason="fixture not yet saved")
def test_jobicy_ids_are_unique():
    soup = BeautifulSoup(JOBICY_FIXTURE.read_text(), "xml")
    items = soup.find_all("item")
    ids = set()
    for item in items:
        link_el = item.find("link")
        guid_el = item.find("guid")
        link = link_el.text.strip() if link_el else (guid_el.text.strip() if guid_el else "")
        title_el = item.find("title")
        title = title_el.text.strip() if title_el else ""
        slug = re.sub(r"[^\w-]", "-", title.lower())[:60]
        job_id = f"jobicy_{slug}_{abs(hash(link)) % 100000}"
        ids.add(job_id)
    assert len(ids) == len(items), "Duplicate job IDs detected"


# ---------------------------------------------------------------------------
# RemoteJobs.com — HTML fixture
# ---------------------------------------------------------------------------

REMOTEJOBS_FIXTURE = FIXTURES / "remotejobs" / "page.html"


@pytest.mark.skipif(not REMOTEJOBS_FIXTURE.exists(), reason="fixture not yet saved")
def test_remotejobs_parses_next_data():
    scraper = RemoteJobsDotComScraper()
    html = REMOTEJOBS_FIXTURE.read_text()
    jobs = scraper._parse_next_data(html)
    if not jobs:
        jobs = scraper._parse_html(html)
    assert len(jobs) >= 1, "Expected at least one job from remotejobs fixture"
    j = jobs[0]
    assert j.title
    assert j.apply_url


@pytest.mark.skipif(not REMOTEJOBS_FIXTURE.exists(), reason="fixture not yet saved")
def test_remotejobs_all_have_source():
    scraper = RemoteJobsDotComScraper()
    html = REMOTEJOBS_FIXTURE.read_text()
    jobs = scraper._parse_next_data(html) or scraper._parse_html(html)
    for j in jobs:
        assert j.source == "remotejobs"


# ---------------------------------------------------------------------------
# Shared / cross-site unit tests (no fixture files needed)
# ---------------------------------------------------------------------------

def test_us_remote_hard_exclude_eu_only():
    assert _us_remote_status("This role is EU-only", "Remote") == "no"


def test_us_remote_hard_exclude_europe_only():
    assert _us_remote_status("Europe only position", "Remote") == "no"


def test_us_remote_allows_ireland_company():
    assert _us_remote_status("We are a Dublin, Ireland company", "Remote") == "yes"


def test_us_remote_no_us_applicants():
    assert _us_remote_status("No US applicants please", "Remote") == "no"


def test_extract_location_from_description():
    desc = "We are hiring!\nLocation: New York, USA (Remote)\nApply today."
    assert "New York" in _extract_location(desc)


def test_extract_location_fallback():
    assert _extract_location("No location info here") == "Remote"


def test_strip_html_removes_tags():
    # separator="\n" is intentional — preserves paragraph breaks in job descriptions
    result = _strip_html("<p>Hello <b>world</b></p>")
    assert "Hello" in result and "world" in result
    assert "<" not in result
