import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

PROFILE_PATH = Path(__file__).parent.parent.parent / "profiles" / "profile.json"


@router.get("")
async def get_profile():
    if not PROFILE_PATH.exists():
        raise HTTPException(status_code=404, detail="profile.json not found in profiles/ folder.")
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)
