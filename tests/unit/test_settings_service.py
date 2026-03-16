"""Unit tests for settings_service — TDD (write first, confirm fail, then implement)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from writer.models.schemas import UserSettingsUpdate


def _make_settings_row(**kwargs: object) -> MagicMock:
    defaults = {
        "id": 1,
        "display_name": None,
        "language_code": "en",
        "ai_instructions": None,
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


class TestGetSettings:
    async def test_get_settings_returns_defaults_when_no_row(self) -> None:
        """When there is no row in the DB, defaults are returned."""
        from writer.services.settings_service import get_settings

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        result = await get_settings(db)

        assert result.display_name is None
        assert result.language_code == "en"
        assert result.ai_instructions is None

    async def test_get_settings_returns_saved_values(self) -> None:
        """When a row exists, its values are returned."""
        from writer.services.settings_service import get_settings

        db = AsyncMock()
        row = _make_settings_row(
            display_name="Alice",
            language_code="fr",
            ai_instructions="Always be formal.",
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        db.execute = AsyncMock(return_value=result_mock)

        result = await get_settings(db)

        assert result.display_name == "Alice"
        assert result.language_code == "fr"
        assert result.ai_instructions == "Always be formal."


class TestUpsertSettings:
    async def test_upsert_settings_creates_row_when_none_exists(self) -> None:
        """Upsert creates a new row and returns the updated settings."""
        from writer.services.settings_service import upsert_settings

        db = AsyncMock()
        # First call (get) returns None; second call (after upsert) returns the row
        saved_row = _make_settings_row(
            display_name="Bob",
            language_code="de",
            ai_instructions="Short replies.",
        )
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = None
        upsert_result = MagicMock()
        upsert_result.scalar_one_or_none.return_value = saved_row
        db.execute = AsyncMock(side_effect=[get_result, upsert_result])

        data = UserSettingsUpdate(
            display_name="Bob",
            language_code="de",
            ai_instructions="Short replies.",
        )
        result = await upsert_settings(db, data)

        assert result.display_name == "Bob"
        assert result.language_code == "de"
        assert result.ai_instructions == "Short replies."

    async def test_upsert_settings_updates_existing_row(self) -> None:
        """Upsert overwrites existing values."""
        from writer.services.settings_service import upsert_settings

        db = AsyncMock()
        updated_row = _make_settings_row(
            display_name="Carol",
            language_code="es",
            ai_instructions=None,
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = updated_row
        db.execute = AsyncMock(return_value=result_mock)

        data = UserSettingsUpdate(display_name="Carol", language_code="es")
        result = await upsert_settings(db, data)

        assert result.display_name == "Carol"
        assert result.language_code == "es"
        assert result.ai_instructions is None


class TestAiInstructionsValidation:
    def test_ai_instructions_max_length_rejected(self) -> None:
        """Pydantic rejects ai_instructions longer than 2000 characters."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserSettingsUpdate(ai_instructions="x" * 2001)

    def test_ai_instructions_at_limit_accepted(self) -> None:
        """Exactly 2000 characters is valid."""
        data = UserSettingsUpdate(ai_instructions="x" * 2000)
        assert data.ai_instructions is not None
        assert len(data.ai_instructions) == 2000
