"""Snippet CRUD service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import ChapterSnippet, Document, Snippet, Source
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

    response = SnippetResponse.model_validate(snippet)
    if snippet.source_id is not None:
        src_result = await db.execute(select(Source).where(Source.id == snippet.source_id))
        source = src_result.scalar_one_or_none()
        if source is not None:
            response.source_title = source.title
    return response


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

    # Resolve source titles in one query
    source_ids = {s.source_id for s in snippets if s.source_id is not None}
    title_map: dict[uuid.UUID, str] = {}
    if source_ids:
        src_result = await db.execute(select(Source).where(Source.id.in_(source_ids)))
        for src in src_result.scalars().all():
            title_map[src.id] = src.title

    responses: list[SnippetResponse] = []
    for s in snippets:
        resp = SnippetResponse.model_validate(s)
        if s.source_id is not None:
            resp.source_title = title_map.get(s.source_id)
        responses.append(resp)
    return responses


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


async def assign_snippet_to_chapter(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    snippet_id: uuid.UUID,
) -> None:
    """Associate a snippet with a chapter (idempotent via merge)."""
    logger.info("assign_snippet_to_chapter chapter=%s snippet=%s", chapter_id, snippet_id)
    junction = ChapterSnippet(chapter_id=chapter_id, snippet_id=snippet_id)
    await db.merge(junction)
    await db.flush()
    logger.info("assign_snippet_to_chapter: assigned")


async def unassign_snippet_from_chapter(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    snippet_id: uuid.UUID,
) -> None:
    """Remove a snippet's association with a chapter."""
    logger.info("unassign_snippet_from_chapter chapter=%s snippet=%s", chapter_id, snippet_id)
    result = await db.execute(
        select(ChapterSnippet).where(
            ChapterSnippet.chapter_id == chapter_id,
            ChapterSnippet.snippet_id == snippet_id,
        )
    )
    junction = result.scalar_one_or_none()
    if junction is None:
        logger.info("unassign_snippet_from_chapter: no association found, noop")
        return
    await db.delete(junction)
    await db.flush()
    logger.info("unassign_snippet_from_chapter: removed")


async def list_snippets_by_chapter(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SnippetResponse]:
    """List snippets associated with a specific chapter."""
    logger.info("list_snippets_by_chapter chapter=%s user=%s", chapter_id, user_id)
    result = await db.execute(
        select(Snippet)
        .join(ChapterSnippet, Snippet.id == ChapterSnippet.snippet_id)
        .where(ChapterSnippet.chapter_id == chapter_id, Snippet.user_id == user_id)
        .order_by(Snippet.created_at.desc())
    )
    snippets = result.scalars().all()
    logger.info("list_snippets_by_chapter: found %d snippets", len(snippets))

    # Resolve source titles
    source_ids = {s.source_id for s in snippets if s.source_id is not None}
    title_map: dict[uuid.UUID, str] = {}
    if source_ids:
        src_result = await db.execute(select(Source).where(Source.id.in_(source_ids)))
        for src in src_result.scalars().all():
            title_map[src.id] = src.title

    responses: list[SnippetResponse] = []
    for s in snippets:
        resp = SnippetResponse.model_validate(s)
        if s.source_id is not None:
            resp.source_title = title_map.get(s.source_id)
        responses.append(resp)
    return responses
