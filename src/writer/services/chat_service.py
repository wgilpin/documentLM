"""Chat service — create, list, and process chat messages for the meta-chat panel."""

import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import ChatMessage
from writer.models.enums import ChatRole
from writer.models.schemas import ChatMessageResponse

logger = get_logger(__name__)

_APP_NAME = "writer-chat"
_USER_ID = "default_user"


async def create_chat_message(
    db: AsyncSession,
    document_id: uuid.UUID,
    content: str,
    role: ChatRole,
) -> ChatMessageResponse:
    """Persist a single chat message and return the response schema."""
    orm = ChatMessage(document_id=document_id, role=role, content=content)
    db.add(orm)
    await db.flush()
    await db.refresh(orm)
    return ChatMessageResponse.model_validate(orm)


async def list_chat_messages(
    db: AsyncSession,
    document_id: uuid.UUID,
) -> list[ChatMessageResponse]:
    """Return all chat messages for a document ordered oldest-first."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.document_id == document_id)
        .order_by(ChatMessage.created_at)
    )
    return [ChatMessageResponse.model_validate(m) for m in result.scalars().all()]


async def invoke_chat_agent(history: list[ChatMessageResponse]) -> str:
    """Invoke the ChatAgent with the full conversation history and return the reply text."""
    from writer.agents.chat_agent import chat_agent

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id=_USER_ID)

    runner = Runner(
        agent=chat_agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    # Build the latest user message (the last turn in history)
    last_user_content = next((m.content for m in reversed(history) if m.role == ChatRole.user), "")
    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=last_user_content)],
    )

    logger.info("Invoking ChatAgent with %d history turns", len(history))

    reply_text: str | None = None
    try:
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=user_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    reply_text = event.content.parts[0].text
                break
    except Exception as exc:
        logger.error("ChatAgent invocation failed: %s", exc)
        raise RuntimeError(f"ChatAgent invocation failed: {exc}") from exc

    if reply_text is None:
        raise ValueError("ChatAgent returned no text response")

    logger.info("ChatAgent response received")
    return reply_text


async def process_chat(
    db: AsyncSession,
    document_id: uuid.UUID,
    history: list[ChatMessageResponse],
) -> ChatMessageResponse:
    """Call the ChatAgent with history and persist + return the assistant reply."""
    try:
        reply_text = await invoke_chat_agent(history)
    except Exception as exc:
        logger.error("ChatAgent error for document=%s: %s", document_id, exc)
        raise

    return await create_chat_message(db, document_id, reply_text, ChatRole.assistant)
