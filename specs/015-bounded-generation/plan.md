# Implementation Plan: Bounded Generation & Curation Workflow

**Branch**: `015-bounded-generation` | **Date**: 2026-04-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/015-bounded-generation/spec.md`

## Summary

Replaces the existing automatic-RAG text generation flow with a deliberate, evidence-first curation loop: **Search → Select → Synthesize**. Users curate evidence snippets from their sources before triggering AI generation. The LLM receives the user's selected snippets (optional), their intent string (required), and the full current document — so it stays coherent with what has already been written and avoids repetition.

Key changes: PDF extraction upgraded from pypdf to PyMuPDF4LLM (markdown output); new `snippets` DB table for curated evidence; a side panel with Document View + Snippet Bank; semantic search returning source metadata; a new bounded-generation API endpoint.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, ChromaDB, `pymupdf4llm` (new)
**Storage**: PostgreSQL (Docker) + ChromaDB (local persistent directory)
**Testing**: pytest — TDD for all service functions; no tests for API endpoints or frontend
**Type Checking**: mypy (strict), ruff
**Target Platform**: Docker containers
**Project Type**: web-service
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any; ruff passes before save; minimize JS
**Scale/Scope**: Demo/prototype — YAGNI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- [x] **I. Python + uv**: All new code is Python; `pymupdf4llm` added via `uv add`
- [x] **II. TDD scope**: Tests planned for `snippet_service`, `agent_service.invoke_bounded_drafter`, `search_service` only — not endpoints or frontend
- [x] **III. No remote APIs in tests**: `run_agent_text` and `vector_store.query_sources_with_metadata` mocked in all tests
- [x] **IV. Simplicity**: Feature scope confirmed; no extras beyond spec (no re-generation history, no snippet export, no multi-user sharing)
- [x] **V. Strong typing**: All new schemas are Pydantic models; `ChunkResult` is a `TypedDict`; no plain dicts; no Any
- [x] **VI. Functional style**: All new service code uses module-level functions; no new classes
- [x] **VII. Ruff**: ruff check + ruff format run before every save
- [x] **VIII. Containers**: PostgreSQL in Docker; no new containers required; ChromaDB persists to local directory (existing pattern)
- [x] **IX. Logging**: All service functions log start/success/failure; every except block logs at ERROR
- [x] **ADK architecture**: No new agent types; `invoke_bounded_drafter` reuses existing `drafter_agent` and `run_agent_text`

## Project Structure

### Documentation (this feature)

```text
specs/015-bounded-generation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/api.md     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/writer/
├── api/
│   ├── snippets.py         # NEW — Snippet CRUD endpoints
│   ├── search.py           # NEW — Semantic search endpoint
│   ├── generation.py       # NEW — Bounded generate endpoint
│   └── sources.py          # MODIFIED — add GET /{id}/view for Document View
├── services/
│   ├── snippet_service.py  # NEW — CRUD business logic
│   ├── search_service.py   # NEW — search result mapping
│   └── agent_service.py    # MODIFIED — add invoke_bounded_drafter
├── models/
│   ├── db.py               # MODIFIED — add Snippet ORM model
│   └── schemas.py          # MODIFIED — add Snippet/Search/Generation schemas
└── main.py                 # MODIFIED — register new routers

documentlm_core/
└── services/vector_store.py  # MODIFIED — add query_sources_with_metadata + ChunkResult

migrations/versions/
└── xxxx_add_snippets_table.py  # NEW

tests/unit/
└── test_snippet_service.py     # NEW
└── test_search_service.py      # NEW
└── test_bounded_generation.py  # NEW

static/
└── editor.js                   # MODIFIED — bundling UI + insertBoundedSuggestion()

