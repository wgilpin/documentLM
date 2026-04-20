"""One-shot backfill: embed every existing snippet and stamp entity_type on legacy source chunks.

Idempotent: safe to re-run. Uses deterministic vector IDs (snip_<snippet_uuid>) so upsert
replaces rather than duplicates.

Usage:
    uv run python scripts/backfill_snippet_embeddings.py

Exits 0 on success, 1 if any snippet failed to embed.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from dataclasses import dataclass

from documentlm_core.core.config import settings as core_settings
from documentlm_core.core.logging import get_logger
from documentlm_core.services import vector_store
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from writer.models.db import Document, Snippet

logger = get_logger(__name__)


@dataclass(slots=True)
class BackfillCounts:
    scanned: int = 0
    embedded: int = 0
    skipped: int = 0
    failed: int = 0


async def _collect_snippet_tuples(
    db: AsyncSession,
) -> list[tuple[uuid.UUID, uuid.UUID, uuid.UUID | None, uuid.UUID, str, bool]]:
    """Return (snippet_id, document_id, source_id, user_id, text, is_private) for every snippet."""
    result = await db.execute(
        select(
            Snippet.id,
            Snippet.document_id,
            Snippet.source_id,
            Snippet.user_id,
            Snippet.text,
            Document.is_private,
        ).join(Document, Document.id == Snippet.document_id)
    )
    return [(row[0], row[1], row[2], row[3], row[4], bool(row[5])) for row in result.all()]


def _stamp_legacy_source_chunks(user_id: uuid.UUID) -> int:
    """Add entity_type=source to any existing chunks in the user's collection that lack it.

    Returns the number of chunks stamped.
    """
    collection = vector_store.get_collection(user_id)
    try:
        raw = collection.get(include=["metadatas"])
    except Exception as exc:  # noqa: BLE001
        logger.error("backfill: collection.get failed for user=%s: %s", user_id, exc)
        return 0
    ids: list[str] = list(raw.get("ids") or [])
    metas: list[dict[str, object]] = list(raw.get("metadatas") or [])  # type: ignore[arg-type]
    to_update_ids: list[str] = []
    to_update_metas: list[dict[str, object]] = []
    for chroma_id, meta in zip(ids, metas, strict=False):
        if not isinstance(meta, dict):
            continue
        if "entity_type" in meta:
            continue
        # Only stamp rows that look like source chunks (snippet chunks always carry entity_type).
        to_update_ids.append(chroma_id)
        to_update_metas.append({**meta, "entity_type": "source"})
    if to_update_ids:
        collection.update(ids=to_update_ids, metadatas=to_update_metas)  # type: ignore[arg-type]
        logger.info(
            "backfill: stamped entity_type=source on %d legacy chunks for user=%s",
            len(to_update_ids),
            user_id,
        )
    return len(to_update_ids)


async def run_backfill() -> BackfillCounts:
    counts = BackfillCounts()
    engine = create_async_engine(core_settings.database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    seen_users: set[uuid.UUID] = set()
    try:
        async with session_factory() as db:
            tuples = await _collect_snippet_tuples(db)
            counts.scanned = len(tuples)
            logger.info("backfill: scanning %d snippets", counts.scanned)
            for snippet_id, document_id, source_id, user_id, text, is_private in tuples:
                if user_id not in seen_users:
                    _stamp_legacy_source_chunks(user_id)
                    seen_users.add(user_id)
                try:
                    collection = vector_store.get_collection(user_id)
                    existing = collection.get(ids=[f"snip_{snippet_id}"])
                    already = bool(existing.get("ids"))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "backfill: existence check failed for snippet=%s user=%s: %s",
                        snippet_id,
                        user_id,
                        exc,
                    )
                    already = False
                try:
                    vector_store.index_snippet(
                        snippet_id=snippet_id,
                        document_id=document_id,
                        text=text,
                        user_id=user_id,
                        source_id=source_id,
                        is_private=is_private,
                    )
                    if already:
                        counts.skipped += 1
                    else:
                        counts.embedded += 1
                except Exception as exc:  # noqa: BLE001
                    counts.failed += 1
                    logger.error(
                        "backfill: failed to embed snippet=%s user=%s: %s",
                        snippet_id,
                        user_id,
                        exc,
                    )
    finally:
        await engine.dispose()
    return counts


def main() -> int:
    counts = asyncio.run(run_backfill())
    logger.info(
        "backfill_snippet_embeddings: scanned=%d embedded=%d skipped=%d failed=%d",
        counts.scanned,
        counts.embedded,
        counts.skipped,
        counts.failed,
    )
    print(
        f"backfill_snippet_embeddings: scanned={counts.scanned} "
        f"embedded={counts.embedded} skipped={counts.skipped} failed={counts.failed}"
    )
    return 1 if counts.failed else 0


if __name__ == "__main__":
    sys.exit(main())
