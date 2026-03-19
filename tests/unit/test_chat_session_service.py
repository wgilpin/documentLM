"""Unit tests for chat_session_service — TDD. DB is always mocked."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from writer.models.enums import SessionStatus


def _make_session(
    id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    status: SessionStatus = SessionStatus.active,
    created_at: datetime | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = id or uuid.uuid4()
    s.user_id = user_id or uuid.uuid4()
    s.document_id = document_id or uuid.uuid4()
    s.status = status
    s.created_at = created_at or datetime.now(UTC)
    return s


# ---------------------------------------------------------------------------
# get_or_create_active_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_active_session_returns_existing() -> None:
    """Returns the existing active session when one already exists."""
    from writer.services import chat_session_service

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    existing = _make_session(user_id=user_id, document_id=doc_id, status=SessionStatus.active)

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=mock_result)

    result = await chat_session_service.get_or_create_active_session(db, user_id, doc_id)

    assert result is existing
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_active_session_creates_when_none_exists() -> None:
    """Creates a new active session when no active session exists."""
    from writer.models.db import ChatSession
    from writer.services import chat_session_service

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    db.flush = AsyncMock()

    result = await chat_session_service.get_or_create_active_session(db, user_id, doc_id)

    assert isinstance(result, ChatSession)
    assert result.user_id == user_id
    assert result.document_id == doc_id
    db.add.assert_called_once()
    db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# session_has_messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_has_messages_returns_true_when_messages_exist() -> None:
    """Returns True when the session has at least one message."""
    from writer.services import chat_session_service

    session_id = uuid.uuid4()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 3
    db.execute = AsyncMock(return_value=mock_result)

    result = await chat_session_service.session_has_messages(db, session_id)

    assert result is True


@pytest.mark.asyncio
async def test_session_has_messages_returns_false_when_empty() -> None:
    """Returns False when the session has no messages."""
    from writer.services import chat_session_service

    session_id = uuid.uuid4()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    db.execute = AsyncMock(return_value=mock_result)

    result = await chat_session_service.session_has_messages(db, session_id)

    assert result is False
