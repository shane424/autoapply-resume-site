"""
Playwright-based auto-apply service.

Detects the ATS (Greenhouse, Lever, Workable, Ashby, or unknown) from the
job application URL and delegates to the appropriate strategy.
"""
import re
from pathlib import Path
from typing import Optional

from app.models.job import Job
from app.models.settings import UserProfile

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "tailored"


def detect_ats(url: str) -> str:
    url_lower = url.lower()
    if "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
        return "greenhouse"
    if "lever.co" in url_lower:
        return "lever"
    if "workable.com" in url_lower or "apply.workable" in url_lower:
        return "workable"
    if "ashbyhq.com" in url_lower or "jobs.ashby" in url_lower:
        return "ashby"
    return "unknown"


async def _fill_greenhouse(page, profile: UserProfile, resume_path: Path) -> None:
    await page.wait_for_load_state("networkidle", timeout=15000)
    await _try_fill(page, "#first_name", profile.first_name)
    await _try_fill(page, "#last_name", profile.last_name)
    await _try_fill(page, "#email", profile.email)
    await _try_fill(page, "#phone", profile.phone)
    if profile.linkedin:
        await _try_fill(page, "input[name*='linkedin'], input[placeholder*='LinkedIn']", profile.linkedin)
    if profile.website:
        await _try_fill(page, "input[name*='website'], input[placeholder*='website']", profile.website)
    await _try_upload(page, "input[type='file']", resume_path)
    await _try_eeoc(page)
    if profile.cover_letter_template:
        await _try_fill(page, "textarea[name*='cover'], textarea[placeholder*='cover']",
                        profile.cover_letter_template)
    await _try_submit(page)


async def _fill_lever(page, profile: UserProfile, resume_path: Path) -> None:
    await page.wait_for_load_state("networkidle", timeout=15000)
    await _try_fill(page, "input[name='name']", f"{profile.first_name} {profile.last_name}".strip())
    await _try_fill(page, "input[name='email']", profile.email)
    await _try_fill(page, "input[name='phone']", profile.phone)
    if profile.linkedin:
        await _try_fill(page, "input[name*='linkedin']", profile.linkedin)
    if profile.website:
        await _try_fill(page, "input[name*='urls[Other]'], input[name*='website']", profile.website)
    await _try_upload(page, "input[type='file']", resume_path)
    if profile.cover_letter_template:
        await _try_fill(page, "textarea[name='comments']", profile.cover_letter_template)
    await _try_submit(page)


async def _fill_workable(page, profile: UserProfile, resume_path: Path) -> None:
    await page.wait_for_load_state("networkidle", timeout=15000)
    await _try_fill(page, "input[name='firstname'], input[id='firstname']", profile.first_name)
    await _try_fill(page, "input[name='lastname'], input[id='lastname']", profile.last_name)
    await _try_fill(page, "input[name='email'], input[type='email']", profile.email)
    await _try_fill(page, "input[name='phone'], input[type='tel']", profile.phone)
    await _try_upload(page, "input[type='file']", resume_path)
    await _try_submit(page)


async def _fill_ashby(page, profile: UserProfile, resume_path: Path) -> None:
    await page.wait_for_load_state("networkidle", timeout=15000)
    await _try_fill(page, "input[placeholder*='First'], input[name*='firstName']", profile.first_name)
    await _try_fill(page, "input[placeholder*='Last'], input[name*='lastName']", profile.last_name)
    await _try_fill(page, "input[type='email']", profile.email)
    await _try_fill(page, "input[type='tel']", profile.phone)
    await _try_upload(page, "input[type='file']", resume_path)
    await _try_submit(page)


async def _fill_unknown(page, profile: UserProfile, resume_path: Path) -> None:
    """Best-effort heuristic fill for unknown ATS."""
    await page.wait_for_load_state("networkidle", timeout=15000)
    await _try_fill(page, "input[name*='first'], input[placeholder*='First']", profile.first_name)
    await _try_fill(page, "input[name*='last'], input[placeholder*='Last']", profile.last_name)
    await _try_fill(page, "input[type='email'], input[name*='email']", profile.email)
    await _try_fill(page, "input[type='tel'], input[name*='phone']", profile.phone)
    if profile.linkedin:
        await _try_fill(page, "input[name*='linkedin'], input[placeholder*='LinkedIn']", profile.linkedin)
    await _try_upload(page, "input[type='file']", resume_path)
    await _try_submit(page)


async def _try_fill(page, selector: str, value: str) -> None:
    if not value:
        return
    for sel in selector.split(", "):
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                await el.fill(value)
                return
        except Exception:
            continue


async def _try_upload(page, selector: str, resume_path: Path) -> None:
    if not resume_path or not resume_path.exists():
        return
    try:
        el = page.locator(selector).first
        await el.set_input_files(str(resume_path), timeout=5000)
    except Exception:
        pass


async def _try_submit(page) -> None:
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit')",
        "button:has-text('Apply')",
        "button:has-text('Send Application')",
    ]
    for sel in submit_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                await el.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                return
        except Exception:
            continue


async def _try_eeoc(page) -> None:
    """Fill EEOC/EEO dropdowns with 'Decline to identify'."""
    decline_values = ["decline", "prefer not", "do not wish", "i don't wish", "no answer"]
    try:
        selects = await page.locator("select").all()
        for select in selects:
            options = await select.locator("option").all_text_contents()
            for opt in options:
                if any(v in opt.lower() for v in decline_values):
                    await select.select_option(label=opt)
                    break
    except Exception:
        pass


async def auto_apply(job: Job, profile: UserProfile) -> None:
    from playwright.async_api import async_playwright

    job_dir = STORAGE_DIR / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    resume_path = job_dir / "resume.pdf"
    screenshot_path = job_dir / "error.png"

    ats = detect_ats(job.apply_url)
    strategy_map = {
        "greenhouse": _fill_greenhouse,
        "lever": _fill_lever,
        "workable": _fill_workable,
        "ashby": _fill_ashby,
        "unknown": _fill_unknown,
    }
    fill_fn = strategy_map.get(ats, _fill_unknown)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(job.apply_url, timeout=20000, wait_until="domcontentloaded")
            await fill_fn(page, profile, resume_path)
        except Exception as e:
            await page.screenshot(path=str(screenshot_path))
            await browser.close()
            raise RuntimeError(f"Auto-apply failed ({ats}): {e}") from e
        await browser.close()
