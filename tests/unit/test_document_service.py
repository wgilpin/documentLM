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

        with patch("writer.services.document_service.Document") as MockDoc:
            instance = _make_doc(title="My Doc", content="body")
            MockDoc.return_value = instance
            result = await create_document(db, data)

        assert isinstance(result, DocumentResponse)

    async def test_create_calls_db_add_and_flush(self) -> None:
        from writer.services.document_service import create_document

        db = AsyncMock()
        db.add = MagicMock()

        data = DocumentCreate(title="My Doc")
        with patch("writer.services.document_service.Document") as MockDoc:
            instance = _make_doc(title="My Doc", content="")
            MockDoc.return_value = instance
            await create_document(db, data)

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

        result = await get_document(db, doc_id)
        assert isinstance(result, DocumentResponse)
        assert result.id == doc_id

    async def test_get_raises_on_not_found(self) -> None:
        from writer.services.document_service import DocumentNotFoundError, get_document

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await get_document(db, uuid.uuid4())


class TestListDocuments:
    async def test_list_returns_list_of_summaries(self) -> None:
        from writer.services.document_service import list_documents

        db = AsyncMock()
        docs = [_make_doc(), _make_doc()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = docs
        db.execute = AsyncMock(return_value=mock_result)

        result = await list_documents(db)
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
        result = await update_document(db, doc_id, data)
        assert isinstance(result, DocumentResponse)

    async def test_update_raises_on_not_found(self) -> None:
        from writer.services.document_service import DocumentNotFoundError, update_document

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await update_document(db, uuid.uuid4(), DocumentUpdate(title="x"))


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

        await delete_document(db, doc_obj.id)
        db.delete.assert_called_once_with(doc_obj)

    async def test_delete_raises_on_not_found(self) -> None:
        from writer.services.document_service import DocumentNotFoundError, delete_document

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await delete_document(db, uuid.uuid4())


class TestAcceptRejectSuggestion:
    def _make_suggestion(self, **kwargs: object) -> MagicMock:
        from writer.models.enums import SuggestionStatus

        defaults = {
            "id": uuid.uuid4(),
            "comment_id": uuid.uuid4(),
            "original_text": "old",
            "suggested_text": "new text",
            "status": SuggestionStatus.pending,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        }
        defaults.update(kwargs)
        obj = MagicMock()
        for k, v in defaults.items():
            setattr(obj, k, v)
        return obj

    def _make_comment(self, **kwargs: object) -> MagicMock:
        from writer.models.enums import CommentStatus

        defaults = {
            "id": uuid.uuid4(),
            "document_id": uuid.uuid4(),
            "selection_start": 0,
            "selection_end": 3,
            "selected_text": "old",
            "body": "change it",
            "status": CommentStatus.open,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        }
        defaults.update(kwargs)
        obj = MagicMock()
        for k, v in defaults.items():
            setattr(obj, k, v)
        return obj

    async def test_accept_suggestion_replaces_text(self) -> None:
        import json

        from writer.services.document_service import accept_suggestion

        doc_id = uuid.uuid4()
        node_id = "test-node-1"
        suggestion = self._make_suggestion(original_text="old", suggested_text="NEW TEXT")
        comment = self._make_comment(
            id=suggestion.comment_id,
            document_id=doc_id,
            selection_start=0,
            selection_end=3,
            selected_text="old",
            selected_node_id=node_id,
        )
        tiptap_content = json.dumps({
            "type": "doc",
            "content": [{"type": "paragraph", "attrs": {"id": node_id}, "content": [{"type": "text", "text": "old"}]}],
        })
        doc_obj = _make_doc(id=doc_id, content=tiptap_content)

        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        def make_result(val: object) -> MagicMock:
            r = MagicMock()
            r.scalar_one_or_none.return_value = val
            return r

        db.execute = AsyncMock(
            side_effect=[make_result(suggestion), make_result(comment), make_result(doc_obj)]
        )

        result = await accept_suggestion(db, suggestion.id)
        assert isinstance(result, DocumentResponse)
        # Content should have suggestion applied (stored as TipTap JSON)
        assert "NEW TEXT" in result.content

    async def test_reject_suggestion_sets_status(self) -> None:
        from writer.models.schemas import SuggestionResponse
        from writer.services.document_service import reject_suggestion

        suggestion = self._make_suggestion()
        comment = self._make_comment(id=suggestion.comment_id)

        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        def make_result(val: object) -> MagicMock:
            r = MagicMock()
            r.scalar_one_or_none.return_value = val
            return r

        db.execute = AsyncMock(side_effect=[make_result(suggestion), make_result(comment)])

        result = await reject_suggestion(db, suggestion.id)
        assert isinstance(result, SuggestionResponse)
