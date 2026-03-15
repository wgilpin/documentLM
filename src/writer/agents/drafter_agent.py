"""Drafter sub-agent — rewrites or expands selected text based on user instruction."""

from collections.abc import Callable

from google.adk.agents import Agent

from writer.core.config import settings

_INSTRUCTION = (
    "You are a writing assistant. The user has selected a passage from their document and "
    "provided an instruction for how to change it.\n\n"
    "You have access to the full document and a set of research sources via tools.\n\n"
    "Use list_sources to see what sources are available, and get_source to read one.\n\n"
    "Respond with ONLY the replacement text — no preamble, no explanation, no quotes. "
    "The replacement text will be substituted directly into the document."
)


def make_drafter_agent(tools: list[Callable] | None = None) -> Agent:  # type: ignore[type-arg]
    """Create a drafter Agent instance with optional per-request tools."""
    return Agent(
        name="drafter",
        model=settings.gemini_model,
        instruction=_INSTRUCTION,
        tools=tools or [],
    )
