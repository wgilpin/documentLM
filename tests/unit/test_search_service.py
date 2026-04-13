"""Unit tests for search_service — TDD."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from writer.services.vector_store import ChunkResult


def _make_chunk(text: str, source_id: str | None = None) -> ChunkResult:
    sid = source_id or str(uuid.uuid4())
    return ChunkResult(text=text, source_id=sid, document_id=str(uuid.uuid4()))


class TestSearchDocumentCorpus:
    async def test_returns_search_response_with_results(self) -> None:
        from writer.models.schemas import SearchResponse
        from writer.services.search_service import search_document_corpus

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()

        chunks = [_make_chunk("Residents reported health issues", str(source_id))]

        source_obj = MagicMock()
        source_obj.title = "Interview Transcripts 2024"
        source_result = MagicMock()
        source_result.scalar_one_or_none.return_value = source_obj

        db = AsyncMock()
        db.execute = AsyncMock(return_value=source_result)

        with patch(
            "writer.services.search_service.query_sources_with_metadata", return_value=chunks
        ):
            result = await search_document_corpus("health impacts", user_id, doc_id, db)

        assert isinstance(result, SearchResponse)
        assert result.query == "health impacts"
        assert len(result.results) == 1
        assert result.results[0].text == "Residents reported health issues"
        assert result.results[0].source_title == "Interview Transcripts 2024"
        assert result.results[0].source_id == source_id

    async def test_no_results_returns_empty_search_response(self) -> None:
        from writer.models.schemas import SearchResponse
        from writer.services.search_service import search_document_corpus

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        db = AsyncMock()

        with patch("writer.services.search_service.query_sources_with_metadata", return_value=[]):
            result = await search_document_corpus("nonexistent query", user_id, doc_id, db)

        assert isinstance(result, SearchResponse)
        assert result.results == []
        assert result.query == "nonexistent query"

    async def test_source_not_found_skips_result(self) -> None:
        """If a source_id in chunk results no longer exists in DB, that chunk is skipped."""
        from writer.models.schemas import SearchResponse
        from writer.services.search_service import search_document_corpus

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chunks = [_make_chunk("Some text", str(uuid.uuid4()))]

        source_result = MagicMock()
        source_result.scalar_one_or_none.return_value = None  # Source not found

        db = AsyncMock()
        db.execute = AsyncMock(return_value=source_result)

        with patch(
            "writer.services.search_service.query_sources_with_metadata", return_value=chunks
        ):
            result = await search_document_corpus("query", user_id, doc_id, db)

        assert isinstance(result, SearchResponse)
        assert result.results == []
