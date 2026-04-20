# Data Model: Chapter-Scoped Sources and Snippets

## Overview

One new join table (`chapter_sources`) and a few new Pydantic schemas. The existing `chapter_snippets` table from spec-016 is reused without modification.

## Tables

### `chapter_sources` (NEW)

Many-to-many junction between `chapters` and `sources`.

| Column      | Type | Constraints                                                                  |
|-------------|------|------------------------------------------------------------------------------|
| chapter_id  | UUID | PK part 1, FK → `chapters.id` ON DELETE CASCADE                              |
| source_id   | UUID | PK part 2, FK → `sources.id` ON DELETE CASCADE                               |

**Indexes**:

- Composite PK `(chapter_id, source_id)` covers chapter→source lookups.
- Secondary index `chapter_sources_source_idx` on `(source_id)` for the reverse direction (used when computing `chapter_ids` for a `SourceResponse`).

**Cascade behaviour**:

- Deleting a chapter removes its association rows. Sources referenced only by that chapter become document-level.
- Deleting a source removes its association rows.

**Cross-document integrity**: Enforced at the service layer (`assign_source_to_chapter` checks that the source's `document_id` equals the chapter's `document_id`). FK constraints alone cannot enforce this without an explicit `document_id` denormalisation, which we don't carry.

### `chapter_snippets` (UNCHANGED — exists from spec-016)

Reproduced for reference. No DDL changes in this feature.

| Column     | Type | Constraints                                                                   |
|------------|------|-------------------------------------------------------------------------------|
| chapter_id | UUID | PK part 1, FK → `chapters.id` ON DELETE CASCADE                               |
| snippet_id | UUID | PK part 2, FK → `snippets.id` ON DELETE CASCADE                               |

Existing index `chapter_snippets_snippet_idx` on `(snippet_id)`.

## SQLAlchemy ORM additions (`writer/models/db.py`)

```python
class ChapterSource(Base):
    __tablename__ = "chapter_sources"
    __table_args__ = (Index("chapter_sources_source_idx", "source_id"),)

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
```

Add `"ChapterSource"` to the `__all__` list in `db.py`.

## Pydantic schema additions (`writer/models/schemas.py`)

### Extended request schemas

```python
class SourceCreate(BaseModel):
    document_id: uuid.UUID
    source_type: SourceType
    title: str
    content: str = ""
    url: str | None = None
    chapter_ids: list[uuid.UUID] = []  # NEW — empty == document-level


class SnippetCreate(BaseModel):
    source_id: uuid.UUID | None = None
    text: str
    char_offset: int = 0
    note: str | None = None
    tag: str | None = None
    chapter_ids: list[uuid.UUID] = []  # NEW — empty == document-level


class ChapterAssociationUpdate(BaseModel):
    """Replace-set semantics for retroactive tag editing."""
    chapter_ids: list[uuid.UUID]
```

### Extended response schemas

```python
class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    source_type: SourceType
    title: str
    content: str
    url: str | None
    indexing_status: IndexingStatus
    error_message: str | None
    file_path: str | None = None
    created_at: datetime
    chapter_ids: list[uuid.UUID] = []  # NEW — populated by service layer


class SnippetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    source_id: uuid.UUID | None
    text: str
    char_offset: int
    note: str | None
    tag: str | None
    created_at: datetime
    source_title: str | None = None
    chapter_ids: list[uuid.UUID] = []  # NEW — populated by service layer
```

### Filter scope discriminator

Filter scope is parsed in the API layer from a string query parameter (`scope=all|doc-level|chapter:<uuid>`) into a tagged Pydantic model used internally:

```python
class FilterScopeAll(BaseModel):
    kind: Literal["all"] = "all"

class FilterScopeDocLevel(BaseModel):
    kind: Literal["doc-level"] = "doc-level"

class FilterScopeChapter(BaseModel):
    kind: Literal["chapter"] = "chapter"
    chapter_id: uuid.UUID

FilterScope = Annotated[
    FilterScopeAll | FilterScopeDocLevel | FilterScopeChapter,
    Field(discriminator="kind"),
]
```

This keeps the strong-typing rule (no plain dicts, no `Any`) and gives mypy full coverage at the service boundary.

## Validation rules

| Rule | Layer | Enforced by |
|------|-------|-------------|
| `chapter_ids` are valid UUIDs | API | Pydantic on `SourceCreate` / `SnippetCreate` / `ChapterAssociationUpdate` |
| Each chapter_id belongs to the same document as the item | Service | Single SELECT validating `chapter.document_id == item.document_id`; raise `ChapterDocumentMismatchError` otherwise |
| Duplicate `(chapter_id, item_id)` rows are not created | Service | `db.merge()` (idempotent) or pre-INSERT existence check; PK constraint is the backstop |
| Stale chapter UUID in `scope=chapter:<uuid>` filter | Service | Detect "no such chapter for this document"; treat as `scope=all` and log a warning |

## State transitions

Both `chapter_sources` and `chapter_snippets` are stateless join rows — they exist or they don't. There are no status fields, no transitions.

The "document-level" classification is a derived state: an item is document-level *iff* it has zero rows in its join table. No persisted flag is needed.

## Migration

New Alembic migration: `<timestamp>_add_chapter_sources.py`.

```python
def upgrade() -> None:
    op.create_table(
        "chapter_sources",
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chapter_id", "source_id"),
    )
    op.create_index("chapter_sources_source_idx", "chapter_sources", ["source_id"])

def downgrade() -> None:
    op.drop_index("chapter_sources_source_idx", table_name="chapter_sources")
    op.drop_table("chapter_sources")
```

Pure additive change. Safe on any populated database (FR-025).

## Service-layer surface (additions)

### `writer/services/source_service.py`

```python
async def assign_source_to_chapter(db, chapter_id, source_id) -> None
async def unassign_source_from_chapter(db, chapter_id, source_id) -> None
async def replace_source_chapter_associations(db, source_id, chapter_ids, *, document_id, user_id) -> None
async def list_sources_by_scope(db, document_id, user_id, scope: FilterScope) -> list[SourceResponse]
# Extend list_sources to populate chapter_ids on each response.
# Extend add_source to accept chapter_ids and call replace_source_chapter_associations.
```

### `writer/services/snippet_service.py`

```python
async def replace_snippet_chapter_associations(db, snippet_id, chapter_ids, *, document_id, user_id) -> None
async def list_snippets_by_scope(db, document_id, user_id, scope: FilterScope) -> list[SnippetResponse]
# Extend create_snippet to accept chapter_ids and call replace_snippet_chapter_associations.
# Extend list_snippets / list_snippets_by_chapter to populate chapter_ids on each response.
# Existing assign_snippet_to_chapter / unassign_snippet_from_chapter remain unchanged.
```

### Errors

```python
class ChapterDocumentMismatchError(Exception):
    """Raised when an attempted association crosses documents."""
    def __init__(self, chapter_id, item_id):
        super().__init__(f"chapter {chapter_id} does not belong to the same document as item {item_id}")
```

Logged at ERROR level by every except-block per Constitution IX.
