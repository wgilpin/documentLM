"""Chat agent — conversational brainstorming about the document."""

import os

from google.adk.agents import Agent

from writer.core.config import settings

if settings.gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

chat_agent = Agent(
    name="chat",
    model=settings.gemini_model,
    instruction=(
        "You are a creative writing collaborator. The user is working on a document and wants "
        "to brainstorm, explore ideas, or discuss themes with you.\n\n"
        "You receive the conversation history as context. Respond conversationally — ask "
        "follow-up questions, offer perspectives, suggest directions. Do NOT produce formatted "
        "document edits or replacement text. Be concise but thoughtful."
    ),
)
