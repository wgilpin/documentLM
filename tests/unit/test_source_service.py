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
        "file_path": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestExtractPdfMarkdown:
    def test_valid_pdf_bytes_returns_markdown(self) -> None:
        """Valid PDF bytes → returns non-empty markdown string containing text."""
        from writer.services.source_service import _extract_pdf_markdown

        fake_doc = MagicMock()
        fake_doc.__enter__ = MagicMock(return_value=fake_doc)
        fake_doc.__exit__ = MagicMock(return_value=False)

        with (
            patch("fitz.open", return_value=fake_doc),
            patch("pymupdf4llm.to_markdown", return_value="# Heading\n\nSome text content"),
        ):
            result = _extract_pdf_markdown(b"%PDF-fake")

        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_image_only_pdf_raises_pdf_parse_error(self) -> None:
        """Image-only / empty PDF bytes → raises PdfParseError."""
        from writer.services.source_service import PdfParseError, _extract_pdf_markdown

        fake_doc = MagicMock()

        with (
            patch("fitz.open", return_value=fake_doc),
            patch("pymupdf4llm.to_markdown", return_value="   "),
            pytest.raises(PdfParseError),
        ):
            _extract_pdf_markdown(b"%PDF-image-only")


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

    async def test_add_url_fetches_content_when_empty(self) -> None:
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
            content="",
            url="https://example.com",
        )

        with (
            patch("writer.services.source_service.Source") as MockSource,
            patch("writer.services.source_service.select"),
            patch(
                "writer.services.content_fetcher.fetch_url_content",
                new_callable=AsyncMock,
                return_value="Fetched article text",
            ),
            patch(
                "documentlm_core.services.content_cleaner.clean_content",
                new_callable=AsyncMock,
                return_value="Fetched article text",
            ),
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
                "writer.services.source_service._extract_pdf_markdown",
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
            patch("writer.services.source_service._extract_pdf_markdown", return_value="extracted"),
            patch("writer.services.source_service.Source") as MockSource,
            patch(
                "documentlm_core.services.content_cleaner.clean_content",
                new_callable=AsyncMock,
                return_value="extracted",
            ),
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


# ─── Chapter-source association tests (spec 017, US1) ────────────────────────


def _exec_returning_scalar(value: object) -> MagicMock:
    """Build a db.execute return value whose scalar_one_or_none() yields `value`."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _exec_returning_scalars_all(values: list[object]) -> MagicMock:
    res = MagicMock()
    res.scalars.return_value.all.return_value = values
    return res


class TestAssignSourceToChapter:
    async def test_assign_source_to_chapter_idempotent(self) -> None:
        """Calling assign twice with the same pair does not raise."""
        from writer.services.source_service import assign_source_to_chapter

        doc_id = uuid.uuid4()
        chapter = MagicMock(id=uuid.uuid4(), document_id=doc_id)
        source = MagicMock(id=uuid.uuid4(), document_id=doc_id)

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalar(chapter),
                _exec_returning_scalar(source),
                _exec_returning_scalar(chapter),
                _exec_returning_scalar(source),
            ]
        )
        db.merge = AsyncMock()
        db.flush = AsyncMock()

        await assign_source_to_chapter(db, chapter.id, source.id)
        await assign_source_to_chapter(db, chapter.id, source.id)
        assert db.merge.await_count == 2

    async def test_assign_source_to_chapter_cross_doc_raises(self) -> None:
        """Assigning a source to a chapter in a different document raises."""
        from writer.services.source_service import (
            ChapterDocumentMismatchError,
            assign_source_to_chapter,
        )

        chapter = MagicMock(id=uuid.uuid4(), document_id=uuid.uuid4())
        source = MagicMock(id=uuid.uuid4(), document_id=uuid.uuid4())

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalar(chapter),
                _exec_returning_scalar(source),
            ]
        )
        db.merge = AsyncMock()

        with pytest.raises(ChapterDocumentMismatchError):
            await assign_source_to_chapter(db, chapter.id, source.id)

        db.merge.assert_not_awaited()


class TestUnassignSourceFromChapter:
    async def test_unassign_noop_when_absent(self) -> None:
        """Calling unassign when no association exists is a silent no-op."""
        from writer.services.source_service import unassign_source_from_chapter

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_exec_returning_scalar(None))
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        await unassign_source_from_chapter(db, uuid.uuid4(), uuid.uuid4())
        db.delete.assert_not_awaited()

    async def test_unassign_deletes_existing_association(self) -> None:
        from writer.services.source_service import unassign_source_from_chapter

        junction = MagicMock()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_exec_returning_scalar(junction))
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        await unassign_source_from_chapter(db, uuid.uuid4(), uuid.uuid4())
        db.delete.assert_awaited_once_with(junction)


class TestReplaceSourceChapterAssociations:
    async def test_replace_replaces_full_set(self) -> None:
        """Given an existing set {A}, target {B,C} → A removed, B+C merged."""
        from writer.services.source_service import replace_source_chapter_associations

        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()
        chapter_b = uuid.uuid4()
        chapter_c = uuid.uuid4()

        # chapters in document (validation query) → chapter_b, chapter_c
        chapters_in_doc = [
            MagicMock(id=chapter_b, document_id=doc_id),
            MagicMock(id=chapter_c, document_id=doc_id),
        ]
        # current associations → existing A row
        existing_rows = [MagicMock(chapter_id=uuid.uuid4(), source_id=source_id)]

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalars_all(chapters_in_doc),
                _exec_returning_scalars_all(existing_rows),
            ]
        )
        db.merge = AsyncMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        await replace_source_chapter_associations(
            db,
            source_id,
            [chapter_b, chapter_c],
            document_id=doc_id,
            user_id=user_id,
        )

        # old association removed
        db.delete.assert_any_await(existing_rows[0])
        # two new associations merged
        assert db.merge.await_count == 2

    async def test_replace_idempotent_on_same_set(self) -> None:
        """Re-applying the current set → no deletes, no merges (beyond idempotent merge)."""
        from writer.services.source_service import replace_source_chapter_associations

        doc_id = uuid.uuid4()
        source_id = uuid.uuid4()
        chapter_a = uuid.uuid4()
        chapters_in_doc = [MagicMock(id=chapter_a, document_id=doc_id)]
        existing_rows = [MagicMock(chapter_id=chapter_a, source_id=source_id)]

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalars_all(chapters_in_doc),
                _exec_returning_scalars_all(existing_rows),
            ]
        )
        db.merge = AsyncMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        await replace_source_chapter_associations(
            db,
            source_id,
            [chapter_a],
            document_id=doc_id,
            user_id=uuid.uuid4(),
        )

        db.delete.assert_not_awaited()

    async def test_replace_validates_cross_doc(self) -> None:
        """Given a chapter UUID not in document → raises mismatch."""
        from writer.services.source_service import (
            ChapterDocumentMismatchError,
            replace_source_chapter_associations,
        )

        doc_id = uuid.uuid4()
        foreign_chapter = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_exec_returning_scalars_all([]))
        db.merge = AsyncMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        with pytest.raises(ChapterDocumentMismatchError):
            await replace_source_chapter_associations(
                db,
                uuid.uuid4(),
                [foreign_chapter],
                document_id=doc_id,
                user_id=uuid.uuid4(),
            )


class TestListSourcesByScope:
    async def test_scope_all_returns_same_as_list_sources(self) -> None:
        from writer.models.schemas import FilterScopeAll
        from writer.services.source_service import list_sources_by_scope

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        sources = [_make_source(document_id=doc_id), _make_source(document_id=doc_id)]

        db = AsyncMock()
        # execute called twice: once for sources, once for chapter_ids batch
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalars_all(sources),
                _exec_returning_scalars_all([]),  # no associations
            ]
        )

        result = await list_sources_by_scope(db, doc_id, user_id, FilterScopeAll())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(s, SourceResponse) for s in result)
        assert all(s.chapter_ids == [] for s in result)

    async def test_scope_doc_level_returns_only_unassociated(self) -> None:
        from writer.models.schemas import FilterScopeDocLevel
        from writer.services.source_service import list_sources_by_scope

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        untagged = _make_source(document_id=doc_id)

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalars_all([untagged]),
                _exec_returning_scalars_all([]),
            ]
        )

        result = await list_sources_by_scope(db, doc_id, user_id, FilterScopeDocLevel())
        assert len(result) == 1
        assert result[0].id == untagged.id

    async def test_scope_chapter_returns_tagged_sources(self) -> None:
        from writer.models.schemas import FilterScopeChapter
        from writer.services.source_service import list_sources_by_scope

        doc_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        user_id = uuid.uuid4()
        tagged = _make_source(document_id=doc_id)

        db = AsyncMock()
        # chapter-exists check, then sources, then chapter_ids batch
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalar(MagicMock(id=chapter_id, document_id=doc_id)),
                _exec_returning_scalars_all([tagged]),
                _exec_returning_scalars_all(
                    [MagicMock(source_id=tagged.id, chapter_id=chapter_id)]
                ),
            ]
        )

        scope = FilterScopeChapter(chapter_id=chapter_id)
        result = await list_sources_by_scope(db, doc_id, user_id, scope)
        assert len(result) == 1
        assert result[0].id == tagged.id
        assert chapter_id in result[0].chapter_ids

    async def test_scope_chapter_stale_uuid_degrades_to_all(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from writer.models.schemas import FilterScopeChapter
        from writer.services.source_service import list_sources_by_scope

        doc_id = uuid.uuid4()
        stale_chapter = uuid.uuid4()
        user_id = uuid.uuid4()
        sources = [_make_source(document_id=doc_id)]

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalar(None),  # chapter not found → degrade
                _exec_returning_scalars_all(sources),
                _exec_returning_scalars_all([]),
            ]
        )

        with caplog.at_level(logging.WARNING):
            result = await list_sources_by_scope(
                db, doc_id, user_id, FilterScopeChapter(chapter_id=stale_chapter)
            )

        assert len(result) == 1
        assert any(
            "stale" in rec.message.lower() or "unknown" in rec.message.lower()
            for rec in caplog.records
        )


class TestAddSourceWithChapterIds:
    async def test_add_source_with_chapter_ids_creates_associations(self) -> None:
        """add_source with non-empty chapter_ids calls replace_source_chapter_associations."""
        from writer.services.source_service import add_source

        doc_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        user_id = uuid.uuid4()
        instance = _make_source(document_id=doc_id, source_type=SourceType.note)

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        data = SourceCreate(
            document_id=doc_id,
            source_type=SourceType.note,
            title="Tagged note",
            content="body",
            chapter_ids=[chapter_id],
        )

        with (
            patch("writer.services.source_service.Source") as MockSource,
            patch(
                "writer.services.source_service.replace_source_chapter_associations",
                new_callable=AsyncMock,
            ) as mock_replace,
        ):
            MockSource.return_value = instance
            result = await add_source(db, data, user_id)

        mock_replace.assert_awaited_once()
        call_kwargs = mock_replace.await_args.kwargs
        assert call_kwargs["document_id"] == doc_id
        assert call_kwargs["user_id"] == user_id
        assert mock_replace.await_args.args[2] == [chapter_id]
        assert isinstance(result, SourceResponse)

    async def test_add_source_empty_chapter_ids_skips_replace(self) -> None:
        """add_source with empty chapter_ids does not call replace_source_chapter_associations."""
        from writer.services.source_service import add_source

        doc_id = uuid.uuid4()
        user_id = uuid.uuid4()
        instance = _make_source(document_id=doc_id, source_type=SourceType.note)

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        data = SourceCreate(
            document_id=doc_id,
            source_type=SourceType.note,
            title="Doc-level note",
            content="body",
        )

        with (
            patch("writer.services.source_service.Source") as MockSource,
            patch(
                "writer.services.source_service.replace_source_chapter_associations",
                new_callable=AsyncMock,
            ) as mock_replace,
        ):
            MockSource.return_value = instance
            await add_source(db, data, user_id)

        mock_replace.assert_not_awaited()


class TestListSourcesChapterIds:
    async def test_list_sources_populates_chapter_ids(self) -> None:
        from writer.services.source_service import list_sources

        doc_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        source = _make_source(document_id=doc_id)
        source.id = uuid.uuid4()

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_returning_scalars_all([source]),
                _exec_returning_scalars_all(
                    [MagicMock(source_id=source.id, chapter_id=chapter_id)]
                ),
            ]
        )

        result = await list_sources(db, doc_id, uuid.uuid4())
        assert len(result) == 1
        assert result[0].chapter_ids == [chapter_id]
