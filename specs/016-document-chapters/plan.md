# Implementation Plan: Chapter-Centric Documents

**Branch**: `016-document-chapters` | **Date**: 2026-04-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/016-document-chapters/spec.md`

## Summary

Transform the flat single-content document model into a chapter-based structure. Each document contains one or more chapters with independent titles, briefs, and content. The editor view shows all chapters in a scrollable page with only the active chapter displaying a live TipTap editor. Snippets gain many-to-many chapter association. Existing documents are migrated to single-chapter equivalents. Document.content is maintained as a cached concatenation of all chapters so existing agent, comment, and suggestion flows continue working without modification.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg
**Storage**: PostgreSQL (Docker container) + ChromaDB (local persistent directory)
**Testing**: pytest (backend services only — TDD; no tests for frontend components or API endpoints)
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: web-service (FastAPI + HTMX)
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save
**Scale/Scope**: Demo/prototype — YAGNI; no new features without explicit user confirmation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Python + uv**: All new code is Python; uv used for deps
- [x] **II. TDD scope**: Tests planned for chapter_service and snippet chapter-assignment logic only (not endpoints, not frontend)
- [x] **III. No remote APIs in tests**: All external calls mocked; agent invocations are not tested
- [x] **IV. Simplicity**: Feature scope confirmed via `/speckit.specify` and `/speckit.clarify`; no unrequested extras
- [x] **V. Strong typing**: All new functions use Pydantic models (ChapterCreate, ChapterResponse, etc.) and TypedDicts; no plain dicts; no Any
- [x] **VI. Functional style**: chapter_service as module-level functions; no service classes
- [x] **VII. Ruff**: ruff check + ruff format will be run before every save
- [x] **VIII. Containers**: PostgreSQL stays in Docker; no new infrastructure
- [x] **IX. Logging**: All chapter operations (create, update, delete, reorder) emit structured log entries; no silent exceptions
- [x] **ADK architecture**: No new agent types; existing agents receive chapter-concatenated content via Document.content cache

## Project Structure

### Documentation (this feature)

```text
specs/016-document-chapters/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/writer/
├── api/
│   ├── documents.py      # Existing — minor changes for chapter-aware document loading
│   ├── chapters.py       # NEW — chapter CRUD endpoints
│   └── snippets.py       # Modified — chapter filtering, chapter assignment
├── models/
│   ├── db.py             # Modified — add Chapter model, ChapterSnippet junction
│   └── schemas.py        # Modified — add chapter Pydantic schemas
├── services/
│   ├── chapter_service.py    # NEW — chapter CRUD, reordering, content cache
│   ├── snippet_service.py    # Modified — chapter assignment, chapter-filtered listing
│   └── document_service.py   # Modified — chapter-aware document creation, content rebuild
├── templates/
│   ├── document.html         # Modified — chapter layout, TOC, active editor switching
│   └── partials/
│       ├── chapter_card.html     # NEW — rendered chapter block (title, brief, content)
│       ├── chapter_editor.html   # NEW — active chapter editor (TipTap mount)
│       ├── toc.html              # NEW — table of contents partial
│       ├── snippet_bank.html     # Modified — chapter filter toggle
│       └── snippet_card.html     # Modified — chapter assignment UI
└── agents/                   # No changes — agents receive content via Document.content cache

static/
├── editor.js             # Modified — chapter activation, per-chapter TipTap mounting
├── editor.bundle.js      # Rebuilt after editor.js changes
└── style.css             # Modified — chapter layout, TOC, brief toggle styles

migrations/versions/
└── xxxx_add_chapters.py  # NEW — chapters table, chapter_snippets junction, data migration

tests/unit/
├── test_chapter_service.py   # NEW — TDD for chapter CRUD, reordering, content cache
└── test_snippet_service.py   # Modified — tests for chapter assignment
```

**Structure Decision**: Follows existing project structure. New chapter_service.py mirrors the pattern of document_service.py and snippet_service.py. New chapter API routes follow the existing router pattern. New chapter partials follow the existing partial template pattern.

## Key Design Decisions

### 1. Document.content as Cached Concatenation

Document.content column is preserved. Whenever a chapter is created, updated, deleted, or reordered, the chapter_service rebuilds Document.content by concatenating all chapters in order (with `## {chapter.title}` headings). This means:

- **Agent service**: No changes needed — `invoke_drafter`, `invoke_bounded_drafter`, `invoke_planner` all read Document.content as before.
- **Comments/Suggestions**: Continue to work on markdown char offsets within Document.content. New comments created while editing a chapter will have offsets relative to the full concatenated content (the frontend resolves the offset by computing the chapter's position in the full document).
- **Vector store**: Continues indexing Document.content — no ChromaDB changes needed.

Trade-off: Slight denormalization. A chapter save triggers a full content rebuild. Acceptable for ≤50 chapters in a prototype.

### 2. Single TipTap Instance, Dynamically Mounted

Only one TipTap editor instance exists at a time. When the user clicks a chapter:

1. Save current chapter content (HTMX PUT to chapter endpoint)
2. Replace active chapter's editor with rendered HTML
3. Mount TipTap on the newly clicked chapter with its content
4. Update `#document-content` textarea sync target to the new chapter

This avoids the complexity and performance cost of multiple simultaneous editor instances.

### 3. Snippet Many-to-Many via Junction Table

A `chapter_snippets` junction table links snippets to chapters. A snippet can have zero (unassigned), one, or many chapter associations. The snippet_bank partial accepts a `chapter_id` filter parameter. A toggle switches between "this chapter's snippets" and "all snippets" views.

### 4. Migration Strategy

Alembic migration creates `chapters` and `chapter_snippets` tables, then migrates existing data:

- Each existing document gets one chapter with `title = document.title`, `content = document.content`, `position = 0`
- Each existing snippet gets a `chapter_snippets` row linking it to the document's sole chapter
- Document.content is preserved as-is (already matches the single chapter)
