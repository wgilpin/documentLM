"""Chat service — create, list, and process chat messages for the meta-chat panel."""

import asyncio
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from google.adk.runners import Runner

if TYPE_CHECKING:
    from writer.models.schemas import UserSettingsResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import ChatMessage
from writer.models.enums import ChatRole, SourceType
from writer.models.schemas import ChatMessageResponse, SourceCreate
from writer.services import vector_store

logger = get_logger(__name__)

_APP_NAME = "writer-chat"


async def create_chat_message(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    role: ChatRole,
) -> ChatMessageResponse:
    """Persist a single chat message and return the response schema."""
    orm = ChatMessage(document_id=document_id, user_id=user_id, role=role, content=content)
    db.add(orm)
    await db.flush()
    await db.refresh(orm)
    return ChatMessageResponse.model_validate(orm)


async def list_chat_messages(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[ChatMessageResponse]:
    """Return all chat messages for a document ordered oldest-first."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.document_id == document_id, ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at)
    )
    return [ChatMessageResponse.model_validate(m) for m in result.scalars().all()]


def make_find_more_sources_tool(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    db: "AsyncSession",
) -> tuple[Callable[..., Any], Callable[[], bool]]:
    """Return (tool, was_called) where was_called() is True after any successful source fetch."""
    _called = [False]

    async def find_more_sources(query: str) -> str:
        """Search for and index additional sources relevant to the given query.

        Call this when you need more background on a specific topic or subtopic
        and the existing sources are insufficient.

        Args:
            query: The topic or question to find sources about.

        Returns:
            A summary of the sources found and indexed.
        """
        from writer.models.enums import SourceType
        from writer.models.schemas import SourceCreate
        from writer.services import agent_service, source_service
        from writer.services.content_fetcher import fetch_url_content

        logger.info("find_more_sources called: query=%r document=%s", query[:100], document_id)

        raw_sources = await agent_service.invoke_research_agent(query, user_id)
        if not raw_sources:
            logger.info("find_more_sources: no sources returned for query=%r", query[:80])
            return "No additional sources found for that query."

        from writer.services.indexer import run_indexing

        saved_titles: list[str] = []
        for s in raw_sources:
            url = s.get("url")
            if url:
                try:
                    content = await fetch_url_content(url)
                except Exception as exc:
                    logger.warning("find_more_sources: failed to fetch %s: %s", url, exc)
                    content = s.get("summary", "")
            else:
                content = s.get("summary", "")

            saved = await source_service.add_source(
                db,
                SourceCreate(
                    document_id=document_id,
                    source_type=SourceType.url,
                    title=s.get("title", "Source"),
                    content=content,
                    url=url,
                ),
                user_id,
            )
            await db.flush()
            await run_indexing(source_id=saved.id, db=db, user_id=user_id)
            saved_titles.append(s.get("title") or url or "Unknown")

        _called[0] = True
        summary = f"Found and indexed {len(saved_titles)} source(s): {', '.join(saved_titles[:5])}"
        logger.info("find_more_sources: %s", summary)
        return summary

    return find_more_sources, lambda: _called[0]


async def invoke_chat_agent(
    history: list[ChatMessageResponse],
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    is_private_doc: bool = False,
    document_content: str = "",
    user_settings: "UserSettingsResponse | None" = None,
    extra_tools: "list[Callable[..., Any]] | None" = None,
) -> tuple[str, str | None]:
    """Invoke the ChatAgent with the full conversation history and return (reply_text, new_content).

    new_content is non-None only when the agent called the edit_document tool.
    """
    from writer.agents.chat_agent import make_chat_agent

    # Closure that captures the edit result
    edited: list[str | None] = [None]

    edit_call_count = [0]

    def edit_document(new_content: str) -> str:
        """Replace the entire document content with new_content.

        Args:
            new_content: The complete new text for the document.

        Returns:
            Confirmation that the document was updated.
        """
        edit_call_count[0] += 1
        logger.info(
            "edit_document called (call #%d, content len=%d): %r",
            edit_call_count[0],
            len(new_content),
            new_content[:200],
        )
        edited[0] = new_content
        return "Document updated."

    agent = make_chat_agent(
        tools=[edit_document] + (extra_tools or []), user_settings=user_settings
    )

    adk_user_id = str(user_id)
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=_APP_NAME,
        user_id=adk_user_id,
        state={"document_content": document_content},
    )

    runner = Runner(
        agent=agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    # Build a self-contained prompt with full context so the agent never loses history
    prompt_parts: list[str] = []
    md_content = document_content

    if md_content:
        prompt_parts.append(f"--- CURRENT DOCUMENT ---\n{md_content}\n--- END DOCUMENT ---")

    last_user_content = next((m.content for m in reversed(history) if m.role == ChatRole.user), "")

    if last_user_content:
        chunks = await asyncio.to_thread(
            vector_store.query_sources,
            last_user_content,
            user_id,
            document_id,
            is_private_doc,
        )
        logger.info("chat: injecting %d source chunks into context", len(chunks))
        if chunks:
            source_block = "\n".join(chunks)
            prompt_parts.append(f"--- RELEVANT SOURCES ---\n{source_block}\n--- END SOURCES ---")

    prior_turns = history[:-1]  # everything except the new user message at the end
    if prior_turns:
        formatted = "\n\n".join(
            f"{'USER' if m.role == ChatRole.user else 'ASSISTANT'}: {m.content}"
            for m in prior_turns
        )
        prompt_parts.append(f"--- CONVERSATION HISTORY ---\n{formatted}\n--- END HISTORY ---")

    prompt_parts.append(f"USER: {last_user_content}")

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text="\n\n".join(prompt_parts))],
    )

    logger.info("Invoking ChatAgent with %d history turns", len(history))

    reply_text: str | None = None
    event_count = 0
    try:
        async for event in runner.run_async(
            user_id=adk_user_id,
            session_id=session.id,
            new_message=user_message,
        ):
            event_count += 1
            author = getattr(event, "author", "unknown")
            is_final = event.is_final_response()
            # Log function calls
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        logger.info(
                            "ChatAgent event #%d author=%s function_call=%s args_keys=%s",
                            event_count,
                            author,
                            fc.name,
                            list((fc.args or {}).keys()),
                        )
                    elif part.text:
                        logger.info(
                            "ChatAgent event #%d author=%s is_final=%s text=%r",
                            event_count,
                            author,
                            is_final,
                            part.text[:120],
                        )
            else:
                logger.info(
                    "ChatAgent event #%d author=%s is_final=%s (no parts)",
                    event_count,
                    author,
                    is_final,
                )
            if is_final:
                if event.content and event.content.parts:
                    reply_text = event.content.parts[0].text
                break
    except Exception as exc:
        logger.error("ChatAgent invocation failed: %s", exc)
        raise RuntimeError(f"ChatAgent invocation failed: {exc}") from exc

    if reply_text is None:
        raise ValueError("ChatAgent returned no text response")

    logger.info("ChatAgent response received (edited=%s)", edited[0] is not None)
    return reply_text, edited[0]


async def process_chat(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    history: list[ChatMessageResponse],
    document_content: str = "",
    is_private_doc: bool = False,
) -> tuple[ChatMessageResponse, str | None, bool]:
    """Call the ChatAgent with history; return (assistant_msg, new_content, sources_added).

    new_content is non-None when the agent edited the document.
    sources_added is True when the agent called find_more_sources successfully.
    """
    from writer.models.schemas import DocumentUpdate
    from writer.services import document_service, settings_service

    user_settings = await settings_service.get_settings(db, user_id)
    find_more_sources, sources_were_added = make_find_more_sources_tool(document_id, user_id, db)

    try:
        reply_text, new_content = await invoke_chat_agent(
            history,
            document_id,
            user_id,
            is_private_doc,
            document_content,
            user_settings,
            extra_tools=[find_more_sources],
        )
    except Exception as exc:
        logger.error("ChatAgent error for document=%s: %s", document_id, exc)
        raise

    if new_content is not None:
        await document_service.update_document(
            db, document_id, DocumentUpdate(content=new_content), user_id
        )
        logger.info("ChatAgent edited document=%s", document_id)

    msg = await create_chat_message(db, document_id, user_id, reply_text, ChatRole.assistant)
    return msg, new_content, sources_were_added()


async def initialize_chat_with_overview(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    overview: str,
) -> list[ChatMessageResponse]:
    """Seed the chat on first open.

    1. Invokes the research agent to find relevant sources.
    2. Fetches real content from each URL and saves them as Source records.
    3. Invokes the planner agent (overview + sources) to produce an overview paragraph + ToC.
    4. Persists the overview as a user message and the plan as the assistant reply.
    """
    from writer.services import agent_service, source_service
    from writer.services.content_fetcher import fetch_url_content

    # 1. Research
    logger.info("Initializing chat with overview for document=%s", document_id)
    raw_sources = await agent_service.invoke_research_agent(overview, user_id)

    # 2. Fetch content + save sources
    saved_sources = []
    for s in raw_sources:
        url = s.get("url")
        if url:
            try:
                content = await fetch_url_content(url)
                logger.info("Fetched content for url=%s (len=%d)", url, len(content))
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s — using agent summary", url, exc)
                content = s.get("summary", "")
        else:
            content = s.get("summary", "")

        source = await source_service.add_source(
            db,
            SourceCreate(
                document_id=document_id,
                source_type=SourceType.url,
                title=s.get("title", "Source"),
                content=content,
                url=url,
            ),
            user_id,
        )
        saved_sources.append(source)

    logger.info("Saved %d research sources for document=%s", len(saved_sources), document_id)

    # 3. Plan
    plan_text = await agent_service.invoke_planner(overview, saved_sources, document_id, user_id)

    # 4. Persist chat messages
    user_msg = await create_chat_message(db, document_id, user_id, overview, ChatRole.user)
    assistant_msg = await create_chat_message(
        db, document_id, user_id, plan_text, ChatRole.assistant
    )

    logger.info("Chat initialized for document=%s", document_id)
    return [user_msg, assistant_msg]
