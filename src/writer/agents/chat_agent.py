"""Chat agent — conversational collaborator that can also edit the document."""

import os
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from google.adk.agents import Agent

from writer.core.config import settings

if TYPE_CHECKING:
    from writer.models.schemas import UserSettingsResponse

if settings.gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

_LANGUAGES: dict[str, str] = {
    "en": "English",
    "en-GB": "English (UK)",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
    "ar": "Arabic",
}

_INSTRUCTION = (
    "You are a creative writing collaborator. The user is working on a document and wants "
    "to brainstorm, explore ideas, discuss themes, or get help writing.\n\n"
    "The current document content is provided in the session state under 'document_content'.\n\n"
    "ONLY use the edit_document tool when the user gives an explicit instruction to change the "
    "document — e.g. 'rewrite the intro', 'add a section', 'fix the phrasing', 'apply the plan'. "
    "Questions, brainstorming, 'what do you think?', 'can you explain...', 'tell me about...' — "
    "these are NEVER an invitation to edit the document. Answer them conversationally and leave "
    "the document untouched. When you do edit, call edit_document EXACTLY ONCE with the complete "
    "new document content as a single string. Never call edit_document multiple times.\n\n"
    "IMPORTANT — applying an outline vs. drafting:\n"
    "- 'Apply the outline', 'use that structure', 'set up the sections' = copy the headings "
    "and section titles into the document as a skeleton. Leave each section body empty or with "
    "a one-line placeholder like '[content here]'. Do NOT write full prose.\n"
    "- 'Write the section', 'draft this part', 'fill in the content' = write prose for that "
    "specific section only.\n"
    "- 'Write the full document' = write all sections in full.\n\n"
    "When you need more background on a specific topic or subtopic to give the user a better "
    "answer, call find_more_sources with a focused search query. The tool will search for, "
    "fetch, and index relevant sources so they become available as context. Only call it when "
    "the existing sources are clearly insufficient — not on every turn.\n\n"
    "The prompt may include two context sections:\n"
    "- SOURCES FOR THIS DOCUMENT: material the user has explicitly added as sources. Use this "
    "freely.\n"
    "- OTHER INFORMATION: material from the user's other projects. Treat this as background "
    "noise. Do NOT cite it, summarise it, or let it shape your answer unless the user "
    "explicitly asks about that specific topic. If in doubt, ignore it.\n\n"
    "Respond conversationally. When you edit the document, briefly describe what you changed."
)


def _build_settings_suffix(user_settings: "UserSettingsResponse") -> str:
    """Build an instruction suffix from saved user settings."""
    parts: list[str] = []
    if user_settings.display_name:
        parts.append(f"The user's name is {user_settings.display_name}.")
    lang_code = user_settings.language_code
    if lang_code and lang_code != "en":
        lang_name = _LANGUAGES.get(lang_code, lang_code)
        parts.append(f"Respond in {lang_name} ({lang_code}).")
    if user_settings.ai_instructions:
        parts.append(user_settings.ai_instructions)
    return "\n\n" + "\n".join(parts) if parts else ""


def make_chat_agent(
    tools: Sequence[Callable[..., Any]] | None = None,
    user_settings: "UserSettingsResponse | None" = None,
) -> Agent:
    """Create a ChatAgent instance, optionally with per-request tools and user settings."""
    instruction = _INSTRUCTION
    if user_settings is not None:
        instruction += _build_settings_suffix(user_settings)
    return Agent(
        name="chat",
        model=settings.gemini_model,
        instruction=instruction,
        tools=list(tools) if tools else [],
    )
