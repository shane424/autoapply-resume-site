import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.resume_parser import parse_resume
from app.models.resume import ParsedResume

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent.parent / "storage" / "uploads"

# In-memory active resume (single-user)
_active_resume: ParsedResume | None = None


def get_active_resume() -> ParsedResume | None:
    return _active_resume


@router.post("/upload", response_model=ParsedResume)
async def upload_resume(file: UploadFile = File(...)):
    global _active_resume
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc"):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    save_path = UPLOAD_DIR / file.filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        _active_resume = parse_resume(str(save_path))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse resume: {e}")

    return _active_resume


@router.get("/current", response_model=ParsedResume | None)
async def get_current_resume():
    return _active_resume


@router.delete("")
async def delete_resume():
    global _active_resume
    _active_resume = None
    return {"message": "Resume cleared."}
