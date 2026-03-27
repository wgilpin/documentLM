"""Drafter sub-agent — rewrites or expands selected text based on user instruction."""

from collections.abc import Callable, Sequence
from typing import Any

from google.adk.agents import Agent

from writer.core.config import settings

_INSTRUCTION = (
    "You are a writing assistant. The user has selected a passage from their document and "
    "provided an instruction for how to change it.\n\n"
    "Relevant source excerpts are provided in the prompt. If you need additional background "
    "on a specific topic to fulfil the instruction well, call find_more_sources with a focused "
    "search query before writing your response.\n\n"
    "Respond with ONLY the replacement text — no preamble, no explanation, no quotes. "
    "The replacement text will be substituted directly into the document in place of the selected passage. "
    "Ensure the replacement fits naturally with the surrounding content: match the tone, style, "
    "and structure (e.g. if the selection is a list item, keep the result consistent with the other items in that list)."
)


def make_drafter_agent(tools: Sequence[Callable[..., Any]] | None = None) -> Agent:
    """Create a drafter Agent instance with optional per-request tools."""
    return Agent(
        name="drafter",
        model=settings.gemini_model,
        instruction=_INSTRUCTION,
        tools=list(tools) if tools else [],
    )
