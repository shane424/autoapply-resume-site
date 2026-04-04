import asyncio
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.models.job import Job
from app.models.settings import FilterConfig

REMOTEOK_URL = "https://remoteok.com/remote-jobs.json"
WWR_URL = "https://weworkremotely.com/remote-jobs.rss"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AutoApply/1.0)",
    "Accept": "application/json, text/html, application/rss+xml, */*",
}


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
        # First item is a legal notice dict; skip it
        jobs = []
        for item in raw:
            if not isinstance(item, dict) or "id" not in item:
                continue
            if not _matches_filters(item.get("position","") + " " + item.get("description",""), filters):
                continue
            jobs.append(Job(
                id=f"remoteok_{item['id']}",
                source="remoteok",
                title=item.get("position", ""),
                company=item.get("company", ""),
                description=_strip_html(item.get("description", "")),
                apply_url=item.get("url", f"https://remoteok.com/l/{item['id']}"),
                location="Remote",
                salary=item.get("salary") or None,
                tags=[t for t in (item.get("tags") or []) if t],
                posted_at=_parse_epoch(item.get("date")),
            ))
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

            # WWR title format: "Company Name: Job Title"
            if ": " in title_raw:
                company, title = title_raw.split(": ", 1)
            else:
                company, title = "", title_raw

            if not _matches_filters(title + " " + desc_raw, filters):
                continue

            slug = re.sub(r"[^\w-]", "-", title.lower())[:60]
            job_id = f"wwr_{slug}_{abs(hash(link)) % 100000}"

            jobs.append(Job(
                id=job_id,
                source="wwr",
                title=title.strip(),
                company=company.strip(),
                description=desc_raw,
                apply_url=link,
                location="Remote",
                tags=_extract_tags(title + " " + desc_raw),
            ))
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
            # Soft match — if roles are specified at least one should appear
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
