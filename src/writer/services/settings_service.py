"""User settings service — get and upsert the single-row user settings record."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import UserSettings
from writer.models.schemas import UserSettingsResponse, UserSettingsUpdate

logger = get_logger(__name__)

_SETTINGS_ID = 1


def _defaults() -> UserSettingsResponse:
    return UserSettingsResponse(
        display_name=None,
        language_code="en",
        ai_instructions=None,
        updated_at=datetime.now(UTC),
    )


async def get_settings(db: AsyncSession) -> UserSettingsResponse:
    """Return current user settings, or defaults if no row exists yet."""
    result = await db.execute(select(UserSettings).where(UserSettings.id == _SETTINGS_ID))
    row = result.scalar_one_or_none()
    if row is None:
        logger.info("settings: no row found, returning defaults")
        return _defaults()
    logger.info("settings: loaded (language=%s)", row.language_code)
    return UserSettingsResponse.model_validate(row)


async def upsert_settings(db: AsyncSession, data: UserSettingsUpdate) -> UserSettingsResponse:
    """Upsert the single settings row (id=1) and return the updated settings."""
    stmt = (
        insert(UserSettings)
        .values(
            id=_SETTINGS_ID,
            display_name=data.display_name,
            language_code=data.language_code,
            ai_instructions=data.ai_instructions,
        )
        .on_conflict_do_update(
            index_elements=["id"],
            set_={
                "display_name": data.display_name,
                "language_code": data.language_code,
                "ai_instructions": data.ai_instructions,
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await db.execute(stmt)
    await db.flush()
    logger.info("settings: upserted (language=%s)", data.language_code)
    return await get_settings(db)
