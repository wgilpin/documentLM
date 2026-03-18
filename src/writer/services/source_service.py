"""Source management service."""

import asyncio
import uuid
from io import BytesIO
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.config import settings
from writer.core.logging import get_logger
from writer.models.db import Source
from writer.models.enums import SourceType
from writer.models.schemas import SourceCreate, SourceResponse
from writer.services import vector_store

logger = get_logger(__name__)


class SourceNotFoundError(Exception):
    def __init__(self, source_id: uuid.UUID) -> None:
        super().__init__(f"Source {source_id} not found")
        self.source_id = source_id


class PdfParseError(Exception):
    pass


def _extract_pdf_text(file_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


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
            return SourceResponse.model_validate(dupe)
    source = Source(
        user_id=user_id,
        document_id=data.document_id,
        source_type=data.source_type,
        title=data.title,
        content=data.content,
        url=data.url,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    logger.info("Added source id=%s", source.id)
    return SourceResponse.model_validate(source)


async def add_source_pdf(
    db: AsyncSession,
    document_id: uuid.UUID,
    title: str,
    file_bytes: bytes,
    user_id: uuid.UUID,
) -> SourceResponse:
    logger.info("Extracting PDF text doc=%s user=%s", document_id, user_id)
    try:
        content = _extract_pdf_text(file_bytes)
    except Exception as exc:
        logger.exception("PDF extraction failed: %s", exc)
        raise PdfParseError("Failed to parse PDF") from exc
    source = Source(
        user_id=user_id,
        document_id=document_id,
        source_type=SourceType.pdf,
        title=title,
        content=content,
        url=None,
    )
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
    logger.info("Added PDF source id=%s file=%s", source.id, file_path)
    return SourceResponse.model_validate(source)


async def get_source(db: AsyncSession, source_id: uuid.UUID, user_id: uuid.UUID) -> SourceResponse:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        logger.error("Source %s not found for user %s", source_id, user_id)
        raise SourceNotFoundError(source_id)
    return SourceResponse.model_validate(source)


async def list_sources(
    db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID
) -> list[SourceResponse]:
    result = await db.execute(
        select(Source)
        .where(Source.document_id == document_id, Source.user_id == user_id)
        .order_by(Source.created_at)
    )
    sources = result.scalars().all()
    return [SourceResponse.model_validate(s) for s in sources]


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
