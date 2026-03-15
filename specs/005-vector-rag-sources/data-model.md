# Data Model: Vector RAG for Document Sources

**Branch**: `005-vector-rag-sources` | **Date**: 2026-03-15

---

## Relational Changes (PostgreSQL)

### `sources` table — new columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `indexing_status` | `VARCHAR(20)` / enum | NOT NULL | `'pending'` | Values: `pending`, `processing`, `completed`, `failed` |
| `error_message` | `TEXT` | NULL | — | Set only when `indexing_status = 'failed'` |

**Requires**: Alembic migration (`006_add_source_indexing_fields.py` or next available revision).

### SQLAlchemy ORM (`models/db.py`)

```python
class IndexingStatus(enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class Source(Base):
    # ... existing fields ...
    indexing_status: Mapped[IndexingStatus] = mapped_column(
        Enum(IndexingStatus), nullable=False, default=IndexingStatus.pending
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Pydantic Schemas (`models/schemas.py`)

```python
class SourceResponse(BaseModel):
    # ... existing fields ...
    indexing_status: IndexingStatus
    error_message: str | None
```

---

## Vector Store (ChromaDB)

### Collection: `"sources"`

Single collection for all source chunks across all documents.

### Document schema (per chunk)

| Field | Type | Value |
|-------|------|-------|
| `id` | `str` | `"{source_id}_{chunk_index}"` e.g. `"abc123_0"` |
| `document` | `str` | Chunk text content |
| `metadata.source_id` | `str` | UUID of the parent `sources` row (stringified) |

### Example

```python
collection.add(
    ids=["abc123_0", "abc123_1", "abc123_2"],
    documents=["chunk text 0", "chunk text 1", "chunk text 2"],
    metadatas=[
        {"source_id": "abc123"},
        {"source_id": "abc123"},
        {"source_id": "abc123"},
    ],
)
```

---

## State Transitions

```
[upload] → pending
           ↓ (background task starts)
        processing
           ↓ (success)        ↓ (exception)
        completed            failed
                              (error_message set)
```

---

## Configuration (`core/config.py`)

```python
class Settings(BaseSettings):
    # ... existing ...
    chroma_path: str = "./data/chroma"
```

---

## New Module: `services/vector_store.py`

```python
# Public interface (signatures only)

def get_collection() -> chromadb.Collection: ...

def index_source(source_id: uuid.UUID, chunks: list[str]) -> None: ...
    # Adds all chunks with source_id metadata

def query_sources(query_text: str, top_k: int = 5) -> list[str]: ...
    # Returns list of chunk text strings

def delete_source_chunks(source_id: uuid.UUID) -> None: ...
    # Deletes all chunks where metadata.source_id == str(source_id)
```

All three public functions wrap ChromaDB synchronous client calls in `asyncio.to_thread()` when called from async contexts. The module also exposes synchronous variants for use in tests and the background task worker.
