---
description: "Task list for Document Workbench MVP"
---

# Tasks: Document Workbench MVP

**Input**: Design documents from `specs/001-document-workbench-mvp/`
**Prerequisites**: plan.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Tests**: TDD is MANDATORY for backend service code (business logic, data access, transformations).
Tests MUST NOT be written for frontend components or API endpoint handlers.
Tests MUST NOT call remote APIs (LLMs, external HTTP) — use mocks.
Write failing tests FIRST, confirm they fail, then implement.

**ADK note** (from `docs/agents.md`): MVP uses Root Agent + Drafter Agent only.
Session state carries: `selected_text`, `surrounding_context`, `user_instruction`, `core_sources`.
Researcher Agent and SequentialAgent (Ripple Effect) are deferred.

**Organization**: Phases map to user stories for independent delivery.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1, US2, US3)
- All paths relative to repo root

---

## Phase 1: Setup

**Purpose**: Project scaffolding and cross-cutting infrastructure.

- [X] T001 Verify `uv sync` resolves with updated pyproject.toml (google-adk, sqlalchemy, asyncpg, alembic, pypdf); fix version conflicts if any
- [X] T002 [P] Create `src/writer/core/config.py` — pydantic-settings `Settings` class loading `DATABASE_URL` and `GOOGLE_API_KEY` from env
- [X] T003 [P] Create `src/writer/core/logging.py` — configure stdlib `logging` with structured format; expose `get_logger(name: str) -> logging.Logger`
- [X] T004 [P] Create `.env.example` with `DATABASE_URL=postgresql+asyncpg://writer:writer@localhost:5432/writer` and `GOOGLE_API_KEY=`
- [X] T005 Create `Dockerfile` — `python:3.13-slim`, install uv, copy project, `uv sync --no-dev`, CMD `uvicorn writer.main:app`
- [X] T006 Create `docker-compose.yml` — `postgres:16-alpine` service (env: `POSTGRES_DB/USER/PASSWORD=writer`) and `app` service (build `.`, depends_on postgres, env_file `.env`, ports `8000:8000`)
- [X] T007 Create `src/writer/main.py` — FastAPI app with lifespan (engine dispose on shutdown), mount `static/`, register Jinja2 `TemplatingResponse`, include API routers and UI routes

---

## Phase 2: Foundational

**Purpose**: Database layer that ALL user stories depend on. No story work begins until this phase is complete.

**⚠️ CRITICAL**: Blocks all user stories.

- [X] T008 Create `src/writer/core/database.py` — async SQLAlchemy engine (`create_async_engine`), `AsyncSession` factory (`async_sessionmaker`), `get_db()` FastAPI dependency, `Base` declarative base
- [X] T009 Create `src/writer/models/db.py` — four ORM models: `Document` (id UUID PK, title, content, created_at, updated_at); `Source` (id, document_id FK, source_type enum, title, content, url, created_at); `Comment` (id, document_id FK, selection_start, selection_end, selected_text, body, status enum, created_at); `Suggestion` (id, comment_id FK, original_text, suggested_text, status enum, created_at). All timestamps UTC. All enums match data-model.md.
- [X] T010 [P] Create `src/writer/models/schemas.py` — Pydantic v2 models: `DocumentCreate`, `DocumentUpdate`, `DocumentResponse`, `DocumentSummary`, `SourceCreate`, `SourceResponse`, `CommentCreate`, `CommentResponse`, `SuggestionResponse`. No plain dicts. Use `model_config = ConfigDict(from_attributes=True)`.
- [X] T011 Initialise Alembic: `uv run alembic init migrations`; configure `migrations/env.py` to use async engine and import `Base` from `src/writer/models/db.py`; generate initial migration `uv run alembic revision --autogenerate -m "initial schema"`; verify migration SQL is correct
- [X] T012 [P] Create `src/writer/templates/base.html` — HTML5 base template: HTMX CDN (`<script src="https://unpkg.com/htmx.org@2">`), link to `static/style.css`, `{% block content %}` slot. No other JS.
- [X] T013 [P] Create `static/style.css` — minimal layout styles: two-column editor/sidebar, suggestion card styling, source list. No JS.

**Checkpoint**: `docker-compose up -d postgres && uv run alembic upgrade head` succeeds with all four tables created.

---

## Phase 3: User Story 1 — Document Creation & Management (Priority: P1) 🎯 MVP

**Goal**: Users can create a document, view the list, open the editor, type markdown content, and save it.

**Independent Test**: Navigate to `http://localhost:8000`, create a document titled "Test Doc", type content, save — document reappears in the list with updated content.

