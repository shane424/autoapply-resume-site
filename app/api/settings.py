from fastapi import APIRouter, HTTPException
from app.config import load_app_settings, save_app_settings
from app.models.settings import AppSettings

router = APIRouter()


@router.get("", response_model=AppSettings)
async def get_settings():
    return load_app_settings()


@router.put("", response_model=AppSettings)
async def update_settings(new_settings: AppSettings):
    try:
        save_app_settings(new_settings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")
    return new_settings
