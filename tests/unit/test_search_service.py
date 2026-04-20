"""Unit tests for search_service — TDD."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch


def _corpus_row(
    text: str,
    *,
    entity_type: str,
    source_id: str | None = None,
    snippet_id: str | None = None,
    document_id: str | None = None,
    is_private: bool = True,
    distance: float = 0.4,
) -> tuple[str, dict[str, object], float]:
    meta: dict[str, object] = {
        "entity_type": entity_type,
        "document_id": document_id or str(uuid.uuid4()),
        "is_private": is_private,
    }
    if entity_type == "source":
        meta["source_id"] = source_id or str(uuid.uuid4())
    else:
        meta["snippet_id"] = snippet_id or str(uuid.uuid4())
        meta["source_id"] = source_id or "none"
    return (text, meta, distance)


class TestSearchDocumentDualStructure:
    async def test_returns_two_groups_sorted_by_score(self) -> None:
        from writer.models.schemas import (
            FilterScopeAll,
            SearchV2Response,
        )
        from writer.services.search_service import search_document_dual

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_a = uuid.uuid4()
        source_b = uuid.uuid4()
        snippet_a = uuid.uuid4()
        snippet_b = uuid.uuid4()

        corpus = [
            # source chunk, decent match
            _corpus_row(
                "aardvark source A",
                entity_type="source",
                source_id=str(source_a),
                document_id=str(doc_id),
                distance=0.3,
            ),
            # source chunk, worse match
            _corpus_row(
                "aardvark source B",
                entity_type="source",
                source_id=str(source_b),
                document_id=str(doc_id),
                distance=0.7,
            ),
            # snippet, decent match
            _corpus_row(
                "aardvark snippet A",
                entity_type="snippet",
                snippet_id=str(snippet_a),
                source_id="none",
                document_id=str(doc_id),
                distance=0.2,
            ),
            # snippet, worse match
            _corpus_row(
                "aardvark snippet B",
                entity_type="snippet",
                snippet_id=str(snippet_b),
                source_id="none",
                document_id=str(doc_id),
                distance=0.8,
            ),
        ]

        source_a_obj = MagicMock(id=source_a, title="Source A title")
        source_b_obj = MagicMock(id=source_b, title="Source B title")

        source_lookup = MagicMock()
        source_lookup.scalars.return_value.all.return_value = [source_a_obj, source_b_obj]
        # chapter associations: none
        chapter_lookup = MagicMock()
        chapter_lookup.all.return_value = []
        chapter_lookup.scalars.return_value.all.return_value = []
        # in-scope id resolvers: return every id when scope=all
        in_scope_sources = MagicMock()
        in_scope_sources.scalars.return_value.all.return_value = [source_a, source_b]
        in_scope_snippets = MagicMock()
        in_scope_snippets.scalars.return_value.all.return_value = [snippet_a, snippet_b]

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                in_scope_sources,
                in_scope_snippets,
                source_lookup,
                chapter_lookup,
            ]
        )

        with patch("writer.services.search_service.query_document_corpus", return_value=corpus):
            response = await search_document_dual(
                query="aardvark",
                user_id=user_id,
                doc_id=doc_id,
                session=db,
                scope=FilterScopeAll(),
                top_k=10,
            )

        assert isinstance(response, SearchV2Response)
        # Both groups populated.
        assert len(response.sources.in_scope) == 2
        assert len(response.snippets.in_scope) == 2
        # Sorted by score desc (best first).
        assert response.sources.in_scope[0].score >= response.sources.in_scope[1].score
        assert response.snippets.in_scope[0].score >= response.snippets.in_scope[1].score

    async def test_source_group_dedupes_by_source_id(self) -> None:
        """When multiple chunks belong to the same source, keep only the top-scoring one."""
        from writer.models.schemas import FilterScopeAll
        from writer.services.search_service import search_document_dual

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        source_a = uuid.uuid4()

        corpus = [
            _corpus_row(
                "chunk 1 of A (best)",
                entity_type="source",
                source_id=str(source_a),
                document_id=str(doc_id),
                distance=0.2,
            ),
            _corpus_row(
                "chunk 2 of A",
                entity_type="source",
                source_id=str(source_a),
                document_id=str(doc_id),
                distance=0.5,
            ),
            _corpus_row(
                "chunk 3 of A",
                entity_type="source",
                source_id=str(source_a),
                document_id=str(doc_id),
                distance=0.7,
            ),
        ]

        source_a_obj = MagicMock(id=source_a, title="Source A")
        source_lookup = MagicMock()
        source_lookup.scalars.return_value.all.return_value = [source_a_obj]
        chapter_lookup = MagicMock()
        chapter_lookup.scalars.return_value.all.return_value = []
        in_scope_sources = MagicMock()
        in_scope_sources.scalars.return_value.all.return_value = [source_a]
        in_scope_snippets = MagicMock()
        in_scope_snippets.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[in_scope_sources, in_scope_snippets, source_lookup, chapter_lookup]
        )

        with patch("writer.services.search_service.query_document_corpus", return_value=corpus):
            response = await search_document_dual(
                query="q",
                user_id=user_id,
                doc_id=doc_id,
                session=db,
                scope=FilterScopeAll(),
                top_k=10,
            )

        assert len(response.sources.in_scope) == 1
        assert response.sources.in_scope[0].excerpt == "chunk 1 of A (best)"
        assert response.sources.in_scope[0].source_id == source_a

    async def test_empty_groups_still_present(self) -> None:
        """Missing a group in the corpus must still yield an empty in_scope list."""
        from writer.models.schemas import FilterScopeAll
        from writer.services.search_service import search_document_dual

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        # Only snippets in the corpus.
        snippet_a = uuid.uuid4()
        corpus = [
            _corpus_row(
                "lone snippet",
                entity_type="snippet",
                snippet_id=str(snippet_a),
                source_id="none",
                document_id=str(doc_id),
                distance=0.3,
            ),
        ]

        source_lookup = MagicMock()
        source_lookup.scalars.return_value.all.return_value = []
        chapter_lookup = MagicMock()
        chapter_lookup.scalars.return_value.all.return_value = []
        in_scope_sources = MagicMock()
        in_scope_sources.scalars.return_value.all.return_value = []
        in_scope_snippets = MagicMock()
        in_scope_snippets.scalars.return_value.all.return_value = [snippet_a]

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[in_scope_sources, in_scope_snippets, source_lookup, chapter_lookup]
        )

        with patch("writer.services.search_service.query_document_corpus", return_value=corpus):
            response = await search_document_dual(
                query="q",
                user_id=user_id,
                doc_id=doc_id,
                session=db,
                scope=FilterScopeAll(),
                top_k=10,
            )

        assert response.sources.in_scope == []
        assert response.snippets.in_scope != []


class TestResolveInScopeIds:
    async def test_scope_all_returns_all_ids(self) -> None:
        from writer.models.schemas import FilterScopeAll
        from writer.services.search_service import resolve_in_scope_ids

        doc_id = uuid.uuid4()
        src1 = uuid.uuid4()
        src2 = uuid.uuid4()
        snip1 = uuid.uuid4()

        src_result = MagicMock()
        src_result.scalars.return_value.all.return_value = [src1, src2]
        snip_result = MagicMock()
        snip_result.scalars.return_value.all.return_value = [snip1]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[src_result, snip_result])

        ids = await resolve_in_scope_ids(db, doc_id, FilterScopeAll())
        assert ids.source_ids == {src1, src2}
        assert ids.snippet_ids == {snip1}

    async def test_scope_doc_level_returns_untagged_only(self) -> None:
        from writer.models.schemas import FilterScopeDocLevel
        from writer.services.search_service import resolve_in_scope_ids

        doc_id = uuid.uuid4()
        untagged_src = uuid.uuid4()
        untagged_snip = uuid.uuid4()

        src_result = MagicMock()
        src_result.scalars.return_value.all.return_value = [untagged_src]
        snip_result = MagicMock()
        snip_result.scalars.return_value.all.return_value = [untagged_snip]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[src_result, snip_result])

        ids = await resolve_in_scope_ids(db, doc_id, FilterScopeDocLevel())
        assert ids.source_ids == {untagged_src}
        assert ids.snippet_ids == {untagged_snip}

    async def test_scope_chapter_returns_tagged_and_untagged_per_fr012(self) -> None:
        from writer.models.schemas import FilterScopeChapter
        from writer.services.search_service import resolve_in_scope_ids

        doc_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        tagged_src = uuid.uuid4()
        untagged_src = uuid.uuid4()
        tagged_snip = uuid.uuid4()

        # chapter lookup succeeds
        chap_result = MagicMock()
        chap_result.scalar_one_or_none.return_value = MagicMock(id=chapter_id)
        src_result = MagicMock()
        src_result.scalars.return_value.all.return_value = [tagged_src, untagged_src]
        snip_result = MagicMock()
        snip_result.scalars.return_value.all.return_value = [tagged_snip]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[chap_result, src_result, snip_result])

        ids = await resolve_in_scope_ids(db, doc_id, FilterScopeChapter(chapter_id=chapter_id))
        assert tagged_src in ids.source_ids
        assert untagged_src in ids.source_ids
        assert tagged_snip in ids.snippet_ids

    async def test_stale_chapter_degrades_to_all(self) -> None:
        from writer.models.schemas import FilterScopeChapter
        from writer.services.search_service import resolve_in_scope_ids

        doc_id = uuid.uuid4()
        stale_chapter_id = uuid.uuid4()
        src1 = uuid.uuid4()

        # chapter lookup returns None → fallback
        chap_result = MagicMock()
        chap_result.scalar_one_or_none.return_value = None
        src_result = MagicMock()
        src_result.scalars.return_value.all.return_value = [src1]
        snip_result = MagicMock()
        snip_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[chap_result, src_result, snip_result])

        ids = await resolve_in_scope_ids(
            db, doc_id, FilterScopeChapter(chapter_id=stale_chapter_id)
        )
        assert ids.degraded_to_all is True
        assert src1 in ids.source_ids


class TestSpilloverCounts:
    async def test_chapter_scope_counts_out_of_scope_matches(self) -> None:
        """With a chapter scope, out_of_scope_count equals matches whose id is not in-scope."""
        from writer.models.schemas import FilterScopeChapter
        from writer.services.search_service import search_document_dual

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chapter_id = uuid.uuid4()

        in_src = uuid.uuid4()
        out_src = uuid.uuid4()
        in_snip = uuid.uuid4()
        out_snip = uuid.uuid4()

        corpus = [
            _corpus_row(
                "in-scope src text",
                entity_type="source",
                source_id=str(in_src),
                document_id=str(doc_id),
                distance=0.2,
            ),
            _corpus_row(
                "out-of-scope src text",
                entity_type="source",
                source_id=str(out_src),
                document_id=str(doc_id),
                distance=0.3,
            ),
            _corpus_row(
                "in-scope snip text",
                entity_type="snippet",
                snippet_id=str(in_snip),
                source_id="none",
                document_id=str(doc_id),
                distance=0.2,
            ),
            _corpus_row(
                "out-of-scope snip text",
                entity_type="snippet",
                snippet_id=str(out_snip),
                source_id="none",
                document_id=str(doc_id),
                distance=0.3,
            ),
        ]

        # Chapter exists.
        chap_exists = MagicMock()
        chap_exists.scalar_one_or_none.return_value = MagicMock(id=chapter_id)
        in_scope_srcs = MagicMock()
        in_scope_srcs.scalars.return_value.all.return_value = [in_src]
        in_scope_snips = MagicMock()
        in_scope_snips.scalars.return_value.all.return_value = [in_snip]

        in_src_obj = MagicMock(id=in_src, title="InSrc")
        out_src_obj = MagicMock(id=out_src, title="OutSrc")
        source_lookup = MagicMock()
        source_lookup.scalars.return_value.all.return_value = [in_src_obj, out_src_obj]
        chapter_lookup = MagicMock()
        chapter_lookup.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                chap_exists,
                in_scope_srcs,
                in_scope_snips,
                source_lookup,
                chapter_lookup,
            ]
        )

        with patch("writer.services.search_service.query_document_corpus", return_value=corpus):
            response = await search_document_dual(
                query="q",
                user_id=user_id,
                doc_id=doc_id,
                session=db,
                scope=FilterScopeChapter(chapter_id=chapter_id),
                top_k=10,
            )

        assert response.sources.out_of_scope_count == 1
        assert response.snippets.out_of_scope_count == 1
        assert len(response.sources.in_scope) == 1
        assert len(response.snippets.in_scope) == 1

    async def test_all_scope_has_zero_out_of_scope(self) -> None:
        from writer.models.schemas import FilterScopeAll
        from writer.services.search_service import search_document_dual

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        src1 = uuid.uuid4()
        corpus = [
            _corpus_row(
                "only source",
                entity_type="source",
                source_id=str(src1),
                document_id=str(doc_id),
                distance=0.2,
            ),
        ]
        src_obj = MagicMock(id=src1, title="S")
        source_lookup = MagicMock()
        source_lookup.scalars.return_value.all.return_value = [src_obj]
        chapter_lookup = MagicMock()
        chapter_lookup.scalars.return_value.all.return_value = []
        in_scope_srcs = MagicMock()
        in_scope_srcs.scalars.return_value.all.return_value = [src1]
        in_scope_snips = MagicMock()
        in_scope_snips.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[in_scope_srcs, in_scope_snips, source_lookup, chapter_lookup]
        )

        with patch("writer.services.search_service.query_document_corpus", return_value=corpus):
            response = await search_document_dual(
                query="q",
                user_id=user_id,
                doc_id=doc_id,
                session=db,
                scope=FilterScopeAll(),
                top_k=10,
            )

        assert response.sources.out_of_scope_count == 0
        assert response.snippets.out_of_scope_count == 0

    async def test_stale_chapter_scope_response_reflects_degraded(self) -> None:
        """FR-021: when the requested chapter is stale, the echoed scope is 'all'."""
        from writer.models.schemas import FilterScopeAll, FilterScopeChapter
        from writer.services.search_service import search_document_dual

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        stale_chapter_id = uuid.uuid4()
        src1 = uuid.uuid4()

        corpus = [
            _corpus_row(
                "any",
                entity_type="source",
                source_id=str(src1),
                document_id=str(doc_id),
                distance=0.2,
            ),
        ]
        # Chapter lookup returns None.
        chap_stale = MagicMock()
        chap_stale.scalar_one_or_none.return_value = None
        in_scope_srcs = MagicMock()
        in_scope_srcs.scalars.return_value.all.return_value = [src1]
        in_scope_snips = MagicMock()
        in_scope_snips.scalars.return_value.all.return_value = []
        src_obj = MagicMock(id=src1, title="S")
        source_lookup = MagicMock()
        source_lookup.scalars.return_value.all.return_value = [src_obj]
        chapter_lookup = MagicMock()
        chapter_lookup.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                chap_stale,
                in_scope_srcs,
                in_scope_snips,
                source_lookup,
                chapter_lookup,
            ]
        )

        with patch("writer.services.search_service.query_document_corpus", return_value=corpus):
            response = await search_document_dual(
                query="q",
                user_id=user_id,
                doc_id=doc_id,
                session=db,
                scope=FilterScopeChapter(chapter_id=stale_chapter_id),
                top_k=10,
            )

        assert isinstance(response.scope, FilterScopeAll)

    async def test_untagged_snippet_included_in_chapter_scope(self) -> None:
        """FR-012: document-level items remain in-scope of any chapter query."""
        from writer.models.schemas import FilterScopeChapter
        from writer.services.search_service import search_document_dual

        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        untagged_snip = uuid.uuid4()

        corpus = [
            _corpus_row(
                "doc-level snippet match",
                entity_type="snippet",
                snippet_id=str(untagged_snip),
                source_id="none",
                document_id=str(doc_id),
                distance=0.2,
            ),
        ]
        # Chapter exists.
        chap_exists = MagicMock()
        chap_exists.scalar_one_or_none.return_value = MagicMock(id=chapter_id)
        in_scope_srcs = MagicMock()
        in_scope_srcs.scalars.return_value.all.return_value = []
        in_scope_snips = MagicMock()
        in_scope_snips.scalars.return_value.all.return_value = [untagged_snip]
        source_lookup = MagicMock()
        source_lookup.scalars.return_value.all.return_value = []
        chapter_lookup = MagicMock()
        chapter_lookup.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                chap_exists,
                in_scope_srcs,
                in_scope_snips,
                source_lookup,
                chapter_lookup,
            ]
        )

        with patch("writer.services.search_service.query_document_corpus", return_value=corpus):
            response = await search_document_dual(
                query="q",
                user_id=user_id,
                doc_id=doc_id,
                session=db,
                scope=FilterScopeChapter(chapter_id=chapter_id),
                top_k=10,
            )

        assert len(response.snippets.in_scope) == 1
        assert response.snippets.in_scope[0].snippet_id == untagged_snip
