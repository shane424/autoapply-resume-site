from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import resume, jobs, tailor, apply, settings as settings_router, profile as profile_router
from app.utils.deps import print_startup_check, check_dependencies

BASE_DIR = Path(__file__).parent.parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
(STORAGE_DIR / "uploads").mkdir(exist_ok=True)
(STORAGE_DIR / "tailored").mkdir(exist_ok=True)

print_startup_check()

app = FastAPI(title="AutoApply Resume Site")


@app.on_event("startup")
async def _auto_load_resume():
    from app.config import env_settings
    from app.services.resume_parser import parse_resume
    import app.api.resume as resume_mod
    path_str = env_settings.resume_path.strip()
    if not path_str:
        return
    path = Path(path_str)
    if not path.exists():
        print(f"[startup] RESUME_PATH set but file not found: {path}")
        return
    try:
        resume_mod._active_resume = parse_resume(str(path))
        print(f"[startup] Auto-loaded resume from {path}")
    except Exception as e:
        print(f"[startup] Failed to auto-load resume from {path}: {e}")

# Allow Chrome extension (and any localhost origin) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

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
app.include_router(profile_router.router, prefix="/api/profile", tags=["profile"])


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


@app.get("/api/health")
async def health():
    results = check_dependencies()
    missing_required = [k for k in results if k not in ("playwright",) and results[k].startswith("MISSING")]
    return {
        "status": "ok" if not missing_required else "degraded",
        "dependencies": results,
        "missing_required": missing_required,
    }