### Tests for User Story 1 (backend services only — MANDATORY for service layer)

> **Write tests FIRST and confirm they FAIL before any implementation.**
> Tests go in `tests/unit/`. Do NOT test the API endpoints or templates.
> Mock the DB session using `AsyncMock` — do NOT hit a real database in unit tests.

- [X] T014 [P] [US1] Write unit tests for `document_service` in `tests/unit/test_document_service.py` — test `create_document`, `get_document`, `list_documents`, `update_document`, `delete_document`; mock `AsyncSession`; assert correct Pydantic types returned; confirm tests FAIL before implementation

### Implementation for User Story 1

- [X] T015 [US1] Implement `src/writer/services/document_service.py` — pure async functions: `create_document(db, data: DocumentCreate) -> DocumentResponse`, `get_document(db, id: UUID) -> DocumentResponse`, `list_documents(db) -> list[DocumentSummary]`, `update_document(db, id, data: DocumentUpdate) -> DocumentResponse`, `delete_document(db, id: UUID) -> None`. Log all operations. Raise typed exceptions (not plain strings) on not-found.
- [X] T016 [P] [US1] Create `src/writer/templates/index.html` — extends `base.html`; shows document list with title, updated_at, link to editor; "New Document" button (`hx-get="/documents/new"` or simple link)
- [X] T017 [P] [US1] Create `src/writer/templates/document.html` — extends `base.html`; two-column layout: left = `<textarea id="document-content">` with `hx-put="/api/documents/{{doc.id}}"` `hx-trigger="keyup delay:1s"` for auto-save; right = sidebar (source list + suggestion panel placeholders)
- [X] T018 [US1] Implement `src/writer/api/documents.py` — FastAPI router `/api/documents`: `GET /` → `list_documents`, `POST /` → `create_document` (201), `GET /{id}` → `get_document` (404 on miss), `PUT /{id}` → `update_document`, `DELETE /{id}` → `delete_document` (204). All call service functions; no business logic in handlers.
- [X] T019 [US1] Add UI routes in `src/writer/main.py` — `GET /` → `index.html` (document list), `GET /documents/new` → `document.html` (blank), `GET /documents/{id}` → `document.html` (populated). Register `documents` API router.

**Checkpoint**: Create a document via the UI, type content, verify auto-save updates the DB, refresh the page and see the content restored.

---

## Phase 4: User Story 2 — Source Ingestion / Core Bucket (Priority: P2)

**Goal**: Users can add sources (typed note, URL reference, PDF upload) to a document's Core Bucket and see them listed in the sidebar.

**Independent Test**: Open a document, add a typed note source with some text — it appears in the sidebar source list. Upload a PDF — extracted text is shown. All sources persist after page refresh.

### Tests for User Story 2 (backend services only — MANDATORY for service layer)

> Write tests FIRST, confirm they FAIL, then implement. No remote API calls. No endpoint tests.

- [X] T020 [P] [US2] Write unit tests for `source_service` in `tests/unit/test_source_service.py` — test `add_source_note`, `add_source_url`, `add_source_pdf` (mock pypdf extraction), `list_sources`, `delete_source`; assert `SourceResponse` type returned; mock `AsyncSession`; confirm tests FAIL before implementation

### Implementation for User Story 2

- [X] T021 [US2] Implement `src/writer/services/source_service.py` — async functions: `add_source(db, data: SourceCreate) -> SourceResponse` (dispatches by `source_type`); `add_source_pdf(db, document_id: UUID, title: str, file_bytes: bytes) -> SourceResponse` (calls `_extract_pdf_text`); `_extract_pdf_text(file_bytes: bytes) -> str` (uses `pypdf`); `list_sources(db, document_id: UUID) -> list[SourceResponse]`; `delete_source(db, source_id: UUID) -> None`. Log all operations. All exceptions caught and logged.
- [X] T022 [P] [US2] Create `src/writer/templates/partials/sources.html` — renders a single `<li>` source item with title, type badge, delete button (`hx-delete` → removes item via `hx-swap="outerHTML"`)
- [X] T023 [US2] Implement `src/writer/api/sources.py` — FastAPI router `/api/documents/{doc_id}/sources`: `GET /` → `list_sources` (returns HTML partial if `HX-Request` header, else JSON); `POST /` → handles JSON (note/url) and multipart (pdf), calls `source_service`; `DELETE /{source_id}` → `delete_source` (204). Register router in `main.py`.
- [X] T024 [US2] Add source sidebar to `src/writer/templates/document.html` — source list (`<ul id="source-list">` loaded via `hx-get`), add-source form (three tabs: Note/URL/PDF) with `hx-post` targeting `#source-list` with `hx-swap="beforeend"`

