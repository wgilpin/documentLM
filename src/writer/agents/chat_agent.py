"""Chat agent — conversational collaborator that can also edit the document."""

import os
from collections.abc import Callable

from google.adk.agents import Agent

from writer.core.config import settings

if settings.gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

_INSTRUCTION = (
    "You are a creative writing collaborator. The user is working on a document and wants "
    "to brainstorm, explore ideas, discuss themes, or get help writing.\n\n"
    "The current document content is provided in the session state under 'document_content'.\n\n"
    "When the user asks you to make changes to the document — rewrite sections, add content, "
    "fix phrasing, or apply the plan you produced — use the edit_document tool with the "
    "complete new document content.\n\n"
    "Respond conversationally. When you edit the document, briefly describe what you changed."
)


def make_chat_agent(tools: list[Callable] | None = None) -> Agent:  # type: ignore[type-arg]
    """Create a ChatAgent instance, optionally with per-request tools."""
    return Agent(
        name="chat",
        model=settings.gemini_model,
        instruction=_INSTRUCTION,
        tools=tools or [],
    )
