"""ADK agent orchestration service."""

import asyncio
import json
import re

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from writer.core.logging import get_logger
from writer.models.schemas import CommentResponse, DocumentResponse, SourceResponse
from writer.services import vector_store

logger = get_logger(__name__)

_APP_NAME = "writer"
_USER_ID = "default_user"


async def invoke_drafter(
    comment: CommentResponse,
    document: DocumentResponse,
    sources: list[SourceResponse],
) -> str:
    """Invoke the Drafter agent and return its text response.

    Raises ValueError if no text response is returned.
    Raises RuntimeError on unexpected agent errors.
    """
    from writer.agents.drafter_agent import make_drafter_agent

    agent = make_drafter_agent(tools=[])

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id=_USER_ID, state={})

    runner = Runner(
        agent=agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    query_text = f"{comment.body} {comment.selected_text}"
    chunks = await asyncio.to_thread(vector_store.query_sources, query_text)
    logger.info("drafter: injecting %d source chunks into context", len(chunks))

    doc_content = document.content or ""
    source_block = "\n".join(chunks)
    message_text = (
        f"--- FULL DOCUMENT ---\n{doc_content}\n--- END DOCUMENT ---\n\n"
        f"--- RELEVANT SOURCE CHUNKS ---\n{source_block}\n--- END SOURCE CHUNKS ---\n\n"
        f"Selected text:\n{comment.selected_text}\n\n"
        f"Instruction: {comment.body}"
    )
    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message_text)],
    )

    logger.info(
        "Invoking drafter for comment=%s doc=%s | selected=%r instruction=%r",
        comment.id,
        comment.document_id,
        comment.selected_text[:80] if comment.selected_text else None,
        comment.body[:120],
    )

    suggested_text: str | None = None
    try:
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=user_message,
        ):
            agent_name = getattr(event, "author", None) or "unknown"
            if event.content and event.content.parts:
                part_text = event.content.parts[0].text or ""
                logger.info(
                    "Agent event author=%s is_final=%s text=%r",
                    agent_name,
                    event.is_final_response(),
                    part_text[:200],
                )
            else:
                logger.info(
                    "Agent event author=%s is_final=%s (no text parts)",
                    agent_name,
                    event.is_final_response(),
                )
            if event.is_final_response():
                if event.content and event.content.parts:
                    suggested_text = event.content.parts[0].text
                    logger.info(
                        "Final response from agent=%s for comment=%s: %r",
                        agent_name,
                        comment.id,
                        (suggested_text or "")[:200],
                    )
                break
    except Exception as exc:
        logger.exception("Agent invocation failed: %s", exc)
        raise RuntimeError(f"Agent invocation failed: {exc}") from exc

    if suggested_text is None:
        raise ValueError("Drafter agent returned no text response")

    return suggested_text


async def invoke_research_agent(
    overview: str, exclude_urls: list[str] | None = None
) -> list[dict]:  # type: ignore[type-arg]
    """Invoke the Research agent to find sources for the given overview.

    Returns a list of dicts with keys: title, url, summary.
    Returns an empty list if the agent response cannot be parsed as JSON.
    Pass exclude_urls to ask the agent to avoid already-found sources.
    """
    from writer.agents.research_agent import research_agent

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id=_USER_ID)

    runner = Runner(
        agent=research_agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    prompt = overview
    if exclude_urls:
        exclusion_list = "\n".join(f"- {u}" for u in exclude_urls)
        prompt = (
            f"{overview}\n\nDo NOT return any of these URLs — find different sources:\n{exclusion_list}"
        )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    logger.info("Invoking ResearchAgent for overview (len=%d)", len(overview))

    raw_text: str | None = None
    try:
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=user_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    raw_text = event.content.parts[0].text
                break
    except Exception as exc:
        logger.exception("ResearchAgent invocation failed: %s", exc)
        raise RuntimeError(f"ResearchAgent invocation failed: {exc}") from exc

    if raw_text is None:
        raise ValueError("ResearchAgent returned no text response")

    logger.info("ResearchAgent raw response (len=%d)", len(raw_text))

    try:
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        if match is None:
            raise ValueError("No JSON array found in response")
        sources: list[dict] = json.loads(match.group())  # type: ignore[type-arg]
        logger.info("ResearchAgent returned %d sources", len(sources))
        return sources
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to parse ResearchAgent JSON: %s — returning empty list", exc)
        return []


async def invoke_planner(overview: str, sources: list[SourceResponse]) -> str:
    """Invoke the Planner agent with an overview and research sources.

    Returns the plan text (overview paragraph + table of contents).
    """
    from writer.agents.planner_agent import planner_agent

    chunks = await asyncio.to_thread(vector_store.query_sources, overview, top_k=5)
    logger.info("planner: injecting %d source chunks into context", len(chunks))
    research_sources = "\n".join(chunks)

    session_state = {
        "overview": overview,
        "research_sources": research_sources,
    }

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, state=session_state
    )

    runner = Runner(
        agent=planner_agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=overview)],
    )

    logger.info(
        "Invoking PlannerAgent with %d sources (overview len=%d)",
        len(sources),
        len(overview),
    )

    plan_text: str | None = None
    try:
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=user_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    plan_text = event.content.parts[0].text
                break
    except Exception as exc:
        logger.exception("PlannerAgent invocation failed: %s", exc)
        raise RuntimeError(f"PlannerAgent invocation failed: {exc}") from exc

    if plan_text is None:
        raise ValueError("PlannerAgent returned no text response")

    logger.info("PlannerAgent response received (len=%d)", len(plan_text))
    return plan_text