**Checkpoint**: Add a note, a URL reference, and a PDF source — all three appear in the sidebar and persist on refresh. Delete a source — it disappears immediately via HTMX without page reload.

---

## Phase 5: User Story 3 — AI Drafting via Margin Comments + Accept/Reject (Priority: P3)

**Goal**: User highlights text, types a margin comment, the Drafter Agent generates a suggestion shown in the sidebar. User accepts (document updates) or rejects (suggestion dismissed).

**Independent Test**: Open a document with some content and at least one Core Bucket source. Select a sentence, type "Expand this with more detail", submit — AI suggestion appears in sidebar. Click Accept — document textarea updates. Click Reject on another suggestion — it disappears.

**ADK session.state** (from `docs/agents.md`): When invoking the Drafter, populate `session.state` with:
- `selected_text`: the highlighted text
- `surrounding_context`: 500 chars before and after the selection
- `user_instruction`: the comment body
- `core_sources`: concatenated text of all Core Bucket sources for this document

### Tests for User Story 3 (backend services only — MANDATORY for service layer)

> Write tests FIRST, confirm they FAIL, then implement. No remote API calls.
> Mock the ADK `Runner.run_async` — NEVER call the Gemini API in tests.

- [X] T025 [P] [US3] Write unit tests for `agent_service` in `tests/unit/test_agent_service.py` — test `invoke_drafter(comment, document, sources)`: mock `Runner.run_async` to return a fixed `suggested_text`; assert returned `str` is correct; test stale-check helper `is_selection_valid(document_content, start, end, selected_text) -> bool`; confirm tests FAIL before implementation
- [X] T026 [P] [US3] Write unit tests for suggestion lifecycle in `tests/unit/test_document_service.py` (extend existing file) — test `accept_suggestion` replaces text span correctly; test `reject_suggestion` sets status; mock DB session

### Implementation for User Story 3

- [X] T027 [P] [US3] Implement `src/writer/agents/drafter_agent.py` — define ADK `Agent` with `name="drafter"`, `model="gemini-2.0-flash"`, and a system instruction that instructs the agent to rewrite or expand the `selected_text` based on `user_instruction`, using `core_sources` as grounding context. Return only the replacement text.
- [X] T028 [US3] Implement `src/writer/agents/root_agent.py` — define Root `Agent` with `name="root"`, `model="gemini-2.0-flash"`, `sub_agents=[drafter_agent]`. Root agent's instruction: route margin-comment requests to the Drafter sub-agent. Create a module-level `root_agent` singleton. (As per `docs/agents.md` §1: Root Agent is the main dispatcher.)
- [X] T029 [US3] Implement `src/writer/services/agent_service.py` — `invoke_drafter(comment: CommentResponse, document: DocumentResponse, sources: list[SourceResponse]) -> str`: build `session.state` dict (`selected_text`, `surrounding_context`, `user_instruction`, `core_sources`); create `InMemorySessionService`; create `Runner(agent=root_agent, ...)`; call `runner.run_async(...)`; extract and return the Drafter's text response. Log invocation start, success, and any exceptions (never silent). Raise on failure.
- [X] T030 [US3] Add `accept_suggestion` and `reject_suggestion` to `src/writer/services/document_service.py` — `accept_suggestion(db, suggestion_id: UUID) -> DocumentResponse`: stale-check selection, update `document.content`, set `suggestion.status=accepted`, `comment.status=resolved`. `reject_suggestion(db, suggestion_id: UUID) -> SuggestionResponse`: set `suggestion.status=rejected`, `comment.status=resolved`. Log all state transitions.
- [X] T031 [US3] Implement `src/writer/api/suggestions.py` — FastAPI router: `POST /api/documents/{doc_id}/comments` → validate selection, call `agent_service.invoke_drafter`, persist Comment + Suggestion, return HTML partial if `HX-Request`; `GET /api/documents/{doc_id}/suggestions` → list pending; `POST /api/suggestions/{id}/accept` → `document_service.accept_suggestion`, return updated content partial; `POST /api/suggestions/{id}/reject` → `document_service.reject_suggestion`, return empty (HTMX removes element). Register router in `main.py`.
- [X] T032 [P] [US3] Create `src/writer/templates/partials/suggestion.html` — renders a suggestion card: shows `original_text` struck-through, `suggested_text` highlighted; Accept button (`hx-post="/api/suggestions/{{s.id}}/accept"` `hx-target="#document-content"` `hx-swap="innerHTML"`); Reject button (`hx-post="/api/suggestions/{{s.id}}/reject"` `hx-target="#suggestion-{{s.id}}"` `hx-swap="outerHTML"`)
- [X] T033 [US3] Add text-selection capture to `src/writer/templates/document.html` — add a single inline `<script>` block (not an external file) that on `mouseup` reads `window.getSelection()` and writes `selectionStart`, `selectionEnd`, `selectedText` into hidden `<input>` fields on the comment form. Add comment form to sidebar with `hx-post` targeting `#suggestion-panel` `hx-swap="innerHTML"`.

