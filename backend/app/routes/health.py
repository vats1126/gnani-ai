from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    ok: bool
    gemini_configured: bool
    gnani_configured: bool
    gemini_model: str
    env_source: str


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
async def get_health():
    # Ensure any live edits to .env are reflected dynamically
    settings._check_and_reload_if_modified()
    return HealthResponse(
        ok=True,
        gemini_configured=settings.is_gemini_configured,
        gnani_configured=settings.is_gnani_configured,
        gemini_model=settings.GEMINI_LIVE_MODEL,
        env_source=settings.env_source,
    )
