"""Semantic search service — maps ChromaDB chunk results to source metadata."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Source
from writer.models.schemas import SearchResponse, SearchResultItem
from writer.services.vector_store import query_sources_with_metadata

logger = get_logger(__name__)


async def search_document_corpus(
    query: str,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    session: AsyncSession,
    top_k: int = 10,
) -> SearchResponse:
    """Search all ingested sources for the query and return ranked results with source metadata."""
    logger.info(
        "search_document_corpus query=%r user=%s doc=%s top_k=%d", query, user_id, doc_id, top_k
    )

    chunks = query_sources_with_metadata(
        query, user_id, doc_id, is_private_doc=False, top_k=top_k
    )

    if not chunks:
        logger.info("search_document_corpus: no results for query=%r", query)
        return SearchResponse(results=[], query=query)

    results: list[SearchResultItem] = []
    for chunk in chunks:
        try:
            source_uuid = uuid.UUID(chunk["source_id"])
        except (ValueError, KeyError):
            logger.warning(
                "search_document_corpus: invalid source_id %r in chunk", chunk.get("source_id")
            )
            continue

        src_result = await session.execute(select(Source).where(Source.id == source_uuid))
        source = src_result.scalar_one_or_none()
        if source is None:
            logger.warning(
                "search_document_corpus: source %s not found, skipping chunk", source_uuid
            )
            continue

        results.append(
            SearchResultItem(
                text=chunk["text"],
                source_id=source_uuid,
                source_title=source.title,
            )
        )

    logger.info("search_document_corpus: returning %d results", len(results))
    return SearchResponse(results=results, query=query)
