"""ADK agent orchestration service."""

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
