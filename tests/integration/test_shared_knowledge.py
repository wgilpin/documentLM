"""Integration tests for shared knowledge pool (User Story 4).

Non-private sources indexed under doc A are retrievable when querying from doc B
for the same user. A different user's collection is completely isolated.

Uses chromadb.EphemeralClient — no filesystem side-effects.
"""

import uuid
from unittest.mock import patch

import chromadb


def _make_ephemeral_get_collection() -> object:
    """Return a get_collection replacement backed by an ephemeral per-user ChromaDB client."""
    clients: dict[str, chromadb.ClientAPI] = {}

    def get_collection(user_id: uuid.UUID) -> chromadb.Collection:
        hex_id = user_id.hex
        if hex_id not in clients:
            clients[hex_id] = chromadb.EphemeralClient()
        return clients[hex_id].get_or_create_collection(f"user_{hex_id}")

    return get_collection


class TestSharedKnowledgePool:
    def test_non_private_chunk_from_doc_a_retrieved_in_doc_b_context(self) -> None:
        """Chunk indexed under doc A is returned when querying from doc B (same user)."""
        from writer.services.vector_store import index_source, query_sources

        user_id = uuid.uuid4()
        doc_a_id = uuid.uuid4()
        doc_b_id = uuid.uuid4()
        source_id = uuid.uuid4()

        with patch(
            "writer.services.vector_store.get_collection",
            side_effect=_make_ephemeral_get_collection(),
        ):
            # Index under doc A (non-private)
            index_source(
                source_id, doc_a_id, ["Flamingos are pink birds."], user_id, is_private=False
            )

            # Query from doc B context (non-private doc) → should still find doc A's chunk
            result = query_sources("flamingos", user_id, doc_b_id, is_private_doc=False, top_k=3)

        assert len(result) > 0
        assert any("flamingo" in r.lower() or "pink" in r.lower() for r in result)

    def test_chunk_not_returned_for_different_user(self) -> None:
        """A chunk indexed under user A is NOT retrievable by user B."""
        from writer.services.vector_store import index_source, query_sources

        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()

        get_collection_fn = _make_ephemeral_get_collection()

        with patch(
            "writer.services.vector_store.get_collection",
            side_effect=get_collection_fn,
        ):
            # User A indexes a chunk
            index_source(
                source_id, doc_id, ["Secret formula about penguins."], user_a_id, is_private=False
            )

            # User B queries — empty collection for user B
            result = query_sources("penguins", user_b_id, doc_id, is_private_doc=False, top_k=5)

        assert result == []

    def test_private_doc_chunk_excluded_from_cross_doc_query(self) -> None:
        """Chunk marked is_private=True is excluded from non-private (cross-doc) queries."""
        from writer.services.vector_store import index_source, query_sources

        user_id = uuid.uuid4()
        private_doc_id = uuid.uuid4()
        other_doc_id = uuid.uuid4()
        source_id = uuid.uuid4()

        with patch(
            "writer.services.vector_store.get_collection",
            side_effect=_make_ephemeral_get_collection(),
        ):
            # Index a private chunk
            index_source(
                source_id,
                private_doc_id,
                ["Top secret otter information."],
                user_id,
                is_private=True,
            )

            # Query from another doc (non-private context) → should not find private chunk
            result = query_sources("otter", user_id, other_doc_id, is_private_doc=False, top_k=5)

        assert result == [] or not any("otter" in r.lower() for r in result)

    def test_private_doc_query_returns_own_chunks(self) -> None:
        """A private doc's own chunks are returned when querying within that same doc."""
        from writer.services.vector_store import index_source, query_sources

        user_id = uuid.uuid4()
        private_doc_id = uuid.uuid4()
        source_id = uuid.uuid4()

        with patch(
            "writer.services.vector_store.get_collection",
            side_effect=_make_ephemeral_get_collection(),
        ):
            index_source(
                source_id,
                private_doc_id,
                ["Classified narwhal details."],
                user_id,
                is_private=True,
            )

            # Query within the private doc itself → finds own chunks
            result = query_sources("narwhal", user_id, private_doc_id, is_private_doc=True, top_k=3)

        assert len(result) > 0
        assert any("narwhal" in r.lower() for r in result)
