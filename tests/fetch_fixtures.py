"""
Run this once locally to download real job pages as test fixtures.

Usage:
    python tests/fetch_fixtures.py

Saves HTML files to tests/fixtures/pages/.
Once saved, pytest tests/test_job_pages.py runs without network access.
"""

import time
from pathlib import Path

import httpx

PAGES_DIR = Path(__file__).parent / "fixtures" / "pages"
PAGES_DIR.mkdir(parents=True, exist_ok=True)

JOBS = [
    ("acquia_greenhouse",    "https://job-boards.greenhouse.io/acquia/jobs/7821888?gh_src=nodesk"),
    ("lullabot_bamboohr",    "https://lullabot.bamboohr.com/careers/49?source=nodesk"),
    ("axios_greenhouse",     "https://job-boards.greenhouse.io/axios/jobs/7818788"),
    ("chess_rippling",       "https://ats.rippling.com/en-GB/chess/jobs/7bfae6bd-a1ab-4c60-bd25-6f1bc2bc6e63?ref=nodesk"),
    ("remotejobs_swengineer","https://www.remotejobs.com/jobs/software-engineer-ii-a47d7327"),
    ("remotejobs_atlassian", "https://www.remotejobs.com/jobs/staff-it-systems-engineer-atlassian-d9838335"),
    ("stickermule",          "https://www.stickermule.com/career/6db27241-e2d4-4f35-a2c4-b58d84621843"),
    ("wwr_cue",              "https://weworkremotely.com/remote-jobs/cue-senior-software-engineer"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def main():
    with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        for name, url in JOBS:
            dest = PAGES_DIR / f"{name}.html"
            if dest.exists():
                print(f"  skip  {name} (already saved)")
                continue
            try:
                resp = client.get(url)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                size = len(resp.content)
                print(f"  saved {name}  ({size:,} bytes)  →  {dest}")
            except Exception as e:
                print(f"  ERROR {name}: {e}")
            time.sleep(1)  # be polite

    print("\nDone. Run:  pytest tests/test_job_pages.py -v")


if __name__ == "__main__":
    main()
