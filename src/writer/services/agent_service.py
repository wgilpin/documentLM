"""ADK agent orchestration service."""

import json
import re

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from writer.core.logging import get_logger
from writer.models.schemas import CommentResponse, DocumentResponse, SourceResponse

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
    from writer.agents.root_agent import root_agent

    surrounding_start = max(0, comment.selection_start - 500)
    surrounding_end = min(len(document.content), comment.selection_end + 500)
    surrounding_context = document.content[surrounding_start:surrounding_end]
    core_sources = "\n\n---\n\n".join(f"[{s.title}]\n{s.content}" for s in sources if s.content)

    session_state = {
        "selected_text": comment.selected_text,
        "surrounding_context": surrounding_context,
        "user_instruction": comment.body,
        "core_sources": core_sources,
    }

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, state=session_state
    )

    runner = Runner(
        agent=root_agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=comment.body)],
    )

    logger.info("Invoking drafter for comment=%s doc=%s", comment.id, comment.document_id)

    suggested_text: str | None = None
    try:
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=user_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    suggested_text = event.content.parts[0].text
                break
    except Exception as exc:
        logger.exception("Agent invocation failed: %s", exc)
        raise RuntimeError(f"Agent invocation failed: {exc}") from exc

    if suggested_text is None:
        raise ValueError("Drafter agent returned no text response")

    logger.info("Drafter response received for comment=%s", comment.id)
    return suggested_text


async def invoke_research_agent(overview: str) -> list[dict]:  # type: ignore[type-arg]
    """Invoke the Research agent to find sources for the given overview.

    Returns a list of dicts with keys: title, url, summary.
    Returns an empty list if the agent response cannot be parsed as JSON.
    """
    from writer.agents.research_agent import research_agent

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id=_USER_ID)

    runner = Runner(
        agent=research_agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=overview)],
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

    research_sources = "\n\n".join(
        f"[{s.title}]\n{s.content}" for s in sources if s.content
    )

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
