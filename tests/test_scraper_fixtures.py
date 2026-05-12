"""
Scraper tests driven by saved fixtures (no network calls).

Fixture files live under tests/fixtures/:
  remoteok/jobs.json   — subset of https://remoteok.com/remote-jobs.json
  wwr/feed.xml         — subset of https://weworkremotely.com/remote-jobs.rss
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
    RemoteOKScraper,
    WeWorkRemotelyScraper,
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
# RemoteOK — JSON fixture
# ---------------------------------------------------------------------------

REMOTEOK_FIXTURE = FIXTURES / "remoteok" / "jobs.json"


@pytest.mark.skipif(not REMOTEOK_FIXTURE.exists(), reason="fixture not yet saved")
def test_remoteok_parses_fixture():
    raw = json.loads(REMOTEOK_FIXTURE.read_text())
    jobs = []
    for item in raw:
        if not isinstance(item, dict) or "id" not in item:
            continue
        from app.services.scraper import _strip_html, _enrich_job
        from app.models.job import Job
        desc = _strip_html(item.get("description", ""))
        job = Job(
            id=f"remoteok_{item['id']}",
            source="remoteok",
            title=item.get("position", ""),
            company=item.get("company", ""),
            description=desc,
            apply_url=item.get("url", f"https://remoteok.com/l/{item['id']}"),
            location="Remote",
            salary=item.get("salary") or None,
            tags=[t for t in (item.get("tags") or []) if t],
        )
        jobs.append(_enrich_job(job))

    assert len(jobs) >= 1, "Expected at least one job from fixture"
    j = jobs[0]
    assert j.source == "remoteok"
    assert j.title
    assert j.company
    assert j.apply_url.startswith("http")
    assert j.us_remote in ("yes", "no")


@pytest.mark.skipif(not REMOTEOK_FIXTURE.exists(), reason="fixture not yet saved")
def test_remoteok_filter_by_keyword():
    raw = json.loads(REMOTEOK_FIXTURE.read_text())
    # Grab the title of the first real job item
    first = next((x for x in raw if isinstance(x, dict) and "position" in x), None)
    if not first:
        pytest.skip("no job items in fixture")
    keyword = first["position"].split()[0]  # first word of title
    filters = FilterConfig(keywords=[keyword], roles=[], exclude_keywords=[])
    assert _matches_filters(first["position"], filters)


# ---------------------------------------------------------------------------
# We Work Remotely — RSS XML fixture
# ---------------------------------------------------------------------------

WWR_FIXTURE = FIXTURES / "wwr" / "feed.xml"


@pytest.mark.skipif(not WWR_FIXTURE.exists(), reason="fixture not yet saved")
def test_wwr_parses_fixture():
    from app.services.scraper import _enrich_job
    from app.models.job import Job

    soup = BeautifulSoup(WWR_FIXTURE.read_text(), "xml")
    items = soup.find_all("item")
    assert len(items) >= 1, "Expected at least one <item> in RSS fixture"

    jobs = []
    for item in items:
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        guid_el = item.find("guid")

        title_raw = title_el.text.strip() if title_el else ""
        link = link_el.text.strip() if link_el else (guid_el.text.strip() if guid_el else "")
        desc_raw = _strip_html(desc_el.text if desc_el else "")

        if ": " in title_raw:
            company, title = title_raw.split(": ", 1)
        else:
            company, title = "", title_raw

        slug = re.sub(r"[^\w-]", "-", title.lower())[:60]
        job_id = f"wwr_{slug}_{abs(hash(link)) % 100000}"

        job = Job(
            id=job_id,
            source="wwr",
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
    assert j.source == "wwr"
    assert j.title
    assert j.apply_url


@pytest.mark.skipif(not WWR_FIXTURE.exists(), reason="fixture not yet saved")
def test_wwr_company_title_split():
    soup = BeautifulSoup(WWR_FIXTURE.read_text(), "xml")
    item = soup.find("item")
    if not item:
        pytest.skip("no items in fixture")
    title_raw = item.find("title").text.strip()
    if ": " not in title_raw:
        pytest.skip("fixture item has no 'Company: Title' format")
    company, title = title_raw.split(": ", 1)
    assert company
    assert title


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
    # Company based in Ireland is fine — the posting doesn't exclude US applicants
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
