"""Integration tests for the RAG pipeline using an ephemeral ChromaDB instance.

These tests use chromadb.EphemeralClient() — no filesystem side-effects, no cleanup needed.
Run with: uv run pytest tests/integration/test_rag_pipeline.py -m integration
"""

import uuid
from unittest.mock import patch

import chromadb


def _make_ephemeral_get_collection() -> object:
    """Return a get_collection replacement that uses a shared ephemeral client."""
    client = chromadb.EphemeralClient()

    def get_collection(user_id: uuid.UUID) -> chromadb.Collection:
        return client.get_or_create_collection(f"user_{user_id.hex}")

    return get_collection


class TestRagPipelineRoundTrip:
    def test_index_then_query_returns_chunks(self) -> None:
        from writer.services.vector_store import index_source, query_sources

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()
        chunks = ["The sky is blue.", "Water is wet.", "Fire is hot."]

        with patch(
            "writer.services.vector_store.get_collection",
            side_effect=_make_ephemeral_get_collection(),
        ):
            index_source(source_id, doc_id, chunks, user_id, is_private=False)
            result = query_sources("What colour is the sky?", user_id, doc_id, top_k=3)

        assert len(result) > 0
        assert any("sky" in r or "blue" in r for r in result)

    def test_index_delete_then_query_returns_empty(self) -> None:
        from writer.services.vector_store import delete_source_chunks, index_source, query_sources

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()
        chunks = ["Unique content about purple elephants that dance.", "More elephant content."]

        with patch(
            "writer.services.vector_store.get_collection",
            side_effect=_make_ephemeral_get_collection(),
        ):
            index_source(source_id, doc_id, chunks, user_id, is_private=False)
            delete_source_chunks(source_id, user_id)
            result = query_sources("purple elephants", user_id, doc_id, top_k=5)

        assert result == [] or not any("elephant" in r for r in result)
