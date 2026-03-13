"""Drafter sub-agent — rewrites or expands selected text based on user instruction."""

from google.adk.agents import Agent

from writer.core.config import settings

drafter_agent = Agent(
    name="drafter",
    model=settings.gemini_model,
    instruction=(
        "You are a writing assistant. You receive a text selection that the user wants to improve, "
        "along with their instruction and grounding context from trusted sources.\n\n"
        "The session state contains:\n"
        "- selected_text: the text the user highlighted\n"
        "- surrounding_context: 500 chars before and after the selection\n"
        "- user_instruction: what the user wants done to the selected text\n"
        "- core_sources: concatenated text from the user's trusted source materials\n\n"
        "Respond with ONLY the replacement text — no preamble, no explanation, no quotes. "
        "The replacement text will be substituted directly into the document."
    ),
)
