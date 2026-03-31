# AutoApply Resume Site

Automated resume tailoring and job application system. Scrapes remote jobs from RemoteOK and We Work Remotely, uses an LLM (Claude or Ollama) to tailor your resume to each job description, generates a tailored PDF/DOCX, and can auto-apply via Playwright or open the job URL in your browser.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright browser (for auto-apply)

```bash
bash scripts/install_playwright_browsers.sh
```

### 3. Configure secrets

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 4. Configure settings

Edit `config.yaml` to set your job search filters, LLM provider, and profile info.
You can also edit all settings from the web UI at `/settings`.

### 5. Run the dev server

```bash
bash scripts/run_dev.sh
# or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Usage

1. **Upload your resume** at `/resume` — supports PDF and DOCX.
2. **Configure filters** at `/settings` — set target roles, keywords, and your profile.
3. **Refresh jobs** on the dashboard — scrapes RemoteOK and We Work Remotely.
4. **Tailor** — click "Tailor" on any job to generate a tailored PDF/DOCX.
5. **Apply**:
   - "Auto Apply" — Playwright fills and submits the form automatically.
   - "Open URL" — opens the job URL in your browser for manual completion.

---

## LLM Toggle

Switch between Claude and Ollama at `/settings`. The toggle takes effect immediately — no restart needed.

- **Claude**: requires `ANTHROPIC_API_KEY` in `.env`.
- **Ollama**: requires a running Ollama instance (default: `http://localhost:11434`). Set your preferred model in settings.

---

## ATS Support (Auto-Apply)

Full auto-apply supports:
- Greenhouse (`boards.greenhouse.io`)
- Lever (`jobs.lever.co`)
- Workable (`apply.workable.com`)
- Ashby (`jobs.ashbyhq.com`)
- Unknown/custom (heuristic best-effort)

When auto-apply fails, a screenshot is saved to `storage/tailored/{job_id}/error.png` and you can fall back to semi-auto mode.

---

## Running Tests

```bash
pytest tests/
```

---

## Project Structure

```
app/           FastAPI backend
  api/         Route handlers (resume, jobs, tailor, apply, settings)
  services/    Business logic (scraper, LLM, resume parser/builder, apply)
  models/      Pydantic data models
  prompts/     Jinja2 LLM prompt templates
frontend/      Jinja2 templates + vanilla JS + CSS
storage/       Runtime files (uploads, tailored resumes) — gitignored
tests/         Unit tests
config.yaml    User configuration (filters, LLM, profile)
.env           Secrets (API keys) — gitignored
```
