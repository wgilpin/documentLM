"""Integration tests for chat session management against a real PostgreSQL database.

Run with: docker-compose up -d postgres && uv run pytest tests/integration/
Requires DATABASE_URL env var pointing to a test-ready PostgreSQL instance.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from writer.core.config import settings
from writer.core.database import Base
from writer.models import db as _db_models  # noqa: F401 — register all ORM models
from writer.models.enums import SessionStatus


@pytest_asyncio.fixture()
async def db() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session  # type: ignore[misc]
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture()
async def user_and_doc(db: AsyncSession):  # type: ignore[misc]
    """Create a user and document for testing."""
    from writer.models.schemas import DocumentCreate
    from writer.services.auth_service import create_invite_codes, register_user
    from writer.services.document_service import create_document

    codes = await create_invite_codes(db, count=1)
    await db.flush()
    user = await register_user(db, codes[0], "session_test@example.com", "password123")
    await db.flush()
    doc = await create_document(db, DocumentCreate(title="Session Test Doc"), user.id)
    await db.flush()
    return user, doc


class TestCreateNewSession:
    async def test_archives_current_session_when_it_has_messages(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """create_new_session archives the current session when it has messages."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        # Create active session and add a message
        session = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, session.id, "Hello", ChatRole.user)
        await db.flush()

        # Create new session — should archive the old one
        new_session = await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()

        assert new_session is not None
        assert new_session.id != session.id
        assert new_session.status == SessionStatus.active

        # Old session must be archived
        await db.refresh(session)
        assert session.status == SessionStatus.archived

    async def test_returns_none_when_current_session_is_empty(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """create_new_session returns None when current session has no messages (no-op)."""
        from writer.services import chat_session_service

        user, doc = user_and_doc

        # Create active session with no messages
        await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()

        result = await chat_session_service.create_new_session(db, user.id, doc.id)

        assert result is None

    async def test_only_one_active_session_exists_after_creation(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """At most one active session exists per (user_id, document_id) after create_new_session."""
        from sqlalchemy import func, select

        from writer.models.db import ChatSession
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        session = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, session.id, "Hi", ChatRole.user)
        await db.flush()

        await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()

        result = await db.execute(
            select(func.count(ChatSession.id)).where(
                ChatSession.user_id == user.id,
                ChatSession.document_id == doc.id,
                ChatSession.status == SessionStatus.active,
            )
        )
        count = result.scalar_one()
        assert count == 1

    async def test_creates_new_active_session(self, db: AsyncSession, user_and_doc: tuple) -> None:
        """create_new_session creates a new active session."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        session = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, session.id, "Hello", ChatRole.user)
        await db.flush()

        new_session = await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()

        assert new_session is not None
        assert new_session.status == SessionStatus.active


class TestListSessions:
    async def test_ordered_most_recent_first(self, db: AsyncSession, user_and_doc: tuple) -> None:
        """list_sessions returns sessions ordered most-recent first."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        # Create first session with a message, then create a new one
        s1 = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, s1.id, "First", ChatRole.user)
        await db.flush()

        await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()

        sessions = await chat_session_service.list_sessions(db, user.id, doc.id)

        assert len(sessions) >= 2
        # Most recent first — active session should come first
        assert sessions[0].status == SessionStatus.active

    async def test_labels_computed_correctly(self, db: AsyncSession, user_and_doc: tuple) -> None:
        """list_sessions returns 'Current Chat' for active, date label for archived."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        s1 = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, s1.id, "Hi", ChatRole.user)
        await db.flush()

        await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()

        sessions = await chat_session_service.list_sessions(db, user.id, doc.id)

        active = next(s for s in sessions if s.status == SessionStatus.active)
        archived = next(s for s in sessions if s.status == SessionStatus.archived)

        assert active.label == "Current Chat"
        assert archived.label.startswith("Chat \u2014 ")

    async def test_current_chat_label_for_active_session(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """The active session has label 'Current Chat'."""
        from writer.services import chat_session_service

        user, doc = user_and_doc

        await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()

        sessions = await chat_session_service.list_sessions(db, user.id, doc.id)

        assert len(sessions) == 1
        assert sessions[0].label == "Current Chat"


class TestActivateSession:
    async def test_archives_previous_active_session(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """activate_session archives the currently active session."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        s1 = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, s1.id, "Hi", ChatRole.user)
        await db.flush()

        s2 = await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()
        assert s2 is not None

        # Reactivate the first session
        reactivated = await chat_session_service.activate_session(db, user.id, s1.id)
        await db.flush()

        assert reactivated.status == SessionStatus.active
        await db.refresh(s2)
        assert s2.status == SessionStatus.archived

    async def test_raises_on_wrong_user_id(self, db: AsyncSession, user_and_doc: tuple) -> None:
        """activate_session raises ValueError when session belongs to a different user."""
        from writer.services import chat_session_service

        user, doc = user_and_doc

        s = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()

        other_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        with pytest.raises(ValueError):
            await chat_session_service.activate_session(db, other_user_id, s.id)

    async def test_raises_on_invalid_session_id(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """activate_session raises ValueError when session_id does not exist."""
        import uuid as _uuid

        from writer.services import chat_session_service

        user, doc = user_and_doc
        fake_id = _uuid.uuid4()

        with pytest.raises(ValueError):
            await chat_session_service.activate_session(db, user.id, fake_id)

    async def test_get_session_messages_returns_correct_messages(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """get_session_messages returns only messages for the given session."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        s1 = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, s1.id, "Session 1 msg", ChatRole.user)
        await db.flush()

        s2 = await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()
        assert s2 is not None
        await create_chat_message(db, doc.id, user.id, s2.id, "Session 2 msg", ChatRole.user)
        await db.flush()

        msgs = await chat_session_service.get_session_messages(db, s1.id, user.id)

        assert len(msgs) == 1
        assert msgs[0].content == "Session 1 msg"


class TestSessionPersistence:
    async def test_sessions_persist_across_reconnect(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """Sessions and messages persist after closing and reopening db connection."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        s = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, s.id, "Persistent msg", ChatRole.user)
        await db.flush()

        # Expire all objects to simulate a new session read
        db.expire_all()

        sessions = await chat_session_service.list_sessions(db, user.id, doc.id)
        assert len(sessions) == 1
        assert sessions[0].id == s.id

    async def test_get_or_create_returns_same_active_session_on_second_call(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """get_or_create_active_session returns the same session on repeated calls."""
        from writer.services import chat_session_service

        user, doc = user_and_doc

        s1 = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        s2 = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)

        assert s1.id == s2.id

    async def test_list_sessions_returns_all_archived_sessions_after_reconnect(
        self, db: AsyncSession, user_and_doc: tuple
    ) -> None:
        """list_sessions returns all archived sessions after reconnect."""
        from writer.models.enums import ChatRole
        from writer.services import chat_session_service
        from writer.services.chat_service import create_chat_message

        user, doc = user_and_doc

        s1 = await chat_session_service.get_or_create_active_session(db, user.id, doc.id)
        await db.flush()
        await create_chat_message(db, doc.id, user.id, s1.id, "First", ChatRole.user)
        await db.flush()

        await chat_session_service.create_new_session(db, user.id, doc.id)
        await db.flush()

        db.expire_all()

        sessions = await chat_session_service.list_sessions(db, user.id, doc.id)
        archived = [s for s in sessions if s.status == SessionStatus.archived]
        assert len(archived) >= 1
