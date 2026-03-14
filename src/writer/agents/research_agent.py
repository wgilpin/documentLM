"""Research agent — finds high-quality sources for a document topic."""

import os

from google.adk.agents import Agent
from google.adk.tools import google_search

from writer.core.config import settings

if settings.gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

research_agent = Agent(
    name="researcher",
    model=settings.gemini_model,
    tools=[google_search],
    instruction=(
        "You are a research assistant. The user is starting a new document and has provided "
        "an overview of what they want to write. Search for 3–5 high-quality, authoritative "
        "sources relevant to this topic.\n\n"
        "Return ONLY a JSON array (no other text) in this exact format:\n"
        '[{"title": "...", "url": "...", "summary": "2-3 sentence summary of the source"}]\n\n'
        "Choose reputable sources: academic papers, established publications, official sites. "
        "Ensure URLs are real and accessible."
    ),
)
