"""User settings service — get and upsert per-user settings."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import UserSettings
from writer.models.schemas import UserSettingsResponse, UserSettingsUpdate

logger = get_logger(__name__)


def _defaults() -> UserSettingsResponse:
    return UserSettingsResponse(
        display_name=None,
        language_code="en",
        ai_instructions=None,
        updated_at=datetime.now(UTC),
    )


async def get_settings(db: AsyncSession, user_id: uuid.UUID) -> UserSettingsResponse:
    """Return current user settings, or defaults if no row exists yet."""
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    row = result.scalar_one_or_none()
    if row is None:
        logger.info("settings: no row found for user=%s, returning defaults", user_id)
        return _defaults()
    logger.info("settings: loaded for user=%s (language=%s)", user_id, row.language_code)
    return UserSettingsResponse.model_validate(row)


async def upsert_settings(
    db: AsyncSession, user_id: uuid.UUID, data: UserSettingsUpdate
) -> UserSettingsResponse:
    """Upsert the settings row for this user and return the updated settings."""
    stmt = (
        insert(UserSettings)
        .values(
            user_id=user_id,
            display_name=data.display_name,
            language_code=data.language_code,
            ai_instructions=data.ai_instructions,
        )
        .on_conflict_do_update(
            index_elements=["user_id"],
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
    logger.info("settings: upserted for user=%s (language=%s)", user_id, data.language_code)
    return await get_settings(db, user_id)
