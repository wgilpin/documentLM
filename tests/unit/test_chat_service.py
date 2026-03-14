"""Unit tests for chat_service — TDD. ChatAgent is always mocked."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from writer.models.enums import ChatRole
from writer.models.schemas import ChatMessageResponse


def _msg(**kwargs: object) -> ChatMessageResponse:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "role": ChatRole.user,
        "content": "Hello",
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return ChatMessageResponse(**defaults)


# ---------------------------------------------------------------------------
# Helpers: mock ORM message
# ---------------------------------------------------------------------------


def _orm_msg(
    id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    role: ChatRole = ChatRole.user,
    content: str = "Hello",
    created_at: datetime | None = None,
) -> MagicMock:
    m = MagicMock()
    m.id = id or uuid.uuid4()
    m.document_id = document_id or uuid.uuid4()
    m.role = role
    m.content = content
    m.created_at = created_at or datetime.now(UTC)
    return m


# ---------------------------------------------------------------------------
# create_chat_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_chat_message_stores_user_role() -> None:
    """create_chat_message persists a message with role=user and returns a response."""
    from writer.services import chat_service

    doc_id = uuid.uuid4()
    orm_result = _orm_msg(document_id=doc_id, role=ChatRole.user, content="Test message")

    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "_refreshed", True))
    db.add = MagicMock()

    with patch("writer.services.chat_service.ChatMessage") as MockChatMessage:
        mock_instance = MagicMock()
        mock_instance.id = orm_result.id
        mock_instance.document_id = orm_result.document_id
        mock_instance.role = ChatRole.user
        mock_instance.content = "Test message"
        mock_instance.created_at = orm_result.created_at
        MockChatMessage.return_value = mock_instance

        result = await chat_service.create_chat_message(db, doc_id, "Test message", ChatRole.user)

    assert result.role == ChatRole.user
    assert result.content == "Test message"
    assert result.document_id == doc_id
    db.add.assert_called_once()
    db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# list_chat_messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_chat_messages_ordered_by_created_at() -> None:
    """list_chat_messages returns messages ordered by created_at ascending."""
    from writer.services import chat_service

    doc_id = uuid.uuid4()
    t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 1, 10, 1, 0, tzinfo=UTC)
    msg1 = _orm_msg(document_id=doc_id, role=ChatRole.user, content="first", created_at=t1)
    msg2 = _orm_msg(document_id=doc_id, role=ChatRole.assistant, content="second", created_at=t2)

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [msg1, msg2]
    db.execute = AsyncMock(return_value=mock_result)

    results = await chat_service.list_chat_messages(db, doc_id)

    assert len(results) == 2
    assert results[0].content == "first"
    assert results[1].content == "second"
    assert results[0].created_at <= results[1].created_at


# ---------------------------------------------------------------------------
# process_chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_chat_calls_agent_and_returns_assistant_message() -> None:
    """process_chat invokes ChatAgent with history and persists assistant reply."""
    from writer.services import chat_service

    doc_id = uuid.uuid4()
    history = [
        _msg(document_id=doc_id, role=ChatRole.user, content="What themes are in this doc?"),
    ]
    agent_reply = "The main theme is perseverance."

    invoke_path = "writer.services.chat_service.invoke_chat_agent"
    create_path = "writer.services.chat_service.create_chat_message"
    with (
        patch(invoke_path, new_callable=AsyncMock) as mock_agent,
        patch(create_path, new_callable=AsyncMock) as mock_create,
    ):
        mock_agent.return_value = agent_reply
        mock_create.return_value = _msg(
            document_id=doc_id,
            role=ChatRole.assistant,
            content=agent_reply,
        )

        db = AsyncMock()
        result = await chat_service.process_chat(db, doc_id, history)

    mock_agent.assert_called_once_with(history)
    mock_create.assert_called_once_with(db, doc_id, agent_reply, ChatRole.assistant)
    assert result.role == ChatRole.assistant
    assert result.content == agent_reply
