"""Shared enum definitions used by both ORM models and Pydantic schemas."""

import enum


class SourceType(enum.Enum):
    url = "url"
    pdf = "pdf"
    note = "note"


class CommentStatus(enum.Enum):
    open = "open"
    resolved = "resolved"


class SuggestionStatus(enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    stale = "stale"


class ChatRole(enum.Enum):
    user = "user"
    assistant = "assistant"
