"""Snippet CRUD service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Document, Snippet, Source
from writer.models.schemas import SnippetCreate, SnippetResponse, SnippetUpdate

logger = get_logger(__name__)


class SnippetNotFoundError(Exception):
    def __init__(self, snippet_id: uuid.UUID) -> None:
        super().__init__(f"Snippet {snippet_id} not found")
        self.snippet_id = snippet_id


class DocumentNotFoundError(Exception):
    def __init__(self, document_id: uuid.UUID) -> None:
        super().__init__(f"Document {document_id} not found")
        self.document_id = document_id


async def create_snippet(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SnippetCreate,
) -> SnippetResponse:
    logger.info("create_snippet doc=%s user=%s", document_id, user_id)
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    if doc_result.scalar_one_or_none() is None:
        logger.error("create_snippet: document %s not found for user %s", document_id, user_id)
        raise DocumentNotFoundError(document_id)

    snippet = Snippet(
        document_id=document_id,
        user_id=user_id,
        source_id=data.source_id,
        text=data.text,
        char_offset=data.char_offset,
        note=data.note,
        tag=data.tag,
    )
    db.add(snippet)
    await db.flush()
    await db.refresh(snippet)
    logger.info("create_snippet: created snippet id=%s", snippet.id)
    return SnippetResponse.model_validate(snippet)


async def list_snippets(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SnippetResponse]:
    logger.info("list_snippets doc=%s user=%s", document_id, user_id)
    result = await db.execute(
        select(Snippet)
        .where(Snippet.document_id == document_id, Snippet.user_id == user_id)
        .order_by(Snippet.created_at.desc())
    )
    snippets = result.scalars().all()
    logger.info("list_snippets: found %d snippets", len(snippets))
    return [SnippetResponse.model_validate(s) for s in snippets]


async def delete_snippet(
    db: AsyncSession,
    snippet_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    logger.info("delete_snippet id=%s user=%s", snippet_id, user_id)
    result = await db.execute(
        select(Snippet).where(Snippet.id == snippet_id, Snippet.user_id == user_id)
    )
    snippet = result.scalar_one_or_none()
    if snippet is None:
        logger.error("delete_snippet: snippet %s not found for user %s", snippet_id, user_id)
        raise SnippetNotFoundError(snippet_id)
    await db.delete(snippet)
    await db.flush()
    logger.info("delete_snippet: deleted snippet id=%s", snippet_id)


async def update_snippet(
    db: AsyncSession,
    snippet_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SnippetUpdate,
) -> SnippetResponse:
    logger.info("update_snippet id=%s user=%s", snippet_id, user_id)
    result = await db.execute(
        select(Snippet).where(Snippet.id == snippet_id, Snippet.user_id == user_id)
    )
    snippet = result.scalar_one_or_none()
    if snippet is None:
        logger.error("update_snippet: snippet %s not found for user %s", snippet_id, user_id)
        raise SnippetNotFoundError(snippet_id)
    if data.note is not None:
        snippet.note = data.note
    if data.tag is not None:
        snippet.tag = data.tag
    await db.flush()
    await db.refresh(snippet)
    logger.info("update_snippet: updated snippet id=%s", snippet_id)
    return SnippetResponse.model_validate(snippet)


async def get_snippet_with_source_title(
    db: AsyncSession,
    snippet_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SnippetResponse:
    logger.info("get_snippet_with_source_title id=%s user=%s", snippet_id, user_id)
    result = await db.execute(
        select(Snippet).where(Snippet.id == snippet_id, Snippet.user_id == user_id)
    )
    snippet = result.scalar_one_or_none()
    if snippet is None:
        logger.error(
            "get_snippet_with_source_title: snippet %s not found for user %s", snippet_id, user_id
        )
        raise SnippetNotFoundError(snippet_id)

    source_title: str | None = None
    if snippet.source_id is not None:
        src_result = await db.execute(select(Source).where(Source.id == snippet.source_id))
        source = src_result.scalar_one_or_none()
        if source is not None:
            source_title = source.title

    response = SnippetResponse.model_validate(snippet)
    response.source_title = source_title
    logger.info(
        "get_snippet_with_source_title: snippet id=%s source_title=%r", snippet_id, source_title
    )
    return response
