"""Vector store service — re-exported from documentlm_core."""

from documentlm_core.services.vector_store import (  # noqa: F401
    ChunkResult,
    delete_source_chunks,
    get_collection,
    index_source,
    query_sources,
    query_sources_tiered,
    query_sources_with_metadata,
    update_privacy,
)
