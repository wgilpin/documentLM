"""Vector store service — re-exported from documentlm_core."""

from documentlm_core.services.vector_store import (  # noqa: F401
    MAX_DISTANCE,
    ChunkResult,
    delete_snippet_embedding,
    delete_source_chunks,
    get_collection,
    index_snippet,
    index_source,
    query_document_corpus,
    query_sources,
    query_sources_tiered,
    query_sources_with_metadata,
    update_privacy,
)
