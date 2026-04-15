"""Chapter CRUD service — pure async functions."""

import uuid

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Chapter, Document
from writer.models.schemas import (
    ChapterCreate,
    ChapterResponse,
    ChapterUpdate,
)

logger = get_logger(__name__)


class ChapterNotFoundError(Exception):
    def __init__(self, chapter_id: uuid.UUID) -> None:
        super().__init__(f"Chapter {chapter_id} not found")
        self.chapter_id = chapter_id


async def create_chapter(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ChapterCreate,
) -> ChapterResponse:
    logger.info("create_chapter doc=%s user=%s title=%r", document_id, user_id, data.title)

    # Determine next position
    result = await db.execute(
        select(sa_func.max(Chapter.position)).where(Chapter.document_id == document_id)
    )
    max_pos = result.scalar_one_or_none()
    next_pos = 0 if max_pos is None else max_pos + 1

    chapter = Chapter(
        document_id=document_id,
        user_id=user_id,
        title=data.title,
        brief=data.brief,
        content="",
        position=next_pos,
    )
    db.add(chapter)
    await db.flush()
    await db.refresh(chapter)
    logger.info("create_chapter: created id=%s position=%d", chapter.id, chapter.position)

    await rebuild_document_content(db, document_id)
    return ChapterResponse.model_validate(chapter)


async def get_chapter(db: AsyncSession, chapter_id: uuid.UUID) -> ChapterResponse:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)
    return ChapterResponse.model_validate(chapter)


async def list_chapters(db: AsyncSession, document_id: uuid.UUID) -> list[ChapterResponse]:
    result = await db.execute(
        select(Chapter).where(Chapter.document_id == document_id).order_by(Chapter.position)
    )
    chapters = result.scalars().all()
    return [ChapterResponse.model_validate(c) for c in chapters]


async def update_chapter(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    data: ChapterUpdate,
) -> ChapterResponse:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    needs_rebuild = False
    if data.title is not None:
        chapter.title = data.title
        needs_rebuild = True
    if data.content is not None:
        chapter.content = data.content
        needs_rebuild = True
    if data.brief is not None:
        chapter.brief = data.brief

    await db.flush()
    await db.refresh(chapter)
    logger.info("update_chapter id=%s", chapter_id)

    if needs_rebuild:
        await rebuild_document_content(db, chapter.document_id)

    return ChapterResponse.model_validate(chapter)


async def delete_chapter(db: AsyncSession, chapter_id: uuid.UUID) -> None:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    doc_id = chapter.document_id
    await db.delete(chapter)
    await db.flush()
    logger.info("delete_chapter id=%s", chapter_id)

    await _recompact_positions(db, doc_id)
    await rebuild_document_content(db, doc_id)


async def reorder_chapter(
    db: AsyncSession, chapter_id: uuid.UUID, new_position: int
) -> list[ChapterResponse]:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    doc_id = chapter.document_id
    old_position = chapter.position

    if old_position == new_position:
        return await list_chapters(db, doc_id)

    await _reorder_positions(db, doc_id, old_position, new_position, chapter_id)
    await rebuild_document_content(db, doc_id)
    return await list_chapters(db, doc_id)


async def toggle_brief_visibility(
    db: AsyncSession, chapter_id: uuid.UUID, *, brief_visible: bool
) -> ChapterResponse:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    chapter.brief_visible = brief_visible
    await db.flush()
    await db.refresh(chapter)
    logger.info("toggle_brief_visibility id=%s visible=%s", chapter_id, brief_visible)
    return ChapterResponse.model_validate(chapter)


async def rebuild_document_content(db: AsyncSession, document_id: uuid.UUID) -> None:
    """Concatenate all chapters in order and write to Document.content."""
    result = await db.execute(
        select(Chapter).where(Chapter.document_id == document_id).order_by(Chapter.position)
    )
    chapters = result.scalars().all()

    parts: list[str] = []
    for ch in chapters:
        parts.append(f"## {ch.title}\n\n{ch.content}")

    concatenated = "\n\n".join(parts)

    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    doc = doc_result.scalar_one_or_none()
    if doc is not None:
        doc.content = concatenated
        await db.flush()
        logger.info(
            "rebuild_document_content doc=%s chapters=%d len=%d",
            document_id,
            len(chapters),
            len(concatenated),
        )


async def _recompact_positions(db: AsyncSession, document_id: uuid.UUID) -> None:
    """Recompact chapter positions to be sequential starting from 0."""
    result = await db.execute(
        select(Chapter).where(Chapter.document_id == document_id).order_by(Chapter.position)
    )
    chapters = result.scalars().all()
    for i, ch in enumerate(chapters):
        if ch.position != i:
            ch.position = i
    await db.flush()


async def _reorder_positions(
    db: AsyncSession,
    document_id: uuid.UUID,
    old_pos: int,
    new_pos: int,
    chapter_id: uuid.UUID,
) -> None:
    """Shift sibling positions when a chapter moves from old_pos to new_pos."""
    if old_pos < new_pos:
        # Moving down: shift siblings in (old_pos, new_pos] up by -1
        await db.execute(
            update(Chapter)
            .where(
                Chapter.document_id == document_id,
                Chapter.position > old_pos,
                Chapter.position <= new_pos,
                Chapter.id != chapter_id,
            )
            .values(position=Chapter.position - 1)
        )
    else:
        # Moving up: shift siblings in [new_pos, old_pos) down by +1
        await db.execute(
            update(Chapter)
            .where(
                Chapter.document_id == document_id,
                Chapter.position >= new_pos,
                Chapter.position < old_pos,
                Chapter.id != chapter_id,
            )
            .values(position=Chapter.position + 1)
        )

    # Set the chapter's own position
    await db.execute(update(Chapter).where(Chapter.id == chapter_id).values(position=new_pos))
    await db.flush()
