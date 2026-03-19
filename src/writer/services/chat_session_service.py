"""Chat session service — create, list, and manage chat sessions."""

import uuid
from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import ChatMessage, ChatSession
from writer.models.enums import SessionStatus
from writer.models.schemas import ChatMessageResponse, ChatSessionResponse

logger = get_logger(__name__)


def _session_label(session: ChatSession) -> str:
    """Compute the display label for a session."""
    if session.status == SessionStatus.active:
        return "Current Chat"
    dt = session.created_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"Chat \u2014 {dt.strftime('%b')} {dt.day}, {dt.year} {hour}:{dt.minute:02d} {ampm}"


def _to_response(session: ChatSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=session.id,
        document_id=session.document_id,
        status=session.status,
        created_at=session.created_at,
        label=_session_label(session),
    )


async def get_or_create_active_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> ChatSession:
    """Return current active session, creating one if none exists."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.document_id == document_id,
            ChatSession.status == SessionStatus.active,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    session = ChatSession(
        user_id=user_id,
        document_id=document_id,
        status=SessionStatus.active,
    )
    db.add(session)
    await db.flush()
    logger.info(
        "Created new active session=%s for doc=%s user=%s", session.id, document_id, user_id
    )
    return session


async def create_new_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> ChatSession | None:
    """Archive current active session (if it has messages) and create a new active one.

    Returns the new session, or None if current session was empty (no-op).
    """
    current = await get_or_create_active_session(db, user_id, document_id)

    if not await session_has_messages(db, current.id):
        logger.info("create_new_session: current session=%s is empty — no-op", current.id)
        return None

    # Archive the current session and flush before inserting new active session
    current.status = SessionStatus.archived
    db.add(current)
    await db.flush()  # flush archive before inserting new active to avoid unique index violation
    logger.info("Archived session=%s for doc=%s user=%s", current.id, document_id, user_id)

    # Create a fresh active session
    new_session = ChatSession(
        user_id=user_id,
        document_id=document_id,
        status=SessionStatus.active,
    )
    db.add(new_session)
    await db.flush()
    logger.info("Created new session=%s for doc=%s user=%s", new_session.id, document_id, user_id)
    return new_session


async def session_has_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> bool:
    """Check whether a session has any messages."""
    result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
    )
    return result.scalar_one() > 0


async def list_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> list[ChatSessionResponse]:
    """Return all sessions ordered most-recent first, with computed labels."""
    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.user_id == user_id,
            ChatSession.document_id == document_id,
        )
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [_to_response(s) for s in sessions]


async def activate_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> ChatSession:
    """Set given session to active, archiving the previously active session.

    Raises ValueError if session not found or doesn't belong to user.
    """
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    target = result.scalar_one_or_none()

    if target is None:
        raise ValueError(f"Session {session_id} not found")
    if target.user_id != user_id:
        raise ValueError(f"Session {session_id} does not belong to user {user_id}")

    if target.status == SessionStatus.active:
        return target

    # Archive current active session (if any)
    active_result = await db.execute(
        select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.document_id == target.document_id,
            ChatSession.status == SessionStatus.active,
        )
    )
    current_active = active_result.scalar_one_or_none()
    if current_active is not None:
        current_active.status = SessionStatus.archived
        db.add(current_active)
        await db.flush()  # flush archive before activating to avoid unique index violation
        logger.info("Archived session=%s during activate", current_active.id)

    target.status = SessionStatus.active
    db.add(target)
    await db.flush()
    logger.info("Activated session=%s for user=%s", session_id, user_id)
    return target


async def get_session_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[ChatMessageResponse]:
    """Return all messages for a session ordered oldest-first."""
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.user_id == user_id,
        )
        .order_by(ChatMessage.created_at)
    )
    return [ChatMessageResponse.model_validate(m) for m in result.scalars().all()]
