"""Root coordinator agent — dispatches margin-comment requests to sub-agents."""

from google.adk.agents import Agent

from writer.agents.drafter_agent import drafter_agent
from writer.core.config import settings

root_agent = Agent(
    name="root",
    model=settings.gemini_model,
    instruction=(
        "You are the root coordinator for an AI document workbench. "
        "When a user submits a margin comment requesting a text change, "
        "delegate to the drafter sub-agent to produce the replacement text."
    ),
    sub_agents=[drafter_agent],
)
