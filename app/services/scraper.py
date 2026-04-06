import asyncio
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.models.job import Job
from app.models.settings import FilterConfig
from app.services.job_detector import detect_secrets, format_secret_for_application

REMOTEOK_URL = "https://remoteok.com/remote-jobs.json"
WWR_URL = "https://weworkremotely.com/remote-jobs.rss"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AutoApply/1.0)",
    "Accept": "application/json, text/html, application/rss+xml, */*",
}

# Patterns that indicate a position is NOT open to US-based remote workers.
# We err on the side of inclusion — only exclude when explicitly restricted.
_NON_US_PATTERNS = re.compile(
    r"""
    \b(?:
        eu[-\s]only | europe[-\s]only | uk[-\s]only |
        emea[-\s]only | apac[-\s]only |
        not\s+(?:available|open|hiring)\s+(?:in|for|to)\s+(?:the\s+)?(?:us|usa|united\s+states) |
        (?:us|usa|united\s+states)\s+(?:residents?|applicants?|candidates?|citizens?)\s+not |
        no\s+(?:us|usa|united\s+states)\s+(?:residents?|applicants?|candidates?) |
        must\s+be\s+(?:based\s+)?in\s+(?:the\s+)?(?:eu|europe|uk|germany|france|netherlands|canada(?:\s+only)?) |
        (?:germany|france|netherlands|spain|italy|poland|uk|canada)\s+only |
        (?:work\s+)?visa\s+(?:sponsorship\s+)?not\s+(?:available|provided|offered) |
        european\s+union\s+only |
        outside\s+(?:the\s+)?(?:us|usa|united\s+states)\s+only
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _is_us_remote(text: str) -> bool:
    """Return False if the job description explicitly excludes US-based applicants."""
    return not bool(_NON_US_PATTERNS.search(text))


def _enrich_job(job: Job) -> Job:
    """Detect secret instructions and US-remote eligibility from description."""
    secrets = detect_secrets(job.description)
    job.secret_instructions = [s.secret for s in secrets]
    job.us_remote = _is_us_remote(job.description + " " + job.location)
    return job


class RemoteOKScraper:
    async def fetch_jobs(self, filters: FilterConfig) -> list[Job]:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            try:
                res = await client.get(REMOTEOK_URL)
                res.raise_for_status()
            except Exception as e:
                print(f"[RemoteOK] fetch failed: {e}")
                return []

        raw = res.json()
        jobs = []
        for item in raw:
            if not isinstance(item, dict) or "id" not in item:
                continue
            desc = _strip_html(item.get("description", ""))
            combined = item.get("position", "") + " " + desc
            if not _matches_filters(combined, filters):
                continue
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
                posted_at=_parse_epoch(item.get("date")),
            )
            jobs.append(_enrich_job(job))
        return jobs


class WeWorkRemotelyScraper:
    async def fetch_jobs(self, filters: FilterConfig) -> list[Job]:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            try:
                res = await client.get(WWR_URL)
                res.raise_for_status()
            except Exception as e:
                print(f"[WWR] fetch failed: {e}")
                return []

        soup = BeautifulSoup(res.text, "xml")
        items = soup.find_all("item")
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

            if not _matches_filters(title + " " + desc_raw, filters):
                continue

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
                tags=_extract_tags(title + " " + desc_raw),
            )
            jobs.append(_enrich_job(job))
        return jobs


def _matches_filters(text: str, filters: FilterConfig) -> bool:
    text_lower = text.lower()
    if filters.exclude_keywords:
        if any(kw.lower() in text_lower for kw in filters.exclude_keywords if kw):
            return False
    if filters.keywords:
        if not any(kw.lower() in text_lower for kw in filters.keywords if kw):
            return False
    if filters.roles:
        if not any(role.lower() in text_lower for role in filters.roles if role):
            return False
    # Exclude non-US-remote positions
    if not _is_us_remote(text):
        return False
    return True


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n").strip()


def _parse_epoch(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value))
    except Exception:
        return None


def _extract_tags(text: str) -> list[str]:
    common = [
        "Python","JavaScript","TypeScript","React","Node.js","Go","Rust","Java","C#",
        "AWS","GCP","Azure","Docker","Kubernetes","PostgreSQL","MongoDB","Redis",
        "FastAPI","Django","Flask","Rails","GraphQL","REST","DevOps","ML","AI",
        "Remote","Full-time","Part-time","Contract",
    ]
    found = []
    text_lower = text.lower()
    for tag in common:
        if tag.lower() in text_lower and tag not in found:
            found.append(tag)
    return found[:8]


async def scrape_all(filters: FilterConfig) -> list[Job]:
    rok = RemoteOKScraper()
    wwr = WeWorkRemotelyScraper()
    results = await asyncio.gather(
        rok.fetch_jobs(filters),
        wwr.fetch_jobs(filters),
        return_exceptions=True,
    )
    jobs: list[Job] = []
    for r in results:
        if isinstance(r, list):
            jobs.extend(r)
    return jobs
