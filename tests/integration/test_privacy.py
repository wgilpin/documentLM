"""Integration tests for document privacy toggle (User Story 5).

Covers:
- Toggling doc A to private → chunks excluded from other-doc queries
- Toggling back to non-private → chunks included
- Within private doc A → own chunks still accessible
- update_privacy() correctly updates ChromaDB is_private metadata

Uses chromadb.EphemeralClient — no filesystem side-effects.
"""

import uuid
from unittest.mock import patch

import chromadb


def _make_ephemeral_get_collection() -> object:
    """Return a get_collection replacement backed by a single shared ephemeral client."""
    client = chromadb.EphemeralClient()

    def get_collection(user_id: uuid.UUID) -> chromadb.Collection:
        return client.get_or_create_collection(f"user_{user_id.hex}")

    return get_collection


class TestPrivacyToggle:
    def test_toggle_private_excludes_chunks_from_other_doc_query(self) -> None:
        """After marking doc A private, its chunks are not returned for doc B queries."""
        from writer.services.vector_store import index_source, query_sources, update_privacy

        user_id = uuid.uuid4()
        doc_a_id = uuid.uuid4()
        doc_b_id = uuid.uuid4()
        source_id = uuid.uuid4()

        fn = _make_ephemeral_get_collection()
        with patch("writer.services.vector_store.get_collection", side_effect=fn):
            # Index doc A as non-private
            index_source(
                source_id,
                doc_a_id,
                ["Capybara fact: they are social animals."],
                user_id,
                is_private=False,
            )

            # Verify it's accessible from doc B before going private
            before = query_sources("capybara", user_id, doc_b_id, is_private_doc=False, top_k=3)
            assert len(before) > 0

            # Mark doc A private
            update_privacy(user_id, doc_a_id, is_private=True)

            # Now querying from doc B should not see doc A's chunks
            after = query_sources("capybara", user_id, doc_b_id, is_private_doc=False, top_k=3)

        assert after == [] or not any("capybara" in r.lower() for r in after)

    def test_toggle_back_to_non_private_restores_accessibility(self) -> None:
        """After toggling private then back to non-private, chunks are accessible again."""
        from writer.services.vector_store import index_source, query_sources, update_privacy

        user_id = uuid.uuid4()
        doc_a_id = uuid.uuid4()
        doc_b_id = uuid.uuid4()
        source_id = uuid.uuid4()

        fn = _make_ephemeral_get_collection()
        with patch("writer.services.vector_store.get_collection", side_effect=fn):
            index_source(
                source_id, doc_a_id, ["Axolotl regeneration facts."], user_id, is_private=False
            )

            # Make private
            update_privacy(user_id, doc_a_id, is_private=True)

            # Make non-private again
            update_privacy(user_id, doc_a_id, is_private=False)

            # Should now be accessible from doc B
            result = query_sources("axolotl", user_id, doc_b_id, is_private_doc=False, top_k=3)

        assert len(result) > 0
        assert any("axolotl" in r.lower() for r in result)

    def test_private_doc_own_chunks_accessible(self) -> None:
        """Even when a doc is private, its own chunks are accessible within the doc's context."""
        from writer.services.vector_store import index_source, query_sources, update_privacy

        user_id = uuid.uuid4()
        private_doc_id = uuid.uuid4()
        source_id = uuid.uuid4()

        fn = _make_ephemeral_get_collection()
        with patch("writer.services.vector_store.get_collection", side_effect=fn):
            index_source(
                source_id,
                private_doc_id,
                ["Echidna spines are modified hairs."],
                user_id,
                is_private=False,
            )
            update_privacy(user_id, private_doc_id, is_private=True)

            # Within-doc query (is_private_doc=True) still finds own chunks
            result = query_sources("echidna", user_id, private_doc_id, is_private_doc=True, top_k=3)

        assert len(result) > 0
        assert any("echidna" in r.lower() for r in result)

    def test_update_privacy_changes_metadata_in_chromadb(self) -> None:
        """update_privacy sets is_private metadata on all doc chunks correctly."""
        from writer.services.vector_store import index_source, update_privacy

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()

        client = chromadb.EphemeralClient()
        collection = client.get_or_create_collection(f"user_{user_id.hex}")

        with patch("writer.services.vector_store.get_collection", return_value=collection):
            index_source(source_id, doc_id, ["chunk one", "chunk two"], user_id, is_private=False)

            # Verify initial state
            before = collection.get(where={"document_id": str(doc_id)}, include=["metadatas"])
            assert all(m["is_private"] is False for m in (before["metadatas"] or []))

            # Toggle to private
            update_privacy(user_id, doc_id, is_private=True)

            after = collection.get(where={"document_id": str(doc_id)}, include=["metadatas"])
            assert all(m["is_private"] is True for m in (after["metadatas"] or []))
