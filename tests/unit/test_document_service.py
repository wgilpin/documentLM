"""Unit tests for document_service — TDD (write first, confirm fail, then implement)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from writer.models.schemas import DocumentCreate, DocumentResponse, DocumentSummary, DocumentUpdate


def _make_doc(**kwargs: object) -> MagicMock:
    defaults = {
        "id": uuid.uuid4(),
        "title": "Test Doc",
        "content": "Hello world",
        "overview": None,
        "is_private": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    doc = MagicMock()
    for k, v in defaults.items():
        setattr(doc, k, v)
    return doc


class TestCreateDocument:
    async def test_create_returns_document_response(self) -> None:
        from writer.services.document_service import create_document

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        data = DocumentCreate(title="My Doc", content="body")

        doc_obj = _make_doc(title="My Doc", content="body")
        db.refresh.side_effect = lambda obj: setattr(obj, "id", doc_obj.id) or None

        user_id = uuid.uuid4()
        with patch("writer.services.document_service.Document") as MockDoc:
            instance = _make_doc(title="My Doc", content="body")
            MockDoc.return_value = instance
            result = await create_document(db, data, user_id)

        assert isinstance(result, DocumentResponse)

    async def test_create_calls_db_add_and_flush(self) -> None:
        from writer.services.document_service import create_document

        db = AsyncMock()
        db.add = MagicMock()

        user_id = uuid.uuid4()
        data = DocumentCreate(title="My Doc")
        with patch("writer.services.document_service.Document") as MockDoc:
            instance = _make_doc(title="My Doc", content="")
            MockDoc.return_value = instance
            await create_document(db, data, user_id)

        db.add.assert_called_once()
        db.flush.assert_called_once()


class TestGetDocument:
    async def test_get_returns_document_response(self) -> None:
        from writer.services.document_service import get_document

        db = AsyncMock()
        doc_id = uuid.uuid4()
        doc_obj = _make_doc(id=doc_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc_obj
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_document(db, doc_id, uuid.uuid4())
        assert isinstance(result, DocumentResponse)
        assert result.id == doc_id

    async def test_get_raises_on_not_found(self) -> None:
        from writer.services.document_service import DocumentNotFoundError, get_document

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await get_document(db, uuid.uuid4(), uuid.uuid4())


class TestListDocuments:
    async def test_list_returns_list_of_summaries(self) -> None:
        from writer.services.document_service import list_documents

        db = AsyncMock()
        docs = [_make_doc(), _make_doc()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = docs
        db.execute = AsyncMock(return_value=mock_result)

        result = await list_documents(db, uuid.uuid4())
        assert isinstance(result, list)
        assert all(isinstance(r, DocumentSummary) for r in result)


class TestUpdateDocument:
    async def test_update_returns_document_response(self) -> None:
        from writer.services.document_service import update_document

        db = AsyncMock()
        doc_id = uuid.uuid4()
        doc_obj = _make_doc(id=doc_id, title="Old", content="old content")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        data = DocumentUpdate(title="New Title")
        result = await update_document(db, doc_id, data, uuid.uuid4())
        assert isinstance(result, DocumentResponse)

    async def test_update_raises_on_not_found(self) -> None:
        from writer.services.document_service import DocumentNotFoundError, update_document

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await update_document(db, uuid.uuid4(), DocumentUpdate(title="x"), uuid.uuid4())


class TestDeleteDocument:
    async def test_delete_removes_document(self) -> None:
        from writer.services.document_service import delete_document

        db = AsyncMock()
        doc_obj = _make_doc()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        await delete_document(db, doc_obj.id, uuid.uuid4())
        db.delete.assert_called_once_with(doc_obj)

    async def test_delete_raises_on_not_found(self) -> None:
        from writer.services.document_service import DocumentNotFoundError, delete_document

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await delete_document(db, uuid.uuid4(), uuid.uuid4())


