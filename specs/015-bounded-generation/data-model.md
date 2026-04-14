# Data Model: Bounded Generation & Curation Workflow

**Feature**: 015-bounded-generation
**Phase**: Phase 1 — Design
**Date**: 2026-04-13

---

## New Table: `snippets`

One new PostgreSQL table. One Alembic migration required.

```sql
CREATE TABLE snippets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_id   UUID REFERENCES sources(id) ON DELETE SET NULL,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    char_offset INTEGER NOT NULL DEFAULT 0,   -- start offset in source.content
    note        TEXT,                          -- user-editable note (nullable)
    tag         TEXT,                          -- user-editable tag label (nullable)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX snippets_document_user_idx ON snippets (document_id, user_id);
```

### ORM Model (SQLAlchemy 2.x)

Location: `src/writer/models/db.py`

```python
class Snippet(Base):
    __tablename__ = "snippets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

---

## Modified: `source_service._extract_pdf_text`

**Location**: `src/writer/services/source_service.py`

The private function `_extract_pdf_text(file_bytes: bytes) -> str` is replaced:

```python
# Before (pypdf):
def _extract_pdf_text(file_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(file_bytes))
    ...

# After (pymupdf4llm):
def _extract_pdf_markdown(file_bytes: bytes) -> str:
    import fitz  # pymupdf
    import pymupdf4llm
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    md = pymupdf4llm.to_markdown(doc)
    if not md.strip():
        raise PdfParseError("PDF contains no extractable text (may be image-only)")
    return md
```

Downstream callers (`add_source_pdf`) pass this markdown to `Source.content` unchanged. The indexer pipeline remains unchanged — `chunk_sentences` operates on the markdown string.

---

## Modified: `documentlm_core` vector store

**Location**: `documentlm_core/src/documentlm_core/services/vector_store.py`

New TypedDict and function added (existing functions unchanged):

```python
from typing import TypedDict

class ChunkResult(TypedDict):
    text: str
    source_id: str    # UUID as string
    document_id: str  # UUID as string

def query_sources_with_metadata(
    query_text: str,
    user_id: uuid.UUID,
    doc_id: uuid.UUID,
    is_private_doc: bool = False,
    top_k: int = 10,
) -> list[ChunkResult]:
    """Return top_k relevant chunks with source metadata."""
    ...
```

Re-exported from `writer/services/vector_store.py`.

---

## Pydantic Schemas (new/modified)

**Location**: `src/writer/models/schemas.py`

```python
class SnippetCreate(BaseModel):
    source_id: uuid.UUID | None = None
    text: str
    char_offset: int = 0
    note: str | None = None
    tag: str | None = None

class SnippetUpdate(BaseModel):
    note: str | None = None
    tag: str | None = None

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
    # source_title is joined and populated by the service layer (not from ORM directly)
    source_title: str | None = None

class SearchResultItem(BaseModel):
    text: str
    source_id: uuid.UUID
    source_title: str     # resolved by service from DB

class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    query: str

class BoundedGenerateRequest(BaseModel):
    snippet_ids: list[uuid.UUID]    # optional — may be empty
    intent: Annotated[str, Field(min_length=1, max_length=500)]
    cursor_context: str = ""        # heading/paragraph at insertion point; used to identify
                                    # the current chapter. Full document fetched server-side.

class BoundedGenerationResponse(BaseModel):
    suggested_text: str
```

---

## Entity Relationship Summary

```
users ──────────┬── documents ──── snippets ──── sources
                │                       │
                └── sources ────────────┘
                          (source_id FK, nullable — SET NULL on delete)
```

- `Snippet.source_id` is nullable (SET NULL): if a source is deleted, saved snippets retain their text but `source_id = NULL` (FR: "source unavailable" notice).
- `Snippet.document_id` cascades delete: removing a document removes all its snippets.
- `Snippet.user_id` cascades delete: removing a user removes all their snippets.

---

## Migration Plan

Single Alembic migration: `add_snippets_table.py`

- `op.create_table('snippets', ...)` with all columns and FKs
- `op.create_index('snippets_document_user_idx', 'snippets', ['document_id', 'user_id'])`
- No changes to existing tables

No schema changes to `sources` or `documents`. The `Source.content` field format changes from plain-text to markdown for new PDFs, but the column type remains `TEXT` — no migration needed.
