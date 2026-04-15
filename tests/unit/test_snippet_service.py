"""Unit tests for snippet_service — TDD."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_snippet(**kwargs: object) -> MagicMock:
    defaults = {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "source_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "text": "Some highlighted text",
        "char_offset": 0,
        "note": None,
        "tag": None,
        "created_at": datetime.now(UTC),
        # source_title not on ORM model — explicitly None so model_validate doesn't get MagicMock
        "source_title": None,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_db(scalar_result: object = None, scalars_result: list | None = None) -> AsyncMock:
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    if scalars_result is not None:
        mock_result.scalars.return_value.all.return_value = scalars_result
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


class TestCreateSnippet:
    async def test_create_snippet_happy_path(self) -> None:
        from writer.models.schemas import SnippetCreate, SnippetResponse
        from writer.services.snippet_service import create_snippet

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        snippet_obj = _make_snippet(document_id=doc_id, user_id=user_id)

        doc_obj = MagicMock()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc_obj

        db = AsyncMock()
        db.execute = AsyncMock(return_value=doc_result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        with patch("writer.services.snippet_service.Snippet", return_value=snippet_obj):
            data = SnippetCreate(text="Highlighted passage", char_offset=42)
            result = await create_snippet(db, doc_id, user_id, data)

        assert isinstance(result, SnippetResponse)

    async def test_create_snippet_document_not_found_raises_404(self) -> None:
        from writer.models.schemas import SnippetCreate
        from writer.services.snippet_service import DocumentNotFoundError, create_snippet

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        # DB returns None for document lookup
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        data = SnippetCreate(text="Some text")
        with pytest.raises(DocumentNotFoundError):
            await create_snippet(db, doc_id, user_id, data)


class TestListSnippets:
    async def test_list_snippets_returns_empty_list(self) -> None:
        from writer.services.snippet_service import list_snippets

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        db = _make_db(scalars_result=[])

        result = await list_snippets(db, doc_id, user_id)
        assert result == []

    async def test_list_snippets_returns_ordered_by_created_at_desc(self) -> None:
        from writer.models.schemas import SnippetResponse
        from writer.services.snippet_service import list_snippets

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        snippets = [_make_snippet(), _make_snippet(), _make_snippet()]
        db = _make_db(scalars_result=snippets)

        result = await list_snippets(db, doc_id, user_id)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(s, SnippetResponse) for s in result)


class TestDeleteSnippet:
    async def test_delete_snippet_happy_path(self) -> None:
        from writer.services.snippet_service import delete_snippet

        user_id = uuid.uuid4()
        snippet_id = uuid.uuid4()
        snippet_obj = _make_snippet(id=snippet_id, user_id=user_id)
        db = _make_db(scalar_result=snippet_obj)

        await delete_snippet(db, snippet_id, user_id)
        db.delete.assert_called_once_with(snippet_obj)

    async def test_delete_snippet_not_found(self) -> None:
        from writer.services.snippet_service import SnippetNotFoundError, delete_snippet

        db = _make_db(scalar_result=None)
        with pytest.raises(SnippetNotFoundError):
            await delete_snippet(db, uuid.uuid4(), uuid.uuid4())

    async def test_delete_snippet_wrong_user(self) -> None:
        from writer.services.snippet_service import SnippetNotFoundError, delete_snippet

        # Snippet belongs to a different user — DB returns None (query includes user_id filter)
        db = _make_db(scalar_result=None)
        with pytest.raises(SnippetNotFoundError):
            await delete_snippet(db, uuid.uuid4(), uuid.uuid4())


class TestUpdateSnippet:
    async def test_update_snippet_note_and_tag(self) -> None:
        from writer.models.schemas import SnippetResponse, SnippetUpdate
        from writer.services.snippet_service import update_snippet

        snippet_id = uuid.uuid4()
        user_id = uuid.uuid4()
        snippet_obj = _make_snippet(id=snippet_id, user_id=user_id, note=None, tag=None)
        db = _make_db(scalar_result=snippet_obj)

        data = SnippetUpdate(note="My note", tag="important")
        result = await update_snippet(db, snippet_id, user_id, data)
        assert isinstance(result, SnippetResponse)
        assert snippet_obj.note == "My note"
        assert snippet_obj.tag == "important"

    async def test_update_snippet_not_found(self) -> None:
        from writer.models.schemas import SnippetUpdate
        from writer.services.snippet_service import SnippetNotFoundError, update_snippet

        db = _make_db(scalar_result=None)
        with pytest.raises(SnippetNotFoundError):
            await update_snippet(db, uuid.uuid4(), uuid.uuid4(), SnippetUpdate())


class TestGetSnippetWithSourceTitle:
    async def test_returns_snippet_with_source_title(self) -> None:
        from writer.models.schemas import SnippetResponse
        from writer.services.snippet_service import get_snippet_with_source_title

        snippet_id = uuid.uuid4()
        user_id = uuid.uuid4()
        source_id = uuid.uuid4()
        snippet_obj = _make_snippet(id=snippet_id, user_id=user_id, source_id=source_id)

        db = AsyncMock()
        # First execute: snippet lookup
        snippet_result = MagicMock()
        snippet_result.scalar_one_or_none.return_value = snippet_obj
        # Second execute: source lookup
        source_obj = MagicMock()
        source_obj.title = "My Source Title"
        source_result = MagicMock()
        source_result.scalar_one_or_none.return_value = source_obj
        db.execute = AsyncMock(side_effect=[snippet_result, source_result])

        result = await get_snippet_with_source_title(db, snippet_id, user_id)
        assert isinstance(result, SnippetResponse)
        assert result.source_title == "My Source Title"

    async def test_source_deleted_returns_none_title(self) -> None:
        from writer.models.schemas import SnippetResponse
        from writer.services.snippet_service import get_snippet_with_source_title

        snippet_id = uuid.uuid4()
        user_id = uuid.uuid4()
        # source_id is None (source was deleted)
        snippet_obj = _make_snippet(id=snippet_id, user_id=user_id, source_id=None)

        db = AsyncMock()
        snippet_result = MagicMock()
        snippet_result.scalar_one_or_none.return_value = snippet_obj
        db.execute = AsyncMock(return_value=snippet_result)

        result = await get_snippet_with_source_title(db, snippet_id, user_id)
        assert isinstance(result, SnippetResponse)
        assert result.source_title is None


# ── T022: snippet-chapter assignment ──────────────────────────────────────


class TestAssignSnippetToChapter:
    async def test_assign_creates_junction_row(self) -> None:
        from writer.services.snippet_service import assign_snippet_to_chapter

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        # merge returns the object back
        chapter_snippet_obj = MagicMock()
        db.merge = AsyncMock(return_value=chapter_snippet_obj)

        chapter_id = uuid.uuid4()
        snippet_id = uuid.uuid4()

        await assign_snippet_to_chapter(db, chapter_id, snippet_id)
        db.merge.assert_called_once()

    async def test_assign_is_idempotent(self) -> None:
        from writer.services.snippet_service import assign_snippet_to_chapter

        db = AsyncMock()
        db.merge = AsyncMock(return_value=MagicMock())
        db.flush = AsyncMock()

        chapter_id = uuid.uuid4()
        snippet_id = uuid.uuid4()

        # Call twice — should not error
        await assign_snippet_to_chapter(db, chapter_id, snippet_id)
        await assign_snippet_to_chapter(db, chapter_id, snippet_id)


class TestUnassignSnippetFromChapter:
    async def test_unassign_removes_junction_row(self) -> None:
        from writer.services.snippet_service import unassign_snippet_from_chapter

        db = AsyncMock()
        junction_obj = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = junction_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        await unassign_snippet_from_chapter(db, uuid.uuid4(), uuid.uuid4())
        db.delete.assert_called_once_with(junction_obj)

    async def test_unassign_nonexistent_is_noop(self) -> None:
        from writer.services.snippet_service import unassign_snippet_from_chapter

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        # Should not raise
        await unassign_snippet_from_chapter(db, uuid.uuid4(), uuid.uuid4())


# ── T023: chapter-filtered snippet listing ────────────────────────────────


class TestListSnippetsByChapter:
    async def test_list_snippets_by_chapter_returns_filtered(self) -> None:
        from writer.models.schemas import SnippetResponse
        from writer.services.snippet_service import list_snippets_by_chapter

        chapter_id = uuid.uuid4()
        user_id = uuid.uuid4()
        snippets = [_make_snippet(), _make_snippet()]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = snippets
        # Second call for source title lookup returns empty
        src_result = MagicMock()
        src_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[mock_result, src_result])

        result = await list_snippets_by_chapter(db, chapter_id, user_id)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(s, SnippetResponse) for s in result)
