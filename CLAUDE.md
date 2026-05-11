# AutoApply Resume Site — CLAUDE.md

## What This Project Is

A two-part automated job application system for Shane Smith (Cincinnati, OH):

1. **Python/FastAPI backend** — scrapes remote job boards (RemoteOK, We Work Remotely, RemoteJobs.com), uses Claude AI to tailor Shane's resume to each job description, generates a PDF + DOCX saved to `C:/Users/Shane/Documents/Resume/2025/updated/AIGenerated/`, and can auto-apply via Playwright or open the URL in a browser.

2. **Chrome extension** (`extension/`) — works on any job site. Detects job postings automatically, sends the job description to the local backend for tailoring, shows the result in a sidebar, and auto-fills application forms with profile data.

## Current Phase

Alpha — core functionality working. Active focus: output quality, extension reliability.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| LLM | Claude API (`claude-haiku-4-5-20251001`) or local Ollama — toggled in `config.yaml` |
| Job scraping | RemoteOK JSON API, WeWorkRemotely RSS, RemoteJobs.com HTML/Next.js |
| Resume parsing | pdfplumber (PDF), python-docx (DOCX) |
| Resume output | reportlab (PDF), python-docx (DOCX) |
| Browser automation | Playwright (auto-apply), subprocess xdg-open/open (semi-auto) |
| Frontend | Jinja2 + vanilla JS + Pico CSS (no build step, no npm) |
| Extension | Chrome Manifest V3, vanilla JS, no framework |
| Config | `config.yaml` + `.env` (ANTHROPIC_API_KEY) |

## Directory Structure

```
autoapply-resume-site/
├── app/
│   ├── api/           # FastAPI routers: jobs, tailor, resume, apply, settings
│   ├── models/        # Pydantic: Job, ParsedResume, TailoredResumeContent, AppSettings
│   ├── prompts/       # Jinja2 LLM templates: tailor_resume.j2, extract_keywords.j2
│   ├── services/      # scraper, llm_client, resume_parser, resume_builder, job_detector
│   └── utils/         # deps.py — startup dependency check
├── extension/         # Chrome extension (load unpacked from this folder)
│   ├── manifest.json
│   ├── background.js  # Service worker — POSTs to /api/tailor/inline
│   ├── content.js     # Injected into every page — job detection, form autofill, sidebar
│   ├── popup.html/js  # Extension popup — Server URL, Profile, Resume, Job Boards, Stats
│   └── icons/
├── frontend/          # Web dashboard
│   ├── templates/index.html
│   └── static/js/jobs.js, css/style.css
├── storage/tailored/  # Auto-generated resume files per job (internal, not the output dir)
├── tests/
├── config.yaml        # LLM provider, job filters, output_dir, user_profile
└── .env               # ANTHROPIC_API_KEY=sk-ant-...
```

## Build & Run

```bash
# Install (Windows — use python.org Python 3.12, NOT MinGW)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium

# Start server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/

# Load extension in Chrome
# Chrome → Extensions → Enable Developer Mode → Load unpacked → select extension/ folder
```

## Project-Specific Code Rules

1. **No WeasyPrint** — removed; crashes on Windows. Use `reportlab` only for PDF.
2. **Vanilla JS only** — no npm, no bundler, no framework on frontend or extension.
3. **Python 3.12.7 from python.org** — MinGW/MSYS builds break Playwright.
4. **Extension calls localhost:8000** — the FastAPI server must be running.
5. **All API endpoints return JSON** — never raw strings from FastAPI routes.
6. **`config.yaml` is the source of truth** — don't hardcode model names, output paths, or filters.
7. **Single LLM call per tailor** — keywords are extracted inline in `tailor_resume.j2`; never add a second LLM call back to the tailor flow.

## Known Gotchas

- Claude model must be `claude-haiku-4-5-20251001` exactly — other names 404.
- `HRFlowable` in reportlab crashes on Windows (`'super' object has no attribute 'transform'`) — use `Table`-based horizontal rules (already done).
- `pyo3_runtime.PanicException` from a broken `cryptography` build inherits `BaseException` not `Exception` — catch `BaseException` in dependency checks.
- Multi-column PDF layout produces duplicate bullets — `seen_bullets` set in `_parse_experience()` deduplicates them.
- Company names like `AGR LLC - GE Aviation` must be normalized to `AGR LLC (GE Aviation)` — `_normalize_company()` handles this at parse time AND is re-applied to LLM output in `llm_client.py`.
- The extension job-search tab opens real job board URLs — it does NOT ask an LLM to generate job listings (LLMs can't do that).