**Checkpoint**: Full flow — comment submitted, ADK invoked, suggestion appears in sidebar, Accept updates the textarea, Reject removes the card — all without page reload.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [X] T034 [P] Create `tests/integration/test_db.py` — integration tests using a real test PostgreSQL DB (Docker): test round-trip create/read/delete for Document and Source via services; verify DB constraints; uses pytest fixture to set up and tear down DB
- [X] T035 [P] Add `mypy` type stubs for `google-adk` if not bundled (`py.typed` marker); add `sqlalchemy` stubs; ensure `uv run mypy src/` passes with zero errors
- [X] T036 Run full validation per `specs/001-document-workbench-mvp/quickstart.md`: all steps execute cleanly; app starts; full user journey (create doc → add source → submit comment → accept suggestion) completes without errors

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T002/T003/T004 fully parallel
- **Foundational (Phase 2)**: Depends on T007 (main.py) — T009/T010/T012/T013 parallel after T008
- **US1 (Phase 3)**: Depends on Phase 2 completion — T016/T017 parallel after T015; T018/T019 sequential
- **US2 (Phase 4)**: Depends on Phase 2 completion — T022 parallel; T023/T024 after T021
- **US3 (Phase 5)**: Depends on Phase 2 + ideally US1 for testing end-to-end — T027 parallel; T028→T029→T030→T031 sequential; T032/T033 parallel
- **Polish**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no cross-story dependencies
- **US2 (P2)**: After Phase 2 — independent of US1 (shares DB layer only)
- **US3 (P3)**: After Phase 2 — agent tasks (T027/T028) can start immediately; suggestion lifecycle (T030) depends on US1's `document_service`

### Within Each User Story

- Service-layer tests MUST be written and FAIL before implementation (TDD — mandatory)
- Tests for API endpoints and frontend components MUST NOT be written
- Models (Phase 2) before services → services before endpoints

---

## Parallel Opportunities

### Phase 1 parallel burst
```
T002 (config.py)    ─┐
T003 (logging.py)   ─┤─ all parallel (different files)
T004 (.env.example) ─┘
T005 (Dockerfile) ──┐
T006 (docker-compose)┘ parallel
```

### Phase 2 parallel burst (after T008 DB engine done)
```
T009 (db.py ORM)   ─┐
T010 (schemas.py)  ─┤─ parallel (T010 depends on T009 types but can draft in parallel)
T012 (base.html)   ─┤
T013 (style.css)   ─┘
T011 (alembic) ── after T009
```

### US3 parallel burst
```
T025 (agent_service tests)  ─┐
T026 (suggestion tests)     ─┤─ parallel (write before implementation)
T027 (drafter_agent.py)     ─┘
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL — blocks all stories**)
3. Complete Phase 3: US1 — Document CRUD
4. **STOP and VALIDATE**: Create a document via UI, auto-save works, content persists
5. Deploy/demo the document editor stub

### Incremental Delivery

1. Foundation → US1 (document editor) → **demo: blank editor working**
2. Add US2 (source ingestion) → **demo: sources appear in sidebar**
3. Add US3 (AI drafting) → **demo: full AI workflow end-to-end**

---

## Task Summary

| Phase | Tasks | Parallel | Story |
|---|---|---|---|
| Setup | T001–T007 | T002/T003/T004, T005/T006 | — |
| Foundational | T008–T013 | T009/T010/T012/T013 | — |
| US1 Documents | T014–T019 | T014, T016/T017 | US1 |
| US2 Sources | T020–T024 | T020, T022 | US2 |
| US3 AI Drafting | T025–T033 | T025/T026/T027, T032/T033 | US3 |
| Polish | T034–T036 | T034/T035 | — |
| **Total** | **36 tasks** | | |

**Independent test for each story**:
- US1: Create doc → save → refresh → content preserved ✅
- US2: Add note/URL/PDF → appears in sidebar → persists on refresh ✅
- US3: Select text → comment → AI suggestion → accept updates doc ✅
