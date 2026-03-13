"""Source management service."""

import uuid
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Source
from writer.models.enums import SourceType
from writer.models.schemas import SourceCreate, SourceResponse

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


async def add_source(db: AsyncSession, data: SourceCreate) -> SourceResponse:
    logger.info("Adding source type=%s doc=%s", data.source_type, data.document_id)
    source = Source(
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
    db: AsyncSession, document_id: uuid.UUID, title: str, file_bytes: bytes
) -> SourceResponse:
    logger.info("Extracting PDF text doc=%s", document_id)
    try:
        content = _extract_pdf_text(file_bytes)
    except Exception as exc:
        logger.exception("PDF extraction failed: %s", exc)
        raise PdfParseError("Failed to parse PDF") from exc
    source = Source(
        document_id=document_id,
        source_type=SourceType.pdf,
        title=title,
        content=content,
        url=None,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    logger.info("Added PDF source id=%s", source.id)
    return SourceResponse.model_validate(source)


async def list_sources(db: AsyncSession, document_id: uuid.UUID) -> list[SourceResponse]:
    result = await db.execute(
        select(Source).where(Source.document_id == document_id).order_by(Source.created_at)
    )
    sources = result.scalars().all()
    return [SourceResponse.model_validate(s) for s in sources]


async def delete_source(db: AsyncSession, source_id: uuid.UUID) -> None:
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise SourceNotFoundError(source_id)
    await db.delete(source)
    await db.flush()
    logger.info("Deleted source id=%s", source_id)
