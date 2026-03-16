"""Chat agent — conversational collaborator that can also edit the document."""

import os
from collections.abc import Callable, Sequence
from typing import Any

from google.adk.agents import Agent

from writer.core.config import settings

if settings.gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

_INSTRUCTION = (
    "You are a creative writing collaborator. The user is working on a document and wants "
    "to brainstorm, explore ideas, discuss themes, or get help writing.\n\n"
    "The current document content is provided in the session state under 'document_content'.\n\n"
    "When the user asks you to make changes to the document — rewrite sections, add content, "
    "fix phrasing, or apply the plan you produced — use the edit_document tool EXACTLY ONCE "
    "with the complete new document content as a single string. Never call edit_document "
    "multiple times.\n\n"
    "IMPORTANT — applying an outline vs. drafting:\n"
    "- 'Apply the outline', 'use that structure', 'set up the sections' = copy the headings "
    "and section titles into the document as a skeleton. Leave each section body empty or with "
    "a one-line placeholder like '[content here]'. Do NOT write full prose.\n"
    "- 'Write the section', 'draft this part', 'fill in the content' = write prose for that "
    "specific section only.\n"
    "- 'Write the full document' = write all sections in full.\n\n"
    "Respond conversationally. When you edit the document, briefly describe what you changed."
)


def make_chat_agent(tools: Sequence[Callable[..., Any]] | None = None) -> Agent:
    """Create a ChatAgent instance, optionally with per-request tools."""
    return Agent(
        name="chat",
        model=settings.gemini_model,
        instruction=_INSTRUCTION,
        tools=list(tools) if tools else [],
    )
