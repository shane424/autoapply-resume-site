from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import resume, jobs, tailor, apply, settings as settings_router

BASE_DIR = Path(__file__).parent.parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
(STORAGE_DIR / "uploads").mkdir(exist_ok=True)
(STORAGE_DIR / "tailored").mkdir(exist_ok=True)

app = FastAPI(title="AutoApply Resume Site")

# Static file mounts
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))

# API routers
app.include_router(resume.router, prefix="/api/resume", tags=["resume"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(tailor.router, prefix="/api/tailor", tags=["tailor"])
app.include_router(apply.router, prefix="/api/apply", tags=["apply"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])


# Frontend page routes
@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/resume")
async def resume_page(request: Request):
    return templates.TemplateResponse("resume.html", {"request": request})


@app.get("/jobs/{job_id}")
async def job_detail_page(request: Request, job_id: str):
    return templates.TemplateResponse("job_detail.html", {"request": request, "job_id": job_id})


@app.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})
