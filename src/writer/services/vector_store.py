"""ChromaDB vector store service.

All ChromaDB calls are synchronous (stable client).
Call sites in async contexts must wrap with asyncio.to_thread().
"""

import uuid

import chromadb

from writer.core.config import settings
from writer.core.logging import get_logger

logger = get_logger(__name__)

_collection: chromadb.Collection | None = None


def get_collection() -> chromadb.Collection:
    """Return the singleton ChromaDB 'sources' collection, creating it if needed."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = client.get_or_create_collection("sources")
    return _collection


def index_source(source_id: uuid.UUID, document_id: uuid.UUID, chunks: list[str]) -> None:
    """Add all chunks for a source to the ChromaDB collection."""
    collection = get_collection()
    ids = [f"{source_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"source_id": str(source_id), "document_id": str(document_id)} for _ in chunks]
    collection.add(ids=ids, documents=chunks, metadatas=metadatas)  # type: ignore[arg-type]
    logger.info("Indexed %d chunks for source_id=%s doc=%s", len(chunks), source_id, document_id)


def query_sources(query_text: str, document_id: uuid.UUID, top_k: int = 5) -> list[str]:
    """Return the top_k semantically relevant chunks for the given query, scoped to a document."""
    collection = get_collection()
    result = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where={"document_id": str(document_id)},
    )
    docs: list[str] = result["documents"][0] if result["documents"] else []
    logger.info(
        "query_sources query=%r doc=%s → %d chunks",
        query_text[:80],
        document_id,
        len(docs),
    )
    for i, chunk in enumerate(docs):
        logger.info("  chunk[%d]: %r", i, chunk[:120])
    return docs


def delete_source_chunks(source_id: uuid.UUID) -> None:
    """Remove all ChromaDB chunks belonging to the given source."""
    collection = get_collection()
    collection.delete(where={"source_id": str(source_id)})
    logger.info("Deleted chunks for source_id=%s", source_id)
