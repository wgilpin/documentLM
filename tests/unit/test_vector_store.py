"""Unit tests for vector_store service — TDD."""

import uuid
from unittest.mock import MagicMock, patch


class TestIndexSource:
    def test_chunk_ids_follow_format(self) -> None:
        """Chunk IDs must be '{source_id}_{i}'."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        chunks = ["chunk zero", "chunk one", "chunk two"]

        mock_collection = MagicMock()

        with patch("writer.services.vector_store.get_collection", return_value=mock_collection):
            index_source(source_id, document_id, chunks)

        call_kwargs = mock_collection.add.call_args.kwargs
        expected_ids = [f"{source_id}_0", f"{source_id}_1", f"{source_id}_2"]
        assert call_kwargs["ids"] == expected_ids

    def test_metadata_contains_source_id_and_document_id(self) -> None:
        """Each chunk metadata must include source_id and document_id as strings."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        chunks = ["alpha", "beta"]

        mock_collection = MagicMock()

        with patch("writer.services.vector_store.get_collection", return_value=mock_collection):
            index_source(source_id, document_id, chunks)

        call_kwargs = mock_collection.add.call_args.kwargs
        for meta in call_kwargs["metadatas"]:
            assert meta["source_id"] == str(source_id)
            assert meta["document_id"] == str(document_id)

    def test_collection_add_called_with_correct_documents(self) -> None:
        """collection.add must receive the chunk texts as documents."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        chunks = ["first chunk", "second chunk"]

        mock_collection = MagicMock()

        with patch("writer.services.vector_store.get_collection", return_value=mock_collection):
            index_source(source_id, document_id, chunks)

        call_kwargs = mock_collection.add.call_args.kwargs
        assert call_kwargs["documents"] == chunks

    def test_empty_chunks_still_calls_add(self) -> None:
        """Even with zero chunks, collection.add is called (idempotent)."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch("writer.services.vector_store.get_collection", return_value=mock_collection):
            index_source(source_id, document_id, [])

        mock_collection.add.assert_called_once()


class TestQuerySources:
    def test_calls_collection_query_with_correct_args(self) -> None:
        from writer.services.vector_store import query_sources

        document_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"documents": [["chunk A", "chunk B"]]}

        with patch("writer.services.vector_store.get_collection", return_value=mock_collection):
            result = query_sources("find something", document_id, top_k=5)

        mock_collection.query.assert_called_once_with(
            query_texts=["find something"],
            n_results=5,
            where={"document_id": str(document_id)},
        )
        assert result == ["chunk A", "chunk B"]

    def test_returns_flattened_documents_list(self) -> None:
        from writer.services.vector_store import query_sources

        document_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"documents": [["doc1", "doc2", "doc3"]]}

        with patch("writer.services.vector_store.get_collection", return_value=mock_collection):
            result = query_sources("query text", document_id)

        assert result == ["doc1", "doc2", "doc3"]


class TestDeleteSourceChunks:
    def test_calls_delete_with_source_id_filter(self) -> None:
        from writer.services.vector_store import delete_source_chunks

        source_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch("writer.services.vector_store.get_collection", return_value=mock_collection):
            delete_source_chunks(source_id)

        mock_collection.delete.assert_called_once_with(where={"source_id": str(source_id)})
