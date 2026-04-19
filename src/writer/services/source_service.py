"""Source management service."""

import asyncio
import uuid
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.config import settings
from writer.core.logging import get_logger
from writer.models.db import Chapter, ChapterSource, Source
from writer.models.enums import IndexingStatus, SourceType
from writer.models.schemas import (
    FilterScope,
    FilterScopeAll,
    FilterScopeChapter,
    FilterScopeDocLevel,
    SourceCreate,
    SourceResponse,
)
from writer.services import vector_store

logger = get_logger(__name__)


class SourceNotFoundError(Exception):
    def __init__(self, source_id: uuid.UUID) -> None:
        super().__init__(f"Source {source_id} not found")
        self.source_id = source_id


class PdfParseError(Exception):
    pass


class ChapterDocumentMismatchError(Exception):
    """Raised when an attempted association crosses documents."""

    def __init__(self, chapter_id: uuid.UUID, item_id: uuid.UUID) -> None:
        super().__init__(
            f"chapter {chapter_id} does not belong to the same document as item {item_id}"
        )
        self.chapter_id = chapter_id
        self.item_id = item_id


def _extract_pdf_markdown(file_bytes: bytes) -> str:
    import fitz  # pymupdf
    import pymupdf4llm

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    md: str = pymupdf4llm.to_markdown(doc)
    if not md.strip():
        raise PdfParseError("PDF contains no extractable text (may be image-only)")
    return md


