"""Integration tests for the RAG pipeline using an ephemeral ChromaDB instance.

These tests use chromadb.EphemeralClient() — no filesystem side-effects, no cleanup needed.
Run with: uv run pytest tests/integration/test_rag_pipeline.py -m integration
"""

import uuid
from unittest.mock import patch

import chromadb
import pytest


@pytest.fixture
def ephemeral_collection() -> chromadb.Collection:
    client = chromadb.EphemeralClient()
    return client.get_or_create_collection("sources")


class TestRagPipelineRoundTrip:
    def test_index_then_query_returns_chunks(
        self, ephemeral_collection: chromadb.Collection
    ) -> None:
        from writer.services.vector_store import index_source, query_sources

        source_id = uuid.uuid4()
        chunks = ["The sky is blue.", "Water is wet.", "Fire is hot."]

        with patch(
            "writer.services.vector_store.get_collection",
            return_value=ephemeral_collection,
        ):
            index_source(source_id, chunks)
            result = query_sources("What colour is the sky?", top_k=3)

        assert len(result) > 0
        assert any("sky" in r or "blue" in r for r in result)

    def test_index_delete_then_query_returns_empty(
        self, ephemeral_collection: chromadb.Collection
    ) -> None:
        from writer.services.vector_store import delete_source_chunks, index_source, query_sources

        source_id = uuid.uuid4()
        chunks = ["Unique content about purple elephants that dance.", "More elephant content."]

        with patch(
            "writer.services.vector_store.get_collection",
            return_value=ephemeral_collection,
        ):
            index_source(source_id, chunks)
            delete_source_chunks(source_id)
            result = query_sources("purple elephants", top_k=5)

        assert result == [] or not any("elephant" in r for r in result)
