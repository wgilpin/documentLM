"""ADK agent orchestration service.

invoke_research_agent is re-exported from documentlm_core.
invoke_drafter and invoke_planner are writer-specific and use the core
run_agent_text helper with writer-specific message formatting.
"""

import asyncio
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.services.agent_service import (  # noqa: F401
    invoke_research_agent,
    run_agent_text,
)

from writer.core.logging import get_logger
from writer.models.schemas import CommentResponse, DocumentResponse, SourceResponse
from writer.services import vector_store

logger = get_logger(__name__)

_APP_NAME = "writer"


async def invoke_drafter(
    comment: CommentResponse,
    document: DocumentResponse,
    sources: list[SourceResponse],
    user_id: uuid.UUID,
    db: "AsyncSession | None" = None,
) -> str:
    """Invoke the Drafter agent and return its text response."""
    from writer.agents.drafter_agent import make_drafter_agent
    from writer.services.chat_service import make_find_more_sources_tool

    tools = []
    if db is not None:
        find_more_sources, _ = make_find_more_sources_tool(document.id, user_id, db)
        tools.append(find_more_sources)

    agent = make_drafter_agent(tools=tools)

    query_text = f"{comment.body} {comment.selected_text}"
    chunks = await asyncio.to_thread(
        vector_store.query_sources,
        query_text,
        user_id,
        document.id,
        document.is_private,
    )
    logger.info("drafter: injecting %d source chunks into context", len(chunks))

    doc_content = document.content or ""
    source_block = "\n".join(chunks)

    ctx_window = 300
    sel_start = comment.selection_start or 0
    sel_end = comment.selection_end or len(doc_content)
    before = doc_content[max(0, sel_start - ctx_window) : sel_start]
    after = doc_content[sel_end : sel_end + ctx_window]

    message_text = (
        f"--- FULL DOCUMENT ---\n{doc_content}\n--- END DOCUMENT ---\n\n"
        f"--- RELEVANT SOURCE CHUNKS ---\n{source_block}\n--- END SOURCE CHUNKS ---\n\n"
        f"--- INSERTION CONTEXT ---\n"
        f"The selected text appears at this position in the document:\n"
        f"...{before}[SELECTED]{after}...\n"
        f"--- END INSERTION CONTEXT ---\n\n"
        f"Selected text:\n{comment.selected_text}\n\n"
        f"Instruction: {comment.body}"
    )

    logger.info(
        "Invoking drafter for comment=%s doc=%s | selected=%r instruction=%r",
        comment.id,
        comment.document_id,
        comment.selected_text[:80] if comment.selected_text else None,
        comment.body[:120],
    )

    return await run_agent_text(agent, message_text, user_id, app_name=_APP_NAME)


async def invoke_planner(
    overview: str,
    sources: list[SourceResponse],
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str:
    """Invoke the Planner agent with an overview and research sources."""
    from writer.agents.planner_agent import planner_agent

    chunks = await asyncio.to_thread(
        vector_store.query_sources, overview, user_id, document_id, False, 5
    )
    logger.info("planner: injecting %d source chunks into context", len(chunks))
    research_sources = "\n".join(chunks)

    session_state = {
        "overview": overview,
        "research_sources": research_sources,
    }

    logger.info(
        "Invoking PlannerAgent with %d sources (overview len=%d)",
        len(sources),
        len(overview),
    )

    return await run_agent_text(
        planner_agent,
        overview,
        user_id,
        app_name=_APP_NAME,
        session_state=session_state,
    )
