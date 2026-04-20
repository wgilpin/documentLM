"""Unit tests for vector_store service — TDD."""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch


def _assert_entity_type_filter(where: object, expected: str) -> None:
    """Assert that a Chroma `where` dict includes `entity_type == expected` at any depth.

    Handles both flat (`{"entity_type": {"$eq": "source"}}`) and `$and`-wrapped shapes.
    """
    assert isinstance(where, dict)
    if "entity_type" in where:
        inner = where["entity_type"]
        if isinstance(inner, dict):
            assert inner.get("$eq") == expected, where
        else:
            assert inner == expected, where
        return
    if "$and" in where:
        clauses = where["$and"]
        assert isinstance(clauses, list)
        for clause in clauses:
            if isinstance(clause, dict) and "entity_type" in clause:
                inner = clause["entity_type"]
                if isinstance(inner, dict):
                    assert inner.get("$eq") == expected, where
                else:
                    assert inner == expected, where
                return
    raise AssertionError(f"entity_type filter missing from where clause: {where!r}")


class TestIndexSource:
    def test_chunk_ids_follow_format(self) -> None:
        """Chunk IDs must be '{source_id}_{i}'."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        user_id = uuid.uuid4()
        chunks = ["chunk zero", "chunk one", "chunk two"]

        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            index_source(source_id, document_id, chunks, user_id)

        call_kwargs = mock_collection.add.call_args.kwargs
        expected_ids = [f"{source_id}_0", f"{source_id}_1", f"{source_id}_2"]
        assert call_kwargs["ids"] == expected_ids

    def test_metadata_contains_source_id_and_document_id(self) -> None:
        """Each chunk metadata must include source_id and document_id as strings."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        user_id = uuid.uuid4()
        chunks = ["alpha", "beta"]

        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            index_source(source_id, document_id, chunks, user_id)

        call_kwargs = mock_collection.add.call_args.kwargs
        for meta in call_kwargs["metadatas"]:
            assert meta["source_id"] == str(source_id)
            assert meta["document_id"] == str(document_id)

    def test_collection_add_called_with_correct_documents(self) -> None:
        """collection.add must receive the chunk texts as documents."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        user_id = uuid.uuid4()
        chunks = ["first chunk", "second chunk"]

        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            index_source(source_id, document_id, chunks, user_id)

        call_kwargs = mock_collection.add.call_args.kwargs
        assert call_kwargs["documents"] == chunks

    def test_empty_chunks_still_calls_add(self) -> None:
        """Even with zero chunks, collection.add is called (idempotent)."""
        from writer.services.vector_store import index_source

        source_id = uuid.uuid4()
        document_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            index_source(source_id, document_id, [], user_id)

        mock_collection.add.assert_called_once()


class TestQuerySources:
    def test_calls_collection_query_with_correct_args(self) -> None:
        from writer.services.vector_store import query_sources

        user_id = uuid.uuid4()
        document_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {"documents": [["chunk A", "chunk B"]]}

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            result = query_sources("find something", user_id, document_id, top_k=5)

        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["query_texts"] == ["find something"]
        assert call_kwargs["n_results"] == 5
        where = call_kwargs["where"]
        # Must filter out snippets — an entity_type: "source" predicate must be present.
        _assert_entity_type_filter(where, "source")
        assert result == ["chunk A", "chunk B"]

    def test_returns_flattened_documents_list(self) -> None:
        from writer.services.vector_store import query_sources

        user_id = uuid.uuid4()
        document_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {"documents": [["doc1", "doc2", "doc3"]]}

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            result = query_sources("query text", user_id, document_id)

        assert result == ["doc1", "doc2", "doc3"]

    def test_returns_empty_list_when_collection_empty(self) -> None:
        from writer.services.vector_store import query_sources

        user_id = uuid.uuid4()
        document_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            result = query_sources("query text", user_id, document_id)

        assert result == []
        mock_collection.query.assert_not_called()


class TestQuerySourcesTiered:
    def test_buckets_chunks_by_document_id(self) -> None:
        from writer.services.vector_store import query_sources_tiered

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        other_doc_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "documents": [["this doc chunk", "other doc chunk"]],
            "metadatas": [
                [
                    {"document_id": str(doc_id), "source_id": "x", "is_private": False},
                    {"document_id": str(other_doc_id), "source_id": "y", "is_private": False},
                ]
            ],
            "distances": [[0.3, 0.4]],
        }

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            doc_chunks, other_chunks = query_sources_tiered("query", user_id, doc_id)

        assert doc_chunks == ["this doc chunk"]
        assert other_chunks == ["other doc chunk"]

    def test_drops_chunks_exceeding_max_distance(self) -> None:
        from writer.services.vector_store import query_sources_tiered

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        other_doc_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "documents": [["close chunk", "far chunk"]],
            "metadatas": [
                [
                    {"document_id": str(doc_id), "source_id": "x", "is_private": False},
                    {"document_id": str(other_doc_id), "source_id": "y", "is_private": False},
                ]
            ],
            "distances": [[0.5, 1.5]],
        }

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            doc_chunks, other_chunks = query_sources_tiered(
                "query", user_id, doc_id, max_distance=1.0
            )

        assert doc_chunks == ["close chunk"]
        assert other_chunks == []  # 1.5 > 1.0, discarded

    def test_returns_empty_tuples_when_collection_empty(self) -> None:
        from writer.services.vector_store import query_sources_tiered

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            doc_chunks, other_chunks = query_sources_tiered("query", user_id, doc_id)

        assert doc_chunks == []
        assert other_chunks == []
        mock_collection.query.assert_not_called()

    def test_private_doc_only_queries_this_document(self) -> None:
        from writer.services.vector_store import query_sources_tiered

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.query.return_value = {
            "documents": [["chunk A"]],
            "metadatas": [[{"document_id": str(doc_id), "source_id": "x", "is_private": True}]],
            "distances": [[0.2]],
        }

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            doc_chunks, other_chunks = query_sources_tiered(
                "query", user_id, doc_id, is_private_doc=True
            )

        assert doc_chunks == ["chunk A"]
        assert other_chunks == []
        call_kwargs = mock_collection.query.call_args.kwargs
        where = call_kwargs["where"]
        _assert_entity_type_filter(where, "source")
        # document_id filter must still be present somewhere.
        assert str(doc_id) in repr(where)


class TestDeleteSourceChunks:
    def test_calls_delete_with_source_id_filter(self) -> None:
        from writer.services.vector_store import delete_source_chunks

        source_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            delete_source_chunks(source_id, user_id)

        mock_collection.delete.assert_called_once_with(where={"source_id": str(source_id)})


class TestQuerySourcesWithMetadataEntityFilter:
    def test_adds_entity_type_source_filter(self) -> None:
        from writer.services.vector_store import query_sources_with_metadata

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 3
        mock_collection.query.return_value = {
            "documents": [["chunk"]],
            "metadatas": [[{"source_id": "s", "document_id": str(doc_id), "is_private": False}]],
        }

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            query_sources_with_metadata("q", user_id, doc_id)

        where = mock_collection.query.call_args.kwargs["where"]
        _assert_entity_type_filter(where, "source")


class TestIndexSnippet:
    def test_uses_deterministic_snip_id_and_entity_type_metadata(self) -> None:
        from writer.services.vector_store import index_snippet

        snippet_id = uuid.uuid4()
        document_id = uuid.uuid4()
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            index_snippet(
                snippet_id=snippet_id,
                document_id=document_id,
                text="highlight text",
                user_id=user_id,
                source_id=source_id,
                is_private=False,
            )

        # Should use upsert (idempotent) and deterministic id prefix.
        assert mock_collection.upsert.called or mock_collection.add.called
        call = (
            mock_collection.upsert.call_args
            if mock_collection.upsert.called
            else mock_collection.add.call_args
        )
        kwargs = call.kwargs
        assert kwargs["ids"] == [f"snip_{snippet_id}"]
        assert kwargs["documents"] == ["highlight text"]
        meta = kwargs["metadatas"][0]
        assert meta["entity_type"] == "snippet"
        assert meta["snippet_id"] == str(snippet_id)
        assert meta["document_id"] == str(document_id)
        assert meta["source_id"] == str(source_id)
        assert meta["is_private"] is False

    def test_source_id_none_persists_as_none_sentinel(self) -> None:
        from writer.services.vector_store import index_snippet

        snippet_id = uuid.uuid4()
        document_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            index_snippet(
                snippet_id=snippet_id,
                document_id=document_id,
                text="orphan snippet",
                user_id=user_id,
                source_id=None,
                is_private=True,
            )

        call = (
            mock_collection.upsert.call_args
            if mock_collection.upsert.called
            else mock_collection.add.call_args
        )
        meta = call.kwargs["metadatas"][0]
        assert meta["source_id"] == "none"
        assert meta["is_private"] is True

    def test_strips_urls_from_embedded_text(self) -> None:
        from writer.services.vector_store import index_snippet

        snippet_id = uuid.uuid4()
        document_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            index_snippet(
                snippet_id=snippet_id,
                document_id=document_id,
                text="see https://example.com for details",
                user_id=user_id,
                source_id=None,
                is_private=False,
            )

        call = (
            mock_collection.upsert.call_args
            if mock_collection.upsert.called
            else mock_collection.add.call_args
        )
        document = call.kwargs["documents"][0]
        assert "https://example.com" not in document


class TestDeleteSnippetEmbedding:
    def test_deletes_by_deterministic_id(self) -> None:
        from writer.services.vector_store import delete_snippet_embedding

        snippet_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_collection = MagicMock()

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            delete_snippet_embedding(snippet_id, user_id)

        mock_collection.delete.assert_called_once_with(ids=[f"snip_{snippet_id}"])


class TestQueryDocumentCorpus:
    def test_returns_sources_and_snippets_scoped_to_document(self) -> None:
        from writer.services.vector_store import query_document_corpus

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_meta = {
            "entity_type": "source",
            "source_id": "s1",
            "document_id": str(doc_id),
            "is_private": False,
        }
        snippet_meta = {
            "entity_type": "snippet",
            "snippet_id": "sn1",
            "source_id": "s1",
            "document_id": str(doc_id),
            "is_private": False,
        }
        mock_collection = MagicMock()
        mock_collection.count.return_value = 50
        mock_collection.query.return_value = {
            "documents": [["a source chunk", "a snippet"]],
            "metadatas": [[source_meta, snippet_meta]],
            "distances": [[0.4, 0.5]],
        }

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            results = query_document_corpus("query", user_id, doc_id, top_k=10)

        # Expect (text, metadata, distance) tuples for both entity types.
        assert len(results) == 2
        texts = [r[0] for r in results]
        assert "a source chunk" in texts
        assert "a snippet" in texts

        where = mock_collection.query.call_args.kwargs["where"]
        # Must scope by document_id and allow both entity types.
        assert str(doc_id) in repr(where)
        assert "snippet" in repr(where)

    def test_drops_results_above_max_distance(self) -> None:
        from writer.services.vector_store import query_document_corpus

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "documents": [["keep me", "drop me"]],
            "metadatas": [
                [
                    {
                        "entity_type": "source",
                        "source_id": "s1",
                        "document_id": str(doc_id),
                        "is_private": False,
                    },
                    {
                        "entity_type": "source",
                        "source_id": "s2",
                        "document_id": str(doc_id),
                        "is_private": False,
                    },
                ]
            ],
            "distances": [[0.5, 1.5]],
        }

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            results = query_document_corpus("query", user_id, doc_id, top_k=5)

        texts = [r[0] for r in results]
        assert texts == ["keep me"]

    def test_returns_empty_when_collection_empty(self) -> None:
        from writer.services.vector_store import query_document_corpus

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        with patch(
            "documentlm_core.services.vector_store.get_collection",
            return_value=mock_collection,
        ):
            results = query_document_corpus("query", user_id, doc_id, top_k=5)

        assert results == []
        mock_collection.query.assert_not_called()


class TestSnippetSourceDiscrimination:
    """End-to-end using a tmp Chroma path: snippets MUST NOT leak into RAG paths."""

    def test_query_sources_with_metadata_excludes_snippets(self) -> None:
        """After indexing, query_sources_with_metadata returns only sources."""
        from documentlm_core.services import vector_store as core_vs

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()
        snippet_id = uuid.uuid4()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = str(Path(tmp) / "chroma")
            # Patch the module-level client so get_collection uses the tmp path.
            with (
                patch.object(core_vs, "_client", None),
                patch.object(core_vs.settings, "chroma_path", tmp_path),
            ):
                from writer.services.vector_store import (
                    index_snippet,
                    index_source,
                    query_document_corpus,
                    query_sources_with_metadata,
                )

                index_source(
                    source_id=source_id,
                    document_id=doc_id,
                    chunks=["important source content about alpha"],
                    user_id=user_id,
                    is_private=True,
                )
                index_snippet(
                    snippet_id=snippet_id,
                    document_id=doc_id,
                    text="highlighted alpha phrase",
                    user_id=user_id,
                    source_id=source_id,
                    is_private=True,
                )

                # RAG path: must not return the snippet.
                rag_chunks = query_sources_with_metadata(
                    "alpha", user_id, doc_id, is_private_doc=True, top_k=10
                )
                rag_texts = [c["text"] for c in rag_chunks]
                assert "highlighted alpha phrase" not in rag_texts

                # Dual corpus: must return both entity types.
                dual = query_document_corpus("alpha", user_id, doc_id, top_k=10)
                dual_types = [m.get("entity_type") for _, m, _ in dual]
                assert "source" in dual_types
                assert "snippet" in dual_types
