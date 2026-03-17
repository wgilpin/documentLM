"""Unit tests for source_service — TDD."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from writer.models.enums import IndexingStatus, SourceType
from writer.models.schemas import SourceCreate, SourceResponse


def _make_source(**kwargs: object) -> MagicMock:
    defaults = {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "source_type": SourceType.note,
        "title": "Test Source",
        "content": "some text",
        "url": None,
        "indexing_status": IndexingStatus.completed,
        "error_message": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestAddSource:
    async def test_add_note_returns_source_response(self) -> None:
        from writer.services.source_service import add_source

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        doc_id = uuid.uuid4()
        data = SourceCreate(
            document_id=doc_id, source_type=SourceType.note, title="My Note", content="text"
        )

        user_id = uuid.uuid4()
        with patch("writer.services.source_service.Source") as MockSource:
            instance = _make_source(document_id=doc_id, source_type=SourceType.note)
            MockSource.return_value = instance
            result = await add_source(db, data, user_id)

        assert isinstance(result, SourceResponse)

    async def test_add_url_returns_source_response(self) -> None:
        from writer.services.source_service import add_source

        doc_id = uuid.uuid4()
        instance = _make_source(
            document_id=doc_id, source_type=SourceType.url, url="https://example.com"
        )
        no_dupe = MagicMock()
        no_dupe.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute = AsyncMock(return_value=no_dupe)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        data = SourceCreate(
            document_id=doc_id,
            source_type=SourceType.url,
            title="A Link",
            content="summary",
            url="https://example.com",
        )

        with (
            patch("writer.services.source_service.Source") as MockSource,
            patch("writer.services.source_service.select"),
        ):
            MockSource.return_value = instance
            result = await add_source(db, data, uuid.uuid4())

        assert isinstance(result, SourceResponse)

    async def test_add_url_skips_duplicate(self) -> None:
        from writer.services.source_service import add_source

        doc_id = uuid.uuid4()
        existing = _make_source(
            document_id=doc_id, source_type=SourceType.url, url="https://example.com"
        )
        dupe_result = MagicMock()
        dupe_result.scalar_one_or_none.return_value = existing

        db = AsyncMock()
        db.execute = AsyncMock(return_value=dupe_result)
        db.add = MagicMock()

        data = SourceCreate(
            document_id=doc_id,
            source_type=SourceType.url,
            title="A Link",
            content="summary",
            url="https://example.com",
        )

        with patch("writer.services.source_service.select"):
            result = await add_source(db, data, uuid.uuid4())

        db.add.assert_not_called()
        assert isinstance(result, SourceResponse)


class TestAddSourcePdf:
    async def test_add_pdf_raises_parse_error_on_invalid_bytes(self) -> None:
        from writer.services.source_service import PdfParseError, add_source_pdf

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        doc_id = uuid.uuid4()

        user_id = uuid.uuid4()
        with (
            patch(
                "writer.services.source_service._extract_pdf_text",
                side_effect=Exception("bad pdf"),
            ),
            pytest.raises(PdfParseError),
        ):
            await add_source_pdf(db, doc_id, "Bad PDF", b"not-a-pdf", user_id)

    async def test_add_pdf_extracts_text(self) -> None:
        from writer.services.source_service import add_source_pdf

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        doc_id = uuid.uuid4()
        fake_pdf = b"%PDF-fake"

        user_id = uuid.uuid4()
        with (
            patch("writer.services.source_service._extract_pdf_text", return_value="extracted"),
            patch("writer.services.source_service.Source") as MockSource,
        ):
            instance = _make_source(
                document_id=doc_id,
                source_type=SourceType.pdf,
                content="extracted",
            )
            MockSource.return_value = instance
            result = await add_source_pdf(db, doc_id, "My PDF", fake_pdf, user_id)

        assert isinstance(result, SourceResponse)
        assert result.content == "extracted"


class TestListSources:
    async def test_list_returns_source_responses(self) -> None:
        from writer.services.source_service import list_sources

        db = AsyncMock()
        sources = [_make_source(), _make_source()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sources
        db.execute = AsyncMock(return_value=mock_result)

        result = await list_sources(db, uuid.uuid4(), uuid.uuid4())
        assert isinstance(result, list)
        assert all(isinstance(s, SourceResponse) for s in result)


class TestDeleteSource:
    async def test_delete_removes_source(self) -> None:
        from writer.services.source_service import delete_source

        db = AsyncMock()
        source_obj = _make_source()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        await delete_source(db, source_obj.id, uuid.uuid4())
        db.delete.assert_called_once_with(source_obj)

    async def test_delete_raises_on_not_found(self) -> None:
        from writer.services.source_service import SourceNotFoundError, delete_source

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(SourceNotFoundError):
            await delete_source(db, uuid.uuid4(), uuid.uuid4())

    async def test_delete_calls_vector_store_delete_before_db_delete(self) -> None:
        """delete_source must call delete_source_chunks before deleting the DB record."""
        from writer.services.source_service import delete_source

        db = AsyncMock()
        source_obj = _make_source()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        user_id = uuid.uuid4()
        call_order: list[str] = []

        def track_vs_delete(sid: object, uid: object) -> None:
            call_order.append("vector_store")

        db.delete.side_effect = lambda _: call_order.append("db_delete")

        with patch(
            "writer.services.source_service.vector_store.delete_source_chunks",
            side_effect=track_vs_delete,
        ):
            await delete_source(db, source_obj.id, user_id)

        assert call_order == ["vector_store", "db_delete"]


class TestGetSource:
    async def test_get_source_returns_source(self) -> None:
        from writer.services.source_service import get_source

        db = AsyncMock()
        source_obj = _make_source()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source_obj
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_source(db, source_obj.id, uuid.uuid4())

        assert isinstance(result, SourceResponse)
        assert result.id == source_obj.id

    async def test_get_source_raises_not_found(self) -> None:
        from writer.services.source_service import SourceNotFoundError, get_source

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(SourceNotFoundError):
            await get_source(db, uuid.uuid4(), uuid.uuid4())


class TestDeleteSourceOrdering:
    async def test_delete_propagates_vector_store_exception_without_db_delete(self) -> None:
        """If delete_source_chunks raises, the DB record must NOT be deleted."""
        from writer.services.source_service import delete_source

        db = AsyncMock()
        source_obj = _make_source()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        with (
            patch(
                "writer.services.source_service.vector_store.delete_source_chunks",
                side_effect=RuntimeError("chroma down"),
            ),
            pytest.raises(RuntimeError, match="chroma down"),
        ):
            await delete_source(db, source_obj.id, uuid.uuid4())

        db.delete.assert_not_called()
