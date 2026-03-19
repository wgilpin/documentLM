"""ChromaDB vector store service — per-user collections with privacy filtering.

All ChromaDB calls are synchronous (stable client).
Call sites in async contexts must wrap with asyncio.to_thread().
"""

import uuid

import chromadb

from writer.core.config import settings
from writer.core.logging import get_logger

logger = get_logger(__name__)

_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_path)
    return _client


def get_collection(user_id: uuid.UUID) -> chromadb.Collection:
    """Return (or create) the ChromaDB collection for the given user."""
    name = f"user_{user_id.hex}"
    return _get_client().get_or_create_collection(name)


def index_source(
    source_id: uuid.UUID,
    document_id: uuid.UUID,
    chunks: list[str],
    user_id: uuid.UUID,
    is_private: bool = False,
) -> None:
    """Add all chunks for a source to the user's ChromaDB collection."""
    collection = get_collection(user_id)
    ids = [f"{source_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source_id": str(source_id),
            "document_id": str(document_id),
            "is_private": is_private,
        }
        for _ in chunks
    ]
    collection.add(ids=ids, documents=chunks, metadatas=metadatas)  # type: ignore[arg-type]
    logger.info(
        "Indexed %d chunks for source_id=%s doc=%s user=%s is_private=%s",
        len(chunks),
        source_id,
        document_id,
        user_id,
        is_private,
    )


def query_sources(
    query_text: str,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    is_private_doc: bool = False,
    top_k: int = 5,
) -> list[str]:
    """Return the top_k relevant chunks for the given query.

    When is_private_doc=False: search all non-private chunks for this user.
    When is_private_doc=True: search only chunks from this specific document.
    """
    collection = get_collection(user_id)

    # Check if collection has any documents to avoid ChromaDB errors
    count = collection.count()
    if count == 0:
        logger.info("query_sources: empty collection for user=%s", user_id)
        return []

    where: dict[str, object] = (
        {"document_id": {"$eq": str(doc_id)}} if is_private_doc else {"is_private": False}
    )

    result = collection.query(
        query_texts=[query_text],
        n_results=min(top_k, count),
        where=where,  # type: ignore[arg-type]
    )
    docs: list[str] = result["documents"][0] if result["documents"] else []
    logger.info(
        "query_sources query=%r user=%s doc=%s is_private=%s → %d chunks",
        query_text[:80],
        user_id,
        doc_id,
        is_private_doc,
        len(docs),
    )
    return docs


def query_sources_tiered(
    query_text: str,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    is_private_doc: bool = False,
    top_k: int = 5,
    max_distance: float = 1.0,
) -> tuple[list[str], list[str]]:
    """Return (doc_chunks, other_chunks) for the top_k most relevant chunks.

    Runs a single ChromaDB query then buckets results by whether the chunk
    belongs to doc_id or another document.  Chunks whose squared-L2 distance
    exceeds max_distance are discarded before bucketing.

    Default max_distance=1.0 corresponds to cosine similarity ≥ 0.5 for
    normalised embeddings (squared L2 = 2 × (1 − cosine)).

    When is_private_doc=True: only this document's chunks are searched;
    other_chunks will always be empty.
    """
    collection = get_collection(user_id)

    count = collection.count()
    if count == 0:
        logger.info("query_sources_tiered: empty collection for user=%s", user_id)
        return [], []

    where: dict[str, object] = (
        {"document_id": {"$eq": str(doc_id)}} if is_private_doc else {"is_private": False}
    )

    result = collection.query(
        query_texts=[query_text],
        n_results=min(top_k, count),
        where=where,  # type: ignore[arg-type]
        include=["documents", "metadatas", "distances"],  # type: ignore[list-item]
    )

    raw_docs: list[str] = result["documents"][0] if result["documents"] else []
    raw_metas: list[dict[str, object]] = result["metadatas"][0] if result["metadatas"] else []  # type: ignore[assignment]
    raw_dists: list[float] = result["distances"][0] if result["distances"] else []

    doc_chunks: list[str] = []
    other_chunks: list[str] = []
    doc_id_str = str(doc_id)
    for text, meta, dist in zip(raw_docs, raw_metas, raw_dists, strict=False):
        if dist > max_distance:
            logger.debug(
                "query_sources_tiered: dropping chunk dist=%.3f > %.3f", dist, max_distance
            )
            continue
        if meta.get("document_id") == doc_id_str:
            doc_chunks.append(text)
        else:
            other_chunks.append(text)

    logger.info(
        "query_sources_tiered query=%r user=%s doc=%s max_dist=%.2f"
        " \u2192 %d doc chunks, %d other chunks",
        query_text[:80],
        user_id,
        doc_id,
        max_distance,
        len(doc_chunks),
        len(other_chunks),
    )
    return doc_chunks, other_chunks


def delete_source_chunks(source_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Remove all ChromaDB chunks belonging to the given source from the user's collection."""
    collection = get_collection(user_id)
    collection.delete(where={"source_id": str(source_id)})
    logger.info("Deleted chunks for source_id=%s user=%s", source_id, user_id)


def update_privacy(user_id: uuid.UUID, doc_id: uuid.UUID, is_private: bool) -> None:
    """Update is_private metadata on all chunks belonging to the given document."""
    collection = get_collection(user_id)

    # Get all chunk IDs for this document
    results = collection.get(where={"document_id": str(doc_id)}, include=["metadatas"])
    ids: list[str] = results.get("ids", [])  # type: ignore[assignment]
    if not ids:
        logger.info("update_privacy: no chunks found for doc=%s user=%s", doc_id, user_id)
        return

    existing_metadatas: list[dict[str, object]] = results.get("metadatas") or []  # type: ignore[assignment]
    updated_metadatas = [{**m, "is_private": is_private} for m in existing_metadatas]
    collection.update(ids=ids, metadatas=updated_metadatas)  # type: ignore[arg-type]
    logger.info(
        "update_privacy: updated %d chunks for doc=%s user=%s is_private=%s",
        len(ids),
        doc_id,
        user_id,
        is_private,
    )
