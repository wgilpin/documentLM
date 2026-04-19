"""Snippet CRUD service."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Chapter, ChapterSnippet, Document, Snippet, Source
from writer.models.schemas import (
    FilterScope,
    FilterScopeAll,
    FilterScopeChapter,
    FilterScopeDocLevel,
    SnippetCreate,
    SnippetResponse,
    SnippetUpdate,
)

logger = get_logger(__name__)


class SnippetNotFoundError(Exception):
    def __init__(self, snippet_id: uuid.UUID) -> None:
        super().__init__(f"Snippet {snippet_id} not found")
        self.snippet_id = snippet_id


class DocumentNotFoundError(Exception):
    def __init__(self, document_id: uuid.UUID) -> None:
        super().__init__(f"Document {document_id} not found")
        self.document_id = document_id


class ChapterDocumentMismatchError(Exception):
    """Raised when an attempted association crosses documents."""

    def __init__(self, chapter_id: uuid.UUID, item_id: uuid.UUID) -> None:
        super().__init__(
            f"chapter {chapter_id} does not belong to the same document as item {item_id}"
        )
        self.chapter_id = chapter_id
        self.item_id = item_id


async def _fetch_chapter_ids_for_snippets(
    db: AsyncSession, snippet_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Batch-load chapter_ids keyed by snippet_id."""
    if not snippet_ids:
        return {}
    result = await db.execute(
        select(ChapterSnippet).where(ChapterSnippet.snippet_id.in_(list(snippet_ids)))
    )
    mapping: dict[uuid.UUID, list[uuid.UUID]] = {sid: [] for sid in snippet_ids}
    for row in result.scalars().all():
        mapping.setdefault(row.snippet_id, []).append(row.chapter_id)
    return mapping


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

    if data.chapter_ids:
        await replace_snippet_chapter_associations(
            db,
            snippet.id,
            data.chapter_ids,
            document_id=document_id,
            user_id=user_id,
        )

    response = SnippetResponse.model_validate(snippet)
    response.chapter_ids = list(data.chapter_ids)
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
    snippets = list(result.scalars().all())
    logger.info("list_snippets: found %d snippets", len(snippets))

    source_ids = {s.source_id for s in snippets if s.source_id is not None}
    title_map: dict[uuid.UUID, str] = {}
    if source_ids:
        src_result = await db.execute(select(Source).where(Source.id.in_(source_ids)))
        for src in src_result.scalars().all():
            title_map[src.id] = src.title

    chapter_map = await _fetch_chapter_ids_for_snippets(db, [s.id for s in snippets])

    responses: list[SnippetResponse] = []
    for s in snippets:
        resp = SnippetResponse.model_validate(s)
        if s.source_id is not None:
            resp.source_title = title_map.get(s.source_id)
        resp.chapter_ids = chapter_map.get(s.id, [])
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

    chapter_map = await _fetch_chapter_ids_for_snippets(db, [snippet.id])

    response = SnippetResponse.model_validate(snippet)
    response.source_title = source_title
    response.chapter_ids = chapter_map.get(snippet.id, [])
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
    snippets = list(result.scalars().all())
    logger.info("list_snippets_by_chapter: found %d snippets", len(snippets))

    source_ids = {s.source_id for s in snippets if s.source_id is not None}
    title_map: dict[uuid.UUID, str] = {}
    if source_ids:
        src_result = await db.execute(select(Source).where(Source.id.in_(source_ids)))
        for src in src_result.scalars().all():
            title_map[src.id] = src.title

    chapter_map = await _fetch_chapter_ids_for_snippets(db, [s.id for s in snippets])

    responses: list[SnippetResponse] = []
    for s in snippets:
        resp = SnippetResponse.model_validate(s)
        if s.source_id is not None:
            resp.source_title = title_map.get(s.source_id)
        resp.chapter_ids = chapter_map.get(s.id, [])
        responses.append(resp)
    return responses


