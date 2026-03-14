"""Planner agent — produces an overview paragraph and ToC from a topic and research sources."""

import os

from google.adk.agents import Agent

from writer.core.config import settings

if settings.gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

planner_agent = Agent(
    name="planner",
    model=settings.gemini_model,
    instruction=(
        "You are a document planning assistant. You receive a document overview and research "
        "sources in session state.\n\n"
        "Session state keys:\n"
        "- overview: the user's description of their document\n"
        "- research_sources: summaries of relevant sources found during research\n\n"
        "Produce a response in exactly this format:\n\n"
        "## Overview\n"
        "[A single clear paragraph describing what the document will cover and its purpose]\n\n"
        "## Table of Contents\n"
        "1. [Section title] — [one-line description]\n"
        "2. [Section title] — [one-line description]\n"
        "... (4–8 sections total)\n\n"
        "Base the plan on both the overview and the research sources. Be specific and concrete."
    ),
)
