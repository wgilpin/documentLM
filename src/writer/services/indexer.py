"""Background indexing pipeline for source documents."""

import asyncio
import uuid

from nlp_utils import chunk_sentences  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Source
from writer.models.enums import IndexingStatus
from writer.services import vector_store

logger = get_logger(__name__)


async def run_indexing(source_id: uuid.UUID, db: AsyncSession) -> None:
    """Chunk and index a source into ChromaDB, updating indexing_status.

    Idempotency guard: returns immediately if status is already processing or completed.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()

    if source is None:
        logger.warning("run_indexing: source_id=%s not found — skipping", source_id)
        return

    if source.indexing_status in (IndexingStatus.processing, IndexingStatus.completed):
        logger.info(
            "run_indexing: source_id=%s already %s — skipping",
            source_id,
            source.indexing_status.value,
        )
        return

    source.indexing_status = IndexingStatus.processing
    await db.flush()
    logger.info("run_indexing: source_id=%s status → processing", source_id)

    try:
        chunks = chunk_sentences(source.content, chunk_size=1000, chunk_overlap=100)
        await asyncio.to_thread(vector_store.index_source, source_id, chunks)
        source.indexing_status = IndexingStatus.completed
        await db.flush()
        logger.info(
            "run_indexing: source_id=%s status → completed (%d chunks)", source_id, len(chunks)
        )
    except Exception as exc:
        source.indexing_status = IndexingStatus.failed
        source.error_message = str(exc)
        await db.flush()
        logger.error("run_indexing: source_id=%s failed: %s", source_id, exc)