async def replace_snippet_chapter_associations(
    db: AsyncSession,
    snippet_id: uuid.UUID,
    chapter_ids: Sequence[uuid.UUID],
    *,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Atomically replace the full set of chapter associations for `snippet_id`."""
    logger.info(
        "replace_snippet_chapter_associations snippet=%s doc=%s new_set=%d",
        snippet_id,
        document_id,
        len(chapter_ids),
    )
    target = list(chapter_ids)

    valid_ids: set[uuid.UUID] = set()
    if target:
        chap_result = await db.execute(
            select(Chapter).where(
                Chapter.id.in_(target),
                Chapter.document_id == document_id,
            )
        )
        valid_ids = {c.id for c in chap_result.scalars().all()}
        for cid in target:
            if cid not in valid_ids:
                logger.error(
                    "replace_snippet_chapter_associations: chapter %s not in doc %s",
                    cid,
                    document_id,
                )
                raise ChapterDocumentMismatchError(cid, snippet_id)

    existing_result = await db.execute(
        select(ChapterSnippet).where(ChapterSnippet.snippet_id == snippet_id)
    )
    existing_rows = list(existing_result.scalars().all())
    existing_ids = {row.chapter_id for row in existing_rows}
    target_set = set(target)

    for row in existing_rows:
        if row.chapter_id not in target_set:
            await db.delete(row)

    for cid in target:
        if cid not in existing_ids:
            await db.merge(ChapterSnippet(chapter_id=cid, snippet_id=snippet_id))

    await db.flush()
    logger.info(
        "replace_snippet_chapter_associations: removed=%d added=%d",
        sum(1 for r in existing_rows if r.chapter_id not in target_set),
        sum(1 for c in target if c not in existing_ids),
    )
    _ = user_id  # parity with source side; reserved for future auth


async def list_snippets_by_scope(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    scope: FilterScope,
) -> list[SnippetResponse]:
    """List snippets filtered by scope (all / doc-level / chapter:<uuid>)."""
    logger.info("list_snippets_by_scope doc=%s user=%s scope=%r", document_id, user_id, scope)

    if isinstance(scope, FilterScopeChapter):
        chap_result = await db.execute(
            select(Chapter).where(
                Chapter.id == scope.chapter_id, Chapter.document_id == document_id
            )
        )
        if chap_result.scalar_one_or_none() is None:
            logger.warning(
                "list_snippets_by_scope: stale/unknown chapter %s in doc %s — degrading to all",
                scope.chapter_id,
                document_id,
            )
            return await list_snippets(db, document_id, user_id)
        return await list_snippets_by_chapter(db, scope.chapter_id, user_id)

    if isinstance(scope, FilterScopeDocLevel):
        src_result = await db.execute(
            select(Snippet)
            .outerjoin(ChapterSnippet, Snippet.id == ChapterSnippet.snippet_id)
            .where(
                Snippet.document_id == document_id,
                Snippet.user_id == user_id,
                ChapterSnippet.snippet_id.is_(None),
            )
            .order_by(Snippet.created_at.desc())
        )
        snippets = list(src_result.scalars().all())

        source_ids = {s.source_id for s in snippets if s.source_id is not None}
        title_map: dict[uuid.UUID, str] = {}
        if source_ids:
            src_q = await db.execute(select(Source).where(Source.id.in_(source_ids)))
            for src in src_q.scalars().all():
                title_map[src.id] = src.title

        # chapter_ids batch — always empty for doc-level, but keep shape uniform
        await _fetch_chapter_ids_for_snippets(db, [s.id for s in snippets])

        responses: list[SnippetResponse] = []
        for s in snippets:
            resp = SnippetResponse.model_validate(s)
            if s.source_id is not None:
                resp.source_title = title_map.get(s.source_id)
            resp.chapter_ids = []
            responses.append(resp)
        return responses

    assert isinstance(scope, FilterScopeAll)
    return await list_snippets(db, document_id, user_id)