templates/
├── partials/
│   ├── snippet_card.html        # NEW
│   ├── snippet_bank.html        # NEW
│   ├── search_results.html      # NEW
│   └── bounded_suggestion.html  # NEW
└── document.html                # MODIFIED — add side panel markup
```

**Structure decision**: Follows the existing single-project layout. New API modules mirror the existing `api/suggestions.py` pattern.

## Complexity Tracking

No constitution violations requiring justification. All decisions align with existing patterns.

| Decision | Complexity Source | Justification |
|----------|------------------|---------------|
| `pymupdf4llm` new dep | New package | Directly required by user; lighter than alternatives |
| `documentlm_core` modification | Cross-package change | Necessary — vector store owned by core; `query_sources_with_metadata` is the minimum addition |

## Phase 0: Research

**Status**: Complete — see [research.md](research.md)

Key decisions resolved:

| Unknown | Decision |
|---------|----------|
| PDF parsing library | `pymupdf4llm` (user-specified) — markdown output stored in `Source.content` |
| Snippet anchor strategy | `char_offset: int` stored per snippet for Document View scroll-to |
| Search result metadata | New `query_sources_with_metadata` returning `list[ChunkResult]` TypedDict |
| Snippet Bank scope | Per `document_id + user_id` (workspace = document) |
| Snippet optionality | Snippets optional; intent required when generation is invoked; user can dismiss UI and type instead |
| Document context in generation | Full document fetched server-side and included in LLM prompt — prevents repetition and loss of focus |
| New agent function | `invoke_bounded_drafter(snippets, intent, cursor_context, document)` reuses `drafter_agent` + `run_agent_text` |
| Side panel architecture | HTMX tab-switch; markdown rendered server-side; minimal JS for scroll-to-anchor only |

## Phase 1: Design

**Status**: Complete

### 1. Data Model

See [data-model.md](data-model.md).

**New table**: `snippets` — 1 Alembic migration.
**No schema changes** to existing tables.
**Modified function**: `_extract_pdf_text` → `_extract_pdf_markdown` using `pymupdf4llm`.
**New core function**: `query_sources_with_metadata` in `documentlm_core`.

### 2. API Contracts

See [contracts/api.md](contracts/api.md).

New endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/documents/{doc_id}/snippets` | Create snippet |
| `GET` | `/api/documents/{doc_id}/snippets` | List snippets |
| `DELETE` | `/api/snippets/{snippet_id}` | Delete snippet |
| `PATCH` | `/api/snippets/{snippet_id}` | Update note/tag |
| `GET` | `/api/sources/{source_id}/view` | Source Document View (HTML) |
| `GET` | `/api/documents/{doc_id}/search` | Semantic search with metadata |
| `POST` | `/api/documents/{doc_id}/bounded-generate` | Bounded text generation |

### 3. Quickstart

See [quickstart.md](quickstart.md).

---

## Implementation Order

Follow this sequence — each step is independently testable before moving to the next.

### Step 1 — Core Infrastructure (no UI)

1. Add `pymupdf4llm` dependency (`uv add pymupdf4llm`)
2. Add `ChunkResult` TypedDict + `query_sources_with_metadata` to `documentlm_core`
3. Re-export from `writer/services/vector_store.py`
4. Replace `_extract_pdf_text` with `_extract_pdf_markdown` in `source_service.py`
5. Write Alembic migration for `snippets` table
6. Add `Snippet` ORM model to `models/db.py`
7. Add new Pydantic schemas to `models/schemas.py`

### Step 2 — Service Layer (TDD)

1. Write and pass tests in `test_snippet_service.py`
2. Implement `snippet_service.py`
3. Write and pass tests in `test_search_service.py`
4. Implement `search_service.py`
5. Write and pass tests in `test_bounded_generation.py`
6. Implement `invoke_bounded_drafter` in `agent_service.py`

### Step 3 — API Layer

1. Implement `api/snippets.py` (CRUD endpoints)
2. Implement `api/search.py` (search endpoint)
3. Implement `api/sources.py` addition (Document View endpoint)
4. Implement `api/generation.py` (bounded generate endpoint)
5. Register all new routers in `main.py`

### Step 4 — Templates

1. `partials/snippet_card.html` — snippet card with delete/edit actions
2. `partials/snippet_bank.html` — full bank list with search input at top
3. `partials/search_results.html` — search result cards with checkbox-to-add
4. `partials/bounded_suggestion.html` — generation result that triggers editor insert
5. `document.html` — add side panel with Document View / Snippet Bank tabs

### Step 5 — Editor JS

1. Add `insertBoundedSuggestion(text)` function to `editor.js`
2. Add bundling UI (floating panel on heading/empty block selection) to `editor.js`
3. Run `npm run build:dev`

### Step 6 — Integration Verification

1. `uv run pytest` — all tests pass
2. `uv run ruff check --fix src/ tests/` — zero violations
3. `uv run mypy src/` — zero errors
4. Manual smoke test: ingest PDF → browse source → save snippet → search → bundle → generate → accept