async def _fetch_chapter_ids_for_sources(
    db: AsyncSession, source_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Batch-load chapter_ids keyed by source_id."""
    if not source_ids:
        return {}
    result = await db.execute(
        select(ChapterSource).where(ChapterSource.source_id.in_(list(source_ids)))
    )
    mapping: dict[uuid.UUID, list[uuid.UUID]] = {sid: [] for sid in source_ids}
    for row in result.scalars().all():
        mapping.setdefault(row.source_id, []).append(row.chapter_id)
    return mapping


async def add_source(db: AsyncSession, data: SourceCreate, user_id: uuid.UUID) -> SourceResponse:
    logger.info("Adding source type=%s doc=%s user=%s", data.source_type, data.document_id, user_id)
    if data.url:
        existing = await db.execute(
            select(Source).where(
                Source.document_id == data.document_id,
                Source.url == data.url,
                Source.user_id == user_id,
            )
        )
        dupe = existing.scalar_one_or_none()
        if dupe is not None:
            logger.info("Skipping duplicate url=%s for doc=%s", data.url, data.document_id)
            response = SourceResponse.model_validate(dupe)
            response.chapter_ids = []
            return response

    content = data.content
    missing_content = False
    if data.source_type == SourceType.url and data.url and not content:
        from documentlm_core.services.content_cleaner import clean_content

        from writer.services.content_fetcher import fetch_url_content

        logger.info("Fetching URL content for url=%s", data.url)
        raw = await fetch_url_content(data.url)
        logger.info("Fetched %d chars from url=%s", len(raw), data.url)
        cleaned = await clean_content(raw)
        if cleaned is None:
            content = raw
            missing_content = True
        else:
            content = cleaned

    source = Source(
        user_id=user_id,
        document_id=data.document_id,
        source_type=data.source_type,
        title=data.title,
        content=content,
        url=data.url,
    )
    if missing_content:
        source.indexing_status = IndexingStatus.failed
        source.error_message = "No article content found"
    db.add(source)
    await db.flush()
    await db.refresh(source)

    if data.chapter_ids:
        await replace_source_chapter_associations(
            db,
            source.id,
            data.chapter_ids,
            document_id=data.document_id,
            user_id=user_id,
        )

    logger.info("Added source id=%s chapters=%d", source.id, len(data.chapter_ids))
    response = SourceResponse.model_validate(source)
    response.chapter_ids = list(data.chapter_ids)
    return response


async def add_source_pdf(
    db: AsyncSession,
    document_id: uuid.UUID,
    title: str,
    file_bytes: bytes,
    user_id: uuid.UUID,
    chapter_ids: Sequence[uuid.UUID] = (),
) -> SourceResponse:
    logger.info("Extracting PDF markdown doc=%s user=%s", document_id, user_id)
    try:
        content = _extract_pdf_markdown(file_bytes)
    except PdfParseError:
        raise
    except Exception as exc:
        logger.exception("PDF extraction failed: %s", exc)
        raise PdfParseError("Failed to parse PDF") from exc

    from documentlm_core.services.content_cleaner import clean_content

    raw = content
    cleaned = await clean_content(raw)
    missing_content = cleaned is None
    content = raw if missing_content else cleaned

    source = Source(
        user_id=user_id,
        document_id=document_id,
        source_type=SourceType.pdf,
        title=title,
        content=content,
        url=None,
    )
    if missing_content:
        source.indexing_status = IndexingStatus.failed
        source.error_message = "No article content found"
    db.add(source)
    await db.flush()
    await db.refresh(source)
    pdf_dir = Path(settings.pdf_storage_path)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    file_path = pdf_dir / f"{source.id}.pdf"
    file_path.write_bytes(file_bytes)
    source.file_path = str(file_path)
    await db.flush()
    await db.refresh(source)

    if chapter_ids:
        await replace_source_chapter_associations(
            db,
            source.id,
            list(chapter_ids),
            document_id=document_id,
            user_id=user_id,
        )

    logger.info(
        "Added PDF source id=%s file=%s chapters=%d", source.id, file_path, len(chapter_ids)
    )
    response = SourceResponse.model_validate(source)
    response.chapter_ids = list(chapter_ids)
    return response


async def get_source(db: AsyncSession, source_id: uuid.UUID, user_id: uuid.UUID) -> SourceResponse:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        logger.error("Source %s not found for user %s", source_id, user_id)
        raise SourceNotFoundError(source_id)
    chapter_map = await _fetch_chapter_ids_for_sources(db, [source.id])
    response = SourceResponse.model_validate(source)
    response.chapter_ids = chapter_map.get(source.id, [])
    return response


async def list_sources(
    db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID
) -> list[SourceResponse]:
    result = await db.execute(
        select(Source)
        .where(Source.document_id == document_id, Source.user_id == user_id)
        .order_by(Source.created_at)
    )
    sources = result.scalars().all()
    chapter_map = await _fetch_chapter_ids_for_sources(db, [s.id for s in sources])
    responses: list[SourceResponse] = []
    for s in sources:
        resp = SourceResponse.model_validate(s)
        resp.chapter_ids = chapter_map.get(s.id, [])
        responses.append(resp)
    return responses


async def list_sources_by_scope(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    scope: FilterScope,
) -> list[SourceResponse]:
    """List sources filtered by scope (all / doc-level / chapter:<uuid>)."""
    logger.info("list_sources_by_scope doc=%s user=%s scope=%r", document_id, user_id, scope)

    if isinstance(scope, FilterScopeChapter):
        # Verify chapter exists in this document; otherwise degrade to all.
        chap_result = await db.execute(
            select(Chapter).where(
                Chapter.id == scope.chapter_id, Chapter.document_id == document_id
            )
        )
        if chap_result.scalar_one_or_none() is None:
            logger.warning(
                "list_sources_by_scope: stale/unknown chapter %s in doc %s — degrading to all",
                scope.chapter_id,
                document_id,
            )
            return await list_sources(db, document_id, user_id)

        src_result = await db.execute(
            select(Source)
            .join(ChapterSource, Source.id == ChapterSource.source_id)
            .where(
                ChapterSource.chapter_id == scope.chapter_id,
                Source.user_id == user_id,
                Source.document_id == document_id,
            )
            .order_by(Source.created_at)
        )
        sources = list(src_result.scalars().all())
        chapter_map = await _fetch_chapter_ids_for_sources(db, [s.id for s in sources])
        return [
            _attach_chapter_ids(SourceResponse.model_validate(s), chapter_map, s.id)
            for s in sources
        ]

    if isinstance(scope, FilterScopeDocLevel):
        # Sources with zero rows in chapter_sources.
        src_result = await db.execute(
            select(Source)
            .outerjoin(ChapterSource, Source.id == ChapterSource.source_id)
            .where(
                Source.document_id == document_id,
                Source.user_id == user_id,
                ChapterSource.source_id.is_(None),
            )
            .order_by(Source.created_at)
        )
        sources = list(src_result.scalars().all())
        return [_attach_chapter_ids(SourceResponse.model_validate(s), {}, s.id) for s in sources]

    # FilterScopeAll
    assert isinstance(scope, FilterScopeAll)
    return await list_sources(db, document_id, user_id)


def _attach_chapter_ids(
    response: SourceResponse,
    chapter_map: dict[uuid.UUID, list[uuid.UUID]],
    source_id: uuid.UUID,
) -> SourceResponse:
    response.chapter_ids = chapter_map.get(source_id, [])
    return response


async def assign_source_to_chapter(
    db: AsyncSession, chapter_id: uuid.UUID, source_id: uuid.UUID
) -> None:
    """Associate a source with a chapter (idempotent via merge; validates same-document)."""
    logger.info("assign_source_to_chapter chapter=%s source=%s", chapter_id, source_id)
    chap_res = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = chap_res.scalar_one_or_none()
    src_res = await db.execute(select(Source).where(Source.id == source_id))
    source = src_res.scalar_one_or_none()
    if chapter is None or source is None or chapter.document_id != source.document_id:
        logger.error(
            "assign_source_to_chapter: mismatch chapter=%s source=%s", chapter_id, source_id
        )
        raise ChapterDocumentMismatchError(chapter_id, source_id)

    junction = ChapterSource(chapter_id=chapter_id, source_id=source_id)
    await db.merge(junction)
    await db.flush()
    logger.info("assign_source_to_chapter: assigned")


async def unassign_source_from_chapter(
    db: AsyncSession, chapter_id: uuid.UUID, source_id: uuid.UUID
) -> None:
    """Remove a source's association with a chapter (no-op if absent)."""
    logger.info("unassign_source_from_chapter chapter=%s source=%s", chapter_id, source_id)
    result = await db.execute(
        select(ChapterSource).where(
            ChapterSource.chapter_id == chapter_id,
            ChapterSource.source_id == source_id,
        )
    )
    junction = result.scalar_one_or_none()
    if junction is None:
        logger.info("unassign_source_from_chapter: no association, noop")
        return
    await db.delete(junction)
    await db.flush()
    logger.info("unassign_source_from_chapter: removed")


async def replace_source_chapter_associations(
    db: AsyncSession,
    source_id: uuid.UUID,
    chapter_ids: Sequence[uuid.UUID],
    *,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Atomically replace the full set of chapter associations for `source_id`.

    Validates that every chapter_id belongs to `document_id`; raises
    ChapterDocumentMismatchError on the first outsider (nothing is persisted).
    """
    logger.info(
        "replace_source_chapter_associations source=%s doc=%s new_set=%d",
        source_id,
        document_id,
        len(chapter_ids),
    )
    target = list(chapter_ids)

    # Validation: every target chapter belongs to this document.
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
                    "replace_source_chapter_associations: chapter %s not in doc %s",
                    cid,
                    document_id,
                )
                raise ChapterDocumentMismatchError(cid, source_id)
    else:
        # Still need the existing rows to know what to delete; skip validation query.
        pass

    existing_result = await db.execute(
        select(ChapterSource).where(ChapterSource.source_id == source_id)
    )
    existing_rows = list(existing_result.scalars().all())
    existing_ids = {row.chapter_id for row in existing_rows}
    target_set = set(target)

    # Delete removed associations.
    for row in existing_rows:
        if row.chapter_id not in target_set:
            await db.delete(row)

    # Merge the additions (idempotent — existing rows are a no-op via PK match).
    for cid in target:
        if cid not in existing_ids:
            await db.merge(ChapterSource(chapter_id=cid, source_id=source_id))

    await db.flush()
    logger.info(
        "replace_source_chapter_associations: removed=%d added=%d",
        sum(1 for r in existing_rows if r.chapter_id not in target_set),
        sum(1 for c in target if c not in existing_ids),
    )
    _ = user_id  # kept in signature for parity with snippet side and future auth checks


async def delete_source(db: AsyncSession, source_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise SourceNotFoundError(source_id)
    try:
        await asyncio.to_thread(vector_store.delete_source_chunks, source_id, user_id)
        logger.info("Deleted ChromaDB chunks for source id=%s", source_id)
    except Exception as exc:
        logger.error("Failed to delete ChromaDB chunks for source id=%s: %s", source_id, exc)
        raise
    if source.file_path:
        try:
            Path(source.file_path).unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Failed to delete PDF file %s: %s", source.file_path, exc)
    await db.delete(source)
    await db.flush()
    logger.info("Deleted source id=%s", source_id)
