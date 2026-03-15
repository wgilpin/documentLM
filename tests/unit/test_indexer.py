"""Unit tests for indexer service — TDD."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from writer.models.enums import IndexingStatus, SourceType


def _make_source_orm(**kwargs: object) -> MagicMock:
    defaults = {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "source_type": SourceType.note,
        "title": "Test Source",
        "content": "Sentence one. Sentence two. Sentence three.",
        "url": None,
        "indexing_status": IndexingStatus.pending,
        "error_message": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestRunIndexing:
    async def test_status_transitions_pending_to_completed(self) -> None:
        from writer.services.indexer import run_indexing

        source = _make_source_orm()
        source_id = source.id

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        statuses: list[IndexingStatus] = []

        def capture_status(val: IndexingStatus) -> None:
            statuses.append(val)

        type(source).indexing_status = property(
            lambda self: statuses[-1] if statuses else IndexingStatus.pending,
            lambda self, v: capture_status(v),
        )

        with (
            patch("writer.services.indexer.chunk_sentences", return_value=["c1", "c2"]),
            patch("writer.services.indexer.vector_store") as mock_vs,
        ):
            mock_vs.index_source = MagicMock()
            await run_indexing(source_id, db)

        assert IndexingStatus.processing in statuses
        assert IndexingStatus.completed in statuses

    async def test_chunk_sentences_called_on_source_content(self) -> None:
        from writer.services.indexer import run_indexing

        source = _make_source_orm(content="My content here.")
        source_id = source.id

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        with (
            patch("writer.services.indexer.chunk_sentences", return_value=["chunk"]) as mock_chunk,
            patch("writer.services.indexer.vector_store") as mock_vs,
        ):
            mock_vs.index_source = MagicMock()
            await run_indexing(source_id, db)

        mock_chunk.assert_called_once_with("My content here.", chunk_size=1000, chunk_overlap=100)

    async def test_on_exception_status_set_to_failed_with_error_message(self) -> None:
        from writer.services.indexer import run_indexing

        source = _make_source_orm()
        source_id = source.id

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        with (
            patch(
                "writer.services.indexer.chunk_sentences",
                side_effect=RuntimeError("embed failed"),
            ),
            patch("writer.services.indexer.vector_store"),
        ):
            await run_indexing(source_id, db)

        assert source.indexing_status == IndexingStatus.failed
        assert "embed failed" in str(source.error_message)

    async def test_noop_when_already_processing(self) -> None:
        from writer.services.indexer import run_indexing

        source = _make_source_orm(indexing_status=IndexingStatus.processing)
        source_id = source.id

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("writer.services.indexer.chunk_sentences") as mock_chunk,
            patch("writer.services.indexer.vector_store"),
        ):
            await run_indexing(source_id, db)

        mock_chunk.assert_not_called()

    async def test_noop_when_already_completed(self) -> None:
        from writer.services.indexer import run_indexing

        source = _make_source_orm(indexing_status=IndexingStatus.completed)
        source_id = source.id

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("writer.services.indexer.chunk_sentences") as mock_chunk,
            patch("writer.services.indexer.vector_store"),
        ):
            await run_indexing(source_id, db)

        mock_chunk.assert_not_called()

    async def test_noop_when_source_not_found(self) -> None:
        from writer.services.indexer import run_indexing

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("writer.services.indexer.chunk_sentences") as mock_chunk,
            patch("writer.services.indexer.vector_store"),
        ):
            await run_indexing(uuid.uuid4(), db)

        mock_chunk.assert_not_called()
