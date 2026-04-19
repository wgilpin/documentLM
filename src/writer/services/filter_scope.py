"""Filter scope parsing for source/snippet list endpoints."""

import uuid

from writer.core.logging import get_logger
from writer.models.schemas import (
    FilterScope,
    FilterScopeAll,
    FilterScopeChapter,
    FilterScopeDocLevel,
)

logger = get_logger(__name__)


class FilterScopeParseError(ValueError):
    """Raised when a scope string does not match any known form."""


def parse_filter_scope(raw: str) -> FilterScope:
    """Parse `all` / `doc-level` / `chapter:<uuid>` into a FilterScope."""
    if raw == "all":
        return FilterScopeAll()
    if raw == "doc-level":
        return FilterScopeDocLevel()
    if raw.startswith("chapter:"):
        suffix = raw[len("chapter:") :]
        if not suffix:
            logger.error("Empty chapter UUID in scope=%r", raw)
            raise FilterScopeParseError(f"Chapter scope requires a UUID: {raw!r}")
        try:
            chapter_id = uuid.UUID(suffix)
        except ValueError as exc:
            logger.error("Invalid chapter UUID in scope=%r: %s", raw, exc)
            raise FilterScopeParseError(f"Invalid chapter UUID in scope: {raw!r}") from exc
        return FilterScopeChapter(chapter_id=chapter_id)
    logger.error("Unrecognised scope value %r", raw)
    raise FilterScopeParseError(f"Unrecognised scope: {raw!r}")
