# Implementation Plan: Vector RAG for Document Sources

**Branch**: `005-vector-rag-sources` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-vector-rag-sources/spec.md`

## Summary

Replace full-document text injection in agent context builders with a vector RAG pipeline. When a source is uploaded, its text is chunked (via `nlp_utils.chunk_sentences`) and indexed into a local ChromaDB collection asynchronously. At agent invocation time, the top 5 semantically relevant chunks are retrieved and injected instead of the full document. Source deletion cascades to ChromaDB to prevent orphaned chunks.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, chromadb (new), nlp-utils (local)
**Storage**: PostgreSQL (Docker container) + ChromaDB (local persistent directory `./data/chroma`)
**Testing**: pytest — TDD for `vector_store.py` and updated `source_service.py`; integration tests use ephemeral ChromaDB instance
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL); ChromaDB runs in-process
**Project Type**: Web service (FastAPI + HTMX)
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save
**Scale/Scope**: Demo/prototype — YAGNI; ChromaDB runs in-process, no separate vector DB service

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Python + uv**: All new code is Python; `chromadb` added via `uv add chromadb`
- [x] **II. TDD scope**: Tests planned for `vector_store.py` and `source_service.py` (service layer only); no endpoint tests
- [x] **III. No remote APIs in tests**: ChromaDB uses a local ephemeral client in tests (`chromadb.EphemeralClient()`); no network calls
- [x] **IV. Simplicity**: Scope is exactly what the spec requests — no extra features
- [x] **V. Strong typing**: All new functions use typed signatures, Pydantic schemas updated for new fields; `IndexingStatus` enum; no plain dicts
- [x] **VI. Functional style**: New `vector_store.py` is a module of pure functions; no new classes
- [x] **VII. Ruff**: No exceptions to this rule
- [x] **VIII. Containers**: PostgreSQL + app server in Docker; `./data/chroma` is a volume mount
- [x] **IX. Logging**: `index_source`, `query_sources`, `delete_source_chunks` all emit log entries; background task logs errors on failure
- [x] **ADK architecture**: No new agent types introduced; existing agents have their context builders updated

## Project Structure

### Documentation (this feature)

```text
specs/005-vector-rag-sources/
├── plan.md              # This file
├── research.md          # Resolved decisions (ChromaDB, chunker, background tasks)
├── data-model.md        # Source model changes + ChromaDB collection schema
├── quickstart.md        # Setup and verification guide
├── contracts/
│   └── api-sources.md   # Changed endpoint contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (changes for this feature)

```text
src/writer/
├── models/
│   ├── db.py                    # MODIFY: add IndexingStatus enum + fields to Source
│   └── schemas.py               # MODIFY: add indexing_status, error_message to SourceResponse
├── core/
│   └── config.py                # MODIFY: add chroma_path setting
├── services/
│   ├── vector_store.py          # NEW: index_source, query_sources, delete_source_chunks
│   ├── source_service.py        # MODIFY: trigger indexing after add; cascade delete to vector store
│   └── agent_service.py         # MODIFY: replace full-text injection with vector retrieval
├── api/
│   └── sources.py               # MODIFY: wire BackgroundTasks for indexing trigger
└── (no new templates needed)

migrations/versions/
└── <rev>_add_source_indexing_fields.py   # NEW: add indexing_status + error_message columns

tests/
├── unit/
│   └── test_vector_store.py     # NEW: unit tests for chunking + embedding pipeline
└── integration/
    └── test_rag_pipeline.py     # NEW: integration tests (ephemeral ChromaDB)

data/
└── chroma/                      # Runtime: ChromaDB persistence (gitignored)
```

**Structure Decision**: Single-project layout (existing). All changes are additive to existing modules except the new `vector_store.py` service.

## Implementation Phases

### Phase 1: Model + Migration

1. Add `IndexingStatus` enum to `models/enums.py`
2. Add `indexing_status` and `error_message` to `Source` ORM model (`models/db.py`)
3. Add fields to `SourceResponse` Pydantic schema (`models/schemas.py`)
4. Generate Alembic migration for the two new columns
5. Add `chroma_path: str = "./data/chroma"` to `Settings` (`core/config.py`)

### Phase 2: Vector Store Service

1. Create `services/vector_store.py`:
   - `get_collection() -> chromadb.Collection` — lazy-initialized singleton using `settings.chroma_path`
   - `index_source(source_id: uuid.UUID, chunks: list[str]) -> None`
   - `query_sources(query_text: str, top_k: int = 5) -> list[str]`
   - `delete_source_chunks(source_id: uuid.UUID) -> None`
2. All ChromaDB calls wrapped in `asyncio.to_thread()` at the call site in async contexts
3. Unit tests: `tests/unit/test_vector_store.py` — mock the ChromaDB collection; verify chunk IDs, metadata format, and query routing

### Phase 3: Indexing Pipeline

1. Create `services/indexer.py` (or inline in `source_service.py`):
   - `async def run_indexing(source_id: uuid.UUID, db: AsyncSession) -> None`
   - Sets status → `processing`, calls `chunk_sentences`, calls `index_source`, sets status → `completed`
   - On exception: sets status → `failed`, writes `error_message`, logs at ERROR level
2. Modify `api/sources.py`:
   - Inject `BackgroundTasks` into the upload endpoints
   - After `add_source()` / `add_source_pdf()`, enqueue `run_indexing` as a background task

### Phase 4: Deletion Cascade

1. Modify `source_service.py` → `delete_source()`:
   - Before deleting the relational record, call `delete_source_chunks(source_id)`
   - Log the deletion

### Phase 5: Agent Context — Replace Full-Text Injection

1. Modify `services/agent_service.py`:
   - `invoke_drafter`: replace `source_index` dict (full text) with `query_sources(comment.body + comment.selected_text)` call; inject the returned chunks as a block
   - `invoke_planner`: replace full `research_sources` concatenation with `query_sources(overview)` call
2. Modify `services/chat_service.py`:
   - `invoke_chat_agent`: replace inline `md_content` full-document injection with `query_sources(last_user_message)` for source context (document content injection for the chat agent itself is separate — keep as-is since that's the current document being edited, not sources)

### Phase 6: Tests

1. `tests/unit/test_vector_store.py` — all vector_store functions with mocked collection
2. `tests/integration/test_rag_pipeline.py` — ephemeral `chromadb.EphemeralClient()`:
   - Index a source → query → assert relevant chunks returned
   - Index a source → delete → query → assert no chunks returned
