"""Semantic search service — dual-group search over sources + snippets with scope resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Chapter, ChapterSnippet, ChapterSource, Snippet, Source
from writer.models.schemas import (
    FilterScope,
    FilterScopeAll,
    FilterScopeChapter,
    FilterScopeDocLevel,
    SearchV2Response,
    SnippetGroupPayload,
    SnippetResult,
    SourceGroupPayload,
    SourceResult,
)
from writer.services.vector_store import (
    MAX_DISTANCE,
    query_document_corpus,
)

logger = get_logger(__name__)

# Cap on chunk over-fetch to keep grouping work bounded.
_OVERFETCH_MULTIPLIER = 3
_OVERFETCH_CAP = 60


@dataclass(slots=True)
class InScopeIds:
    """IDs allowed for a given search scope, plus a fallback marker."""

    source_ids: set[uuid.UUID] = field(default_factory=set)
    snippet_ids: set[uuid.UUID] = field(default_factory=set)
    # True iff a chapter scope silently degraded to `all` (FR-021).
    degraded_to_all: bool = False


def _score_from_distance(distance: float) -> float:
    """Normalise a Chroma squared-L2 distance to a descending "score" suitable for display."""
    return max(0.0, 1.0 - distance)


async def _all_source_ids_for_document(
    session: AsyncSession, document_id: uuid.UUID
) -> set[uuid.UUID]:
    res = await session.execute(select(Source.id).where(Source.document_id == document_id))
    return set(res.scalars().all())


async def _all_snippet_ids_for_document(
    session: AsyncSession, document_id: uuid.UUID
) -> set[uuid.UUID]:
    res = await session.execute(select(Snippet.id).where(Snippet.document_id == document_id))
    return set(res.scalars().all())


async def _doc_level_source_ids(session: AsyncSession, document_id: uuid.UUID) -> set[uuid.UUID]:
    res = await session.execute(
        select(Source.id)
        .outerjoin(ChapterSource, Source.id == ChapterSource.source_id)
        .where(Source.document_id == document_id, ChapterSource.source_id.is_(None))
    )
    return set(res.scalars().all())


async def _doc_level_snippet_ids(session: AsyncSession, document_id: uuid.UUID) -> set[uuid.UUID]:
    res = await session.execute(
        select(Snippet.id)
        .outerjoin(ChapterSnippet, Snippet.id == ChapterSnippet.snippet_id)
        .where(Snippet.document_id == document_id, ChapterSnippet.snippet_id.is_(None))
    )
    return set(res.scalars().all())


async def _chapter_or_untagged_source_ids(
    session: AsyncSession, document_id: uuid.UUID, chapter_id: uuid.UUID
) -> set[uuid.UUID]:
    res = await session.execute(
        select(Source.id)
        .outerjoin(ChapterSource, Source.id == ChapterSource.source_id)
        .where(
            Source.document_id == document_id,
            (ChapterSource.chapter_id == chapter_id) | (ChapterSource.source_id.is_(None)),
        )
    )
    return set(res.scalars().all())


async def _chapter_or_untagged_snippet_ids(
    session: AsyncSession, document_id: uuid.UUID, chapter_id: uuid.UUID
) -> set[uuid.UUID]:
    res = await session.execute(
        select(Snippet.id)
        .outerjoin(ChapterSnippet, Snippet.id == ChapterSnippet.snippet_id)
        .where(
            Snippet.document_id == document_id,
            (ChapterSnippet.chapter_id == chapter_id) | (ChapterSnippet.snippet_id.is_(None)),
        )
    )
    return set(res.scalars().all())


async def resolve_in_scope_ids(
    session: AsyncSession,
    doc_id: uuid.UUID,
    scope: FilterScope,
) -> InScopeIds:
    """Return source + snippet id sets that fall within the given scope.

    Chapter scopes follow FR-012: items tagged to the chapter OR with zero chapter tags.
    Stale/unknown chapters silently degrade to `all` and flag the returned struct.
    """
    if isinstance(scope, FilterScopeAll):
        src_ids = await _all_source_ids_for_document(session, doc_id)
        snip_ids = await _all_snippet_ids_for_document(session, doc_id)
        return InScopeIds(source_ids=src_ids, snippet_ids=snip_ids)

    if isinstance(scope, FilterScopeDocLevel):
        src_ids = await _doc_level_source_ids(session, doc_id)
        snip_ids = await _doc_level_snippet_ids(session, doc_id)
        return InScopeIds(source_ids=src_ids, snippet_ids=snip_ids)

    assert isinstance(scope, FilterScopeChapter)
    chap_result = await session.execute(
        select(Chapter).where(Chapter.id == scope.chapter_id, Chapter.document_id == doc_id)
    )
    if chap_result.scalar_one_or_none() is None:
        logger.warning(
            "resolve_in_scope_ids: stale chapter %s in doc %s — degrading to all",
            scope.chapter_id,
            doc_id,
        )
        src_ids = await _all_source_ids_for_document(session, doc_id)
        snip_ids = await _all_snippet_ids_for_document(session, doc_id)
        return InScopeIds(source_ids=src_ids, snippet_ids=snip_ids, degraded_to_all=True)

    src_ids = await _chapter_or_untagged_source_ids(session, doc_id, scope.chapter_id)
    snip_ids = await _chapter_or_untagged_snippet_ids(session, doc_id, scope.chapter_id)
    return InScopeIds(source_ids=src_ids, snippet_ids=snip_ids)


async def search_document_dual(
    query: str,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    session: AsyncSession,
    scope: FilterScope,
    top_k: int = 10,
) -> SearchV2Response:
    """Run one corpus query and bucket results into source + snippet groups.

    Source chunks are grouped by source_id keeping the highest-scoring chunk per source.
    Each result is tagged with `in_scope` relative to the resolved scope; counts of
    out-of-scope matches are computed BEFORE the `top_k` cap for spillover accuracy.
    """
    logger.info(
        "search_document_dual q=%r user=%s doc=%s scope=%r top_k=%d",
        query,
        user_id,
        doc_id,
        scope,
        top_k,
    )

    resolved = await resolve_in_scope_ids(session, doc_id, scope)
    effective_scope: FilterScope = FilterScopeAll() if resolved.degraded_to_all else scope

    fetch_k = min(top_k * _OVERFETCH_MULTIPLIER, _OVERFETCH_CAP)
    corpus = query_document_corpus(
        query_text=query,
        user_id=user_id,
        doc_id=doc_id,
        top_k=fetch_k,
        max_distance=MAX_DISTANCE,
    )

    # Bucket + group source chunks by source_id (keep best chunk per source).
    best_source_chunks: dict[uuid.UUID, tuple[str, float]] = {}
    snippet_hits: list[tuple[uuid.UUID, str, uuid.UUID | None, float]] = []

    for text, meta, distance in corpus:
        entity_type = str(meta.get("entity_type", "source"))
        if entity_type == "source":
            raw_src = meta.get("source_id")
            try:
                src_uuid = uuid.UUID(str(raw_src))
            except (TypeError, ValueError):
                logger.warning("search_document_dual: bad source_id %r in meta", raw_src)
                continue
            existing = best_source_chunks.get(src_uuid)
            if existing is None or distance < _distance_of(existing):
                best_source_chunks[src_uuid] = (text, distance)
        elif entity_type == "snippet":
            raw_snip = meta.get("snippet_id")
            try:
                snip_uuid = uuid.UUID(str(raw_snip))
            except (TypeError, ValueError):
                logger.warning("search_document_dual: bad snippet_id %r in meta", raw_snip)
                continue
            raw_src = meta.get("source_id")
            if raw_src in (None, "none", ""):
                snip_source_id: uuid.UUID | None = None
            else:
                try:
                    snip_source_id = uuid.UUID(str(raw_src))
                except (TypeError, ValueError):
                    snip_source_id = None
            snippet_hits.append((snip_uuid, text, snip_source_id, distance))

    # Batch lookup: source titles for every source referenced by either group.
    source_ids_to_title: set[uuid.UUID] = set(best_source_chunks.keys())
    for _, _, src_id, _ in snippet_hits:
        if src_id is not None:
            source_ids_to_title.add(src_id)
    title_map: dict[uuid.UUID, str] = {}
    if source_ids_to_title:
        src_rows = await session.execute(select(Source).where(Source.id.in_(source_ids_to_title)))
        for src in src_rows.scalars().all():
            title_map[src.id] = src.title

    # Batch lookup: chapter associations for every snippet hit.
    snippet_chapter_map: dict[uuid.UUID, list[uuid.UUID]] = {}
    snippet_ids_seen = [hit[0] for hit in snippet_hits]
    if snippet_ids_seen:
        ch_rows = await session.execute(
            select(ChapterSnippet).where(ChapterSnippet.snippet_id.in_(snippet_ids_seen))
        )
        for row in ch_rows.scalars().all():
            snippet_chapter_map.setdefault(row.snippet_id, []).append(row.chapter_id)

    # Build SourceResult list (sorted by score desc).
    source_results: list[SourceResult] = []
    for src_uuid, (excerpt, distance) in best_source_chunks.items():
        title = title_map.get(src_uuid)
        if title is None:
            logger.warning(
                "search_document_dual: source %s has no title row — dropping result", src_uuid
            )
            continue
        source_results.append(
            SourceResult(
                source_id=src_uuid,
                title=title,
                excerpt=excerpt,
                score=_score_from_distance(distance),
                in_scope=src_uuid in resolved.source_ids,
            )
        )
    source_results.sort(key=lambda r: r.score, reverse=True)

    # Build SnippetResult list (one per snippet hit; sorted by score desc).
    snippet_results: list[SnippetResult] = []
    for snip_uuid, text, src_id, distance in snippet_hits:
        snippet_results.append(
            SnippetResult(
                snippet_id=snip_uuid,
                text=text,
                source_id=src_id,
                source_title=title_map.get(src_id) if src_id is not None else None,
                chapter_ids=snippet_chapter_map.get(snip_uuid, []),
                score=_score_from_distance(distance),
                in_scope=snip_uuid in resolved.snippet_ids,
            )
        )
    snippet_results.sort(key=lambda r: r.score, reverse=True)

    # Out-of-scope counts are computed from the pre-cap list (FR-015/SC-004).
    source_out_of_scope = sum(1 for r in source_results if not r.in_scope)
    snippet_out_of_scope = sum(1 for r in snippet_results if not r.in_scope)

    # Cap each group's in_scope list to top_k (out-of-scope members are dropped from the
    # payload; the spillover count conveys their presence).
    source_in_scope = [r for r in source_results if r.in_scope][:top_k]
    snippet_in_scope = [r for r in snippet_results if r.in_scope][:top_k]

    response = SearchV2Response(
        query=query,
        scope=effective_scope,
        sources=SourceGroupPayload(
            in_scope=source_in_scope, out_of_scope_count=source_out_of_scope
        ),
        snippets=SnippetGroupPayload(
            in_scope=snippet_in_scope, out_of_scope_count=snippet_out_of_scope
        ),
    )
    logger.info(
        "search_document_dual: sources in=%d oos=%d snippets in=%d oos=%d",
        len(source_in_scope),
        source_out_of_scope,
        len(snippet_in_scope),
        snippet_out_of_scope,
    )
    return response


def _distance_of(entry: tuple[str, float]) -> float:
    return entry[1]
