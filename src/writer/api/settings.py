"""Settings API endpoints — GET and POST /api/settings."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.models.schemas import UserSettingsResponse, UserSettingsUpdate
from writer.services import settings_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    """Return current user settings (defaults if not yet saved)."""
    return await settings_service.get_settings(db)


@router.post("", response_model=UserSettingsResponse)
async def update_settings(
    data: UserSettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Upsert user settings and return the updated values.

    Returns HX-Trigger header so HTMX can close the settings dialog.
    """
    result = await settings_service.upsert_settings(db, data)
    return JSONResponse(
        content=result.model_dump(mode="json"),
        headers={"HX-Trigger": "settingsSaved"},
    )
