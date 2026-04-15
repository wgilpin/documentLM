"""Unit tests for chapter_service — TDD (write first, confirm fail, then implement)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from writer.models.schemas import ChapterResponse


def _make_chapter(**kwargs: object) -> MagicMock:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "title": "Test Chapter",
        "brief": None,
        "brief_visible": True,
        "content": "Some content",
        "position": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_document(**kwargs: object) -> MagicMock:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "title": "Test Doc",
        "content": "Hello world",
        "overview": None,
        "is_private": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ── T005: create, get_by_id, list_by_document ─────────────────────────────


class TestCreateChapter:
    async def test_create_assigns_next_position(self) -> None:
        from writer.services.chapter_service import create_chapter

        db = AsyncMock()
        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # First execute: max position query returns None (no chapters)
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = None
        # After creation: refresh
        chapter_obj = _make_chapter(document_id=doc_id, user_id=user_id, position=0)

        db.execute = AsyncMock(return_value=max_result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        from writer.models.schemas import ChapterCreate

        rebuild = "writer.services.chapter_service.rebuild_document_content"
        with (
            patch("writer.services.chapter_service.Chapter", return_value=chapter_obj),
            patch(rebuild, new_callable=AsyncMock),
        ):
            result = await create_chapter(db, doc_id, user_id, ChapterCreate(title="My Chapter"))

        assert isinstance(result, ChapterResponse)
        assert result.position == 0

    async def test_create_with_existing_chapters_gets_next_position(self) -> None:
        from writer.services.chapter_service import create_chapter

        db = AsyncMock()
        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # max position returns 2 (3 existing chapters at 0,1,2)
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = 2
        chapter_obj = _make_chapter(document_id=doc_id, user_id=user_id, position=3)

        db.execute = AsyncMock(return_value=max_result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        from writer.models.schemas import ChapterCreate

        rebuild = "writer.services.chapter_service.rebuild_document_content"
        with (
            patch("writer.services.chapter_service.Chapter", return_value=chapter_obj),
            patch(rebuild, new_callable=AsyncMock),
        ):
            result = await create_chapter(db, doc_id, user_id, ChapterCreate(title="Chapter 4"))

        assert isinstance(result, ChapterResponse)
        assert result.position == 3


class TestGetChapter:
    async def test_get_returns_chapter_response(self) -> None:
        from writer.services.chapter_service import get_chapter

        db = AsyncMock()
        chapter_id = uuid.uuid4()
        chapter_obj = _make_chapter(id=chapter_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter_obj
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_chapter(db, chapter_id)
        assert isinstance(result, ChapterResponse)
        assert result.id == chapter_id

    async def test_get_raises_on_not_found(self) -> None:
        from writer.services.chapter_service import ChapterNotFoundError, get_chapter

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChapterNotFoundError):
            await get_chapter(db, uuid.uuid4())


class TestListChapters:
    async def test_list_returns_ordered_by_position(self) -> None:
        from writer.services.chapter_service import list_chapters

        db = AsyncMock()
        doc_id = uuid.uuid4()
        chapters = [
            _make_chapter(position=0),
            _make_chapter(position=1),
            _make_chapter(position=2),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chapters
        db.execute = AsyncMock(return_value=mock_result)

        result = await list_chapters(db, doc_id)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(r, ChapterResponse) for r in result)

    async def test_list_empty_document_returns_empty(self) -> None:
        from writer.services.chapter_service import list_chapters

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        result = await list_chapters(db, uuid.uuid4())
        assert result == []


# ── T006: update and delete ───────────────────────────────────────────────


class TestUpdateChapter:
    async def test_update_persists_title_change(self) -> None:
        from writer.services.chapter_service import update_chapter

        db = AsyncMock()
        chapter_id = uuid.uuid4()
        chapter_obj = _make_chapter(id=chapter_id, title="Old Title", content="body")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        from writer.models.schemas import ChapterUpdate

        rebuild = "writer.services.chapter_service.rebuild_document_content"
        with patch(rebuild, new_callable=AsyncMock):
            result = await update_chapter(db, chapter_id, ChapterUpdate(title="New Title"))

        assert isinstance(result, ChapterResponse)
        assert chapter_obj.title == "New Title"

    async def test_update_persists_content_change(self) -> None:
        from writer.services.chapter_service import update_chapter

        db = AsyncMock()
        chapter_id = uuid.uuid4()
        chapter_obj = _make_chapter(id=chapter_id, content="old content")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        from writer.models.schemas import ChapterUpdate

        rebuild = "writer.services.chapter_service.rebuild_document_content"
        with patch(rebuild, new_callable=AsyncMock):
            result = await update_chapter(db, chapter_id, ChapterUpdate(content="new content"))

        assert isinstance(result, ChapterResponse)
        assert chapter_obj.content == "new content"

    async def test_update_raises_on_not_found(self) -> None:
        from writer.services.chapter_service import ChapterNotFoundError, update_chapter

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        from writer.models.schemas import ChapterUpdate

        with pytest.raises(ChapterNotFoundError):
            await update_chapter(db, uuid.uuid4(), ChapterUpdate(title="x"))


class TestDeleteChapter:
    async def test_delete_removes_chapter(self) -> None:
        from writer.services.chapter_service import delete_chapter

        db = AsyncMock()
        chapter_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chapter_obj = _make_chapter(id=chapter_id, document_id=doc_id, position=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        recompact = "writer.services.chapter_service._recompact_positions"
        rebuild = "writer.services.chapter_service.rebuild_document_content"
        with (
            patch(recompact, new_callable=AsyncMock),
            patch(rebuild, new_callable=AsyncMock),
        ):
            await delete_chapter(db, chapter_id)

        db.delete.assert_called_once_with(chapter_obj)

    async def test_delete_raises_on_not_found(self) -> None:
        from writer.services.chapter_service import ChapterNotFoundError, delete_chapter

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChapterNotFoundError):
            await delete_chapter(db, uuid.uuid4())


# ── T007: reorder and content cache rebuild ───────────────────────────────


class TestReorderChapter:
    async def test_reorder_adjusts_sibling_positions(self) -> None:
        from writer.services.chapter_service import reorder_chapter

        db = AsyncMock()
        chapter_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chapter_obj = _make_chapter(id=chapter_id, document_id=doc_id, position=0)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        reorder = "writer.services.chapter_service._reorder_positions"
        rebuild = "writer.services.chapter_service.rebuild_document_content"
        with (
            patch(reorder, new_callable=AsyncMock),
            patch(rebuild, new_callable=AsyncMock),
        ):
            result = await reorder_chapter(db, chapter_id, new_position=2)

        assert isinstance(result, list)


class TestRebuildDocumentContent:
    async def test_rebuild_concatenates_chapters_in_order(self) -> None:
        from writer.services.chapter_service import rebuild_document_content

        db = AsyncMock()
        doc_id = uuid.uuid4()

        chapters = [
            _make_chapter(title="Intro", content="Hello", position=0),
            _make_chapter(title="Body", content="World", position=1),
        ]

        doc_obj = _make_document(id=doc_id)

        # First execute: chapter list, second: document lookup
        chapter_result = MagicMock()
        chapter_result.scalars.return_value.all.return_value = chapters
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc_obj
        db.execute = AsyncMock(side_effect=[chapter_result, doc_result])
        db.flush = AsyncMock()

        await rebuild_document_content(db, doc_id)

        expected = "## Intro\n\nHello\n\n## Body\n\nWorld"
        assert doc_obj.content == expected

    async def test_rebuild_empty_chapters(self) -> None:
        from writer.services.chapter_service import rebuild_document_content

        db = AsyncMock()
        doc_id = uuid.uuid4()

        doc_obj = _make_document(id=doc_id)

        chapter_result = MagicMock()
        chapter_result.scalars.return_value.all.return_value = []
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc_obj
        db.execute = AsyncMock(side_effect=[chapter_result, doc_result])
        db.flush = AsyncMock()

        await rebuild_document_content(db, doc_id)

        assert doc_obj.content == ""


# ── T017 (US2): brief update and visibility toggle ───────────────────────


class TestBriefUpdate:
    async def test_update_chapter_with_brief(self) -> None:
        from writer.services.chapter_service import update_chapter

        db = AsyncMock()
        chapter_id = uuid.uuid4()
        chapter_obj = _make_chapter(id=chapter_id, brief=None)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        from writer.models.schemas import ChapterUpdate

        rebuild = "writer.services.chapter_service.rebuild_document_content"
        with patch(rebuild, new_callable=AsyncMock):
            result = await update_chapter(db, chapter_id, ChapterUpdate(brief="My planning note"))

        assert isinstance(result, ChapterResponse)
        assert chapter_obj.brief == "My planning note"


class TestBriefVisibilityToggle:
    async def test_toggle_brief_visibility(self) -> None:
        from writer.services.chapter_service import toggle_brief_visibility

        db = AsyncMock()
        chapter_id = uuid.uuid4()
        chapter_obj = _make_chapter(id=chapter_id, brief_visible=True)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter_obj
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        result = await toggle_brief_visibility(db, chapter_id, brief_visible=False)

        assert isinstance(result, ChapterResponse)
        assert chapter_obj.brief_visible is False


class TestRebuildExcludesBrief:
    async def test_rebuild_does_not_include_brief_text(self) -> None:
        from writer.services.chapter_service import rebuild_document_content

        db = AsyncMock()
        doc_id = uuid.uuid4()

        chapters = [
            _make_chapter(
                title="Intro",
                content="Chapter body",
                brief="This is a planning note",
                position=0,
            ),
        ]

        doc_obj = _make_document(id=doc_id)

        chapter_result = MagicMock()
        chapter_result.scalars.return_value.all.return_value = chapters
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc_obj
        db.execute = AsyncMock(side_effect=[chapter_result, doc_result])
        db.flush = AsyncMock()

        await rebuild_document_content(db, doc_id)

        assert "planning note" not in doc_obj.content
        assert "Chapter body" in doc_obj.content
