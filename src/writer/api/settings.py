"""Settings API endpoints — GET and POST /api/settings."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.models.schemas import UserResponse, UserSettingsResponse, UserSettingsUpdate
from writer.services import settings_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


@router.get("", response_model=UserSettingsResponse)
async def get_settings(db: DbDep, current_user: CurrentUser) -> UserSettingsResponse:
    """Return current user settings (defaults if not yet saved)."""
    return await settings_service.get_settings(db, current_user.id)


@router.post("", response_model=UserSettingsResponse)
async def update_settings(
    data: UserSettingsUpdate,
    db: DbDep,
    current_user: CurrentUser,
) -> JSONResponse:
    """Upsert user settings and return the updated values.

    Returns HX-Trigger header so HTMX can close the settings dialog.
    """
    result = await settings_service.upsert_settings(db, current_user.id, data)
    return JSONResponse(
        content=result.model_dump(mode="json"),
        headers={"HX-Trigger": "settingsSaved"},
    )
