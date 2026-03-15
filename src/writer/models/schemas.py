"""Pydantic v2 request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from writer.models.enums import (
    ChatRole,
    CommentStatus,
    IndexingStatus,
    SourceType,
    SuggestionStatus,
)


class DocumentCreate(BaseModel):
    title: str
    content: str = ""
    overview: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    content: str
    overview: str | None
    created_at: datetime
    updated_at: datetime


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    updated_at: datetime


class SourceCreate(BaseModel):
    document_id: uuid.UUID
    source_type: SourceType
    title: str
    content: str = ""
    url: str | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    source_type: SourceType
    title: str
    content: str
    url: str | None
    indexing_status: IndexingStatus
    error_message: str | None
    created_at: datetime


class CommentCreate(BaseModel):
    document_id: uuid.UUID
    selection_start: int
    selection_end: int
    selected_text: str
    body: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    selection_start: int
    selection_end: int
    selected_text: str
    body: str
    status: CommentStatus
    created_at: datetime


class SuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    comment_id: uuid.UUID
    original_text: str
    suggested_text: str
    status: SuggestionStatus
    created_at: datetime


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    role: ChatRole
    content: str
    created_at: datetime
