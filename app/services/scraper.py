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
REMOTEJOBS_URL = "https://www.remotejobs.com/jobs"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AutoApply/1.0)",
    "Accept": "application/json, text/html, application/rss+xml, */*",
}

# Explicit hard exclusions — job clearly not open to US applicants
_HARD_EXCLUDE_RE = re.compile(
    r"""
    \b(?:
        eu[-\s]only | europe[-\s]only | uk[-\s]only |
        emea[-\s]only | apac[-\s]only |
        not\s+(?:available|open|hiring)\s+(?:in|for|to)\s+(?:the\s+)?(?:us|usa|united\s+states) |
        (?:us|usa|united\s+states)\s+(?:residents?|applicants?|candidates?|citizens?)\s+not |
        no\s+(?:us|usa|united\s+states)\s+(?:residents?|applicants?|candidates?) |
        must\s+be\s+(?:based\s+)?in\s+(?:the\s+)?(?:eu|europe|uk|ireland|germany|france|netherlands|canada(?:\s+only)?) |
        (?:ireland|germany|france|netherlands|spain|italy|poland|uk|canada|australia|india)\s+only |
        european\s+union\s+only |
        outside\s+(?:the\s+)?(?:us|usa|united\s+states)\s+only
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Regex to pull "Location(s): Some City, Country (Remote)" from description
_LOCATION_EXTRACT_RE = re.compile(
    r"location(?:\(s\))?\s*:\s*([^\n]{3,80})", re.IGNORECASE
)


def _extract_location(description: str, fallback: str = "Remote") -> str:
    """Pull an explicit location line from the job description if present."""
    m = _LOCATION_EXTRACT_RE.search(description)
    if m:
        loc = m.group(1).strip().rstrip(".")
        # Keep it short — truncate after first semicolon or second comma
        loc = loc.split(";")[0].strip()
        return loc
    return fallback


def _us_remote_status(text: str, location: str) -> str:
    """Return 'yes' or 'no' — only hard-exclude when explicitly stated.

    A non-US company location (e.g. 'Dublin, Ireland (Remote)') is fine;
    the company is just based there. Only flag 'no' when the posting
    explicitly says US applicants are not welcome.
    """
    combined = text + " " + location
    if _HARD_EXCLUDE_RE.search(combined):
        return "no"
    return "yes"


def _enrich_job(job: Job) -> Job:
    """Detect secret instructions, location, and US-remote eligibility."""
    secrets = detect_secrets(job.description)
    job.secret_instructions = [s.secret for s in secrets]

    # Try to extract a real location from the description text
    extracted_loc = _extract_location(job.description, fallback=job.location or "Remote")
    job.location = extracted_loc

    job.us_remote = _us_remote_status(job.description, extracted_loc)
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


class RemoteJobsDotComScraper:
    """Scraper for remotejobs.com — tries Next.js __NEXT_DATA__ first, falls back to HTML."""

    async def fetch_jobs(self, filters: FilterConfig) -> list[Job]:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            try:
                res = await client.get(REMOTEJOBS_URL)
                res.raise_for_status()
            except Exception as e:
                print(f"[RemoteJobs] fetch failed: {e}")
                return []

        jobs = self._parse_next_data(res.text) or self._parse_html(res.text)
        out = []
        for job in jobs:
            combined = job.title + " " + job.description
            if not _matches_filters(combined, filters):
                continue
            out.append(_enrich_job(job))
        return out

    def _parse_next_data(self, html: str) -> list[Job]:
        """Extract jobs from Next.js __NEXT_DATA__ JSON blob if present."""
        import json as _json
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not tag or not tag.string:
            return []
        try:
            data = _json.loads(tag.string)
        except Exception:
            return []

        # Walk the props tree looking for a list that has job-like objects
        jobs_list = self._dig_jobs(data)
        if not jobs_list:
            return []

        out = []
        for item in jobs_list:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("position") or item.get("name") or ""
            company = item.get("company") or item.get("companyName") or item.get("organization") or ""
            desc = _strip_html(item.get("description") or item.get("body") or item.get("details") or "")
            slug = item.get("slug") or item.get("id") or ""
            url = item.get("url") or item.get("applyUrl") or item.get("applicationUrl") or (
                f"https://www.remotejobs.com/jobs/{slug}" if slug else REMOTEJOBS_URL
            )
            if not title:
                continue
            job_id = f"rjdc_{re.sub(r'[^\\w]', '_', str(slug or title))[:50]}"
            out.append(Job(
                id=job_id,
                source="remotejobs",
                title=str(title),
                company=str(company),
                description=desc,
                apply_url=str(url),
                location=item.get("location") or "Remote",
                tags=_extract_tags(title + " " + desc),
            ))
        return out

    def _dig_jobs(self, obj, depth: int = 0) -> list:
        """Recursively search a JSON tree for a list of job-like dicts."""
        if depth > 8:
            return []
        if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
            # Check if items look like jobs
            sample = obj[0]
            job_keys = {"title", "position", "description", "company", "companyName"}
            if job_keys & set(sample.keys()):
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                result = self._dig_jobs(v, depth + 1)
                if result:
                    return result
        return []

    def _parse_html(self, html: str) -> list[Job]:
        """Fallback: parse job cards from raw HTML."""
        soup = BeautifulSoup(html, "html.parser")
        out = []
        # Common selectors used by job boards
        for card in soup.select("article, [class*='job-card'], [class*='job_card'], [class*='JobCard'], [class*='listing']"):
            title_el = card.find(["h2", "h3", "h4"]) or card.find(attrs={"class": re.compile(r"title|position", re.I)})
            company_el = card.find(attrs={"class": re.compile(r"company|employer|org", re.I)})
            link_el = card.find("a", href=True)

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = "https://www.remotejobs.com" + href

            if not title:
                continue
            slug = re.sub(r"[^\w-]", "-", title.lower())[:60]
            job_id = f"rjdc_{slug}_{abs(hash(href)) % 100000}"
            out.append(Job(
                id=job_id,
                source="remotejobs",
                title=title,
                company=company,
                description="",
                apply_url=href or REMOTEJOBS_URL,
                location="Remote",
                tags=_extract_tags(title),
            ))
        return out


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
    # Hard-exclude only when explicitly not open to US — unclear stays in
    if _HARD_EXCLUDE_RE.search(text):
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
    rjdc = RemoteJobsDotComScraper()
    results = await asyncio.gather(
        rok.fetch_jobs(filters),
        wwr.fetch_jobs(filters),
        rjdc.fetch_jobs(filters),
        return_exceptions=True,
    )
    jobs: list[Job] = []
    for r in results:
        if isinstance(r, list):
            jobs.extend(r)
    return jobs
