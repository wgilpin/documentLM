"""Background indexing pipeline — thin wrapper around documentlm_core."""

import uuid

from documentlm_core.services.indexer import run_indexing as _core_run_indexing
from sqlalchemy.ext.asyncio import AsyncSession

from writer.models.db import Document, Source


async def run_indexing(source_id: uuid.UUID, db: AsyncSession, user_id: uuid.UUID) -> None:
    """Chunk and index a source into ChromaDB, updating indexing_status."""
    await _core_run_indexing(source_id, db, user_id, Source, Document)
