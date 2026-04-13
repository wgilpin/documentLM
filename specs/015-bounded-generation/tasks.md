# Tasks: Bounded Generation & Curation Workflow

**Input**: Design documents from `specs/015-bounded-generation/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Tests**: TDD is MANDATORY for backend service code (snippet_service, search_service, agent_service, source_service).
Tests MUST NOT be written for API endpoint handlers or frontend components.
Tests MUST NOT call remote APIs — mock `run_agent_text` and `query_sources_with_metadata`.
Write failing tests FIRST, confirm they fail, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies and extend core vector store — required before any story work begins.

- [X] T001 Add `pymupdf4llm` and `markdown` dependencies to `src/writer/pyproject.toml` by running `uv add pymupdf4llm markdown` from the repo root
- [X] T002 [P] Add `ChunkResult` TypedDict and `query_sources_with_metadata(query_text, user_id, doc_id, is_private_doc, top_k) -> list[ChunkResult]` to `documentlm_core/src/documentlm_core/services/vector_store.py` — queries ChromaDB and returns metadata alongside text (see data-model.md)
- [X] T003 Re-export `ChunkResult` and `query_sources_with_metadata` from `src/writer/services/vector_store.py` so writer services access them via the local package

**Checkpoint**: `uv run python -c "from writer.services.vector_store import query_sources_with_metadata, ChunkResult"` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema and Pydantic contracts that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Add `Snippet` SQLAlchemy ORM model (id, document_id, source_id, user_id, text, char_offset, note, tag, created_at) to `src/writer/models/db.py` — see exact class definition in data-model.md
- [X] T005 [P] Add `SnippetCreate`, `SnippetUpdate`, `SnippetResponse`, `SearchResultItem`, `SearchResponse`, `BoundedGenerateRequest`, `BoundedGenerationResponse` Pydantic schemas to `src/writer/models/schemas.py` — see exact field definitions in data-model.md; `BoundedGenerateRequest.intent` must have `min_length=1, max_length=500`
- [X] T006 Write Alembic migration for the `snippets` table in `migrations/versions/` via `uv run alembic revision --autogenerate -m "add_snippets_table"`, review the generated file, then apply with `uv run alembic upgrade head` (ask user before running docker/alembic commands if DB container is not already running)

**Checkpoint**: Foundation ready — snippet model importable and migration applied.

---

## Phase 3: User Story 1 — Ingest and Browse a Source Document (Priority: P1) 🎯 MVP

**Goal**: Upgrade PDF extraction to markdown output and expose source content in a browsable Document View panel within the side panel.

**Independent Test**: Upload a PDF → system processes it with pymupdf4llm → user opens Document View in side panel → headings and paragraphs from the PDF are visible. No snippet or generation features needed.

### Tests for User Story 1 (TDD — write and confirm FAILING before implementing)

- [X] T007 [US1] Write failing unit tests for `_extract_pdf_markdown` in `tests/unit/test_source_service.py`: (1) valid PDF bytes → returns non-empty markdown string containing text; (2) image-only / empty PDF bytes → raises `PdfParseError` — mock `fitz.open` or use a minimal synthetic PDF fixture; confirm tests FAIL before proceeding

### Implementation for User Story 1

- [X] T008 [US1] Replace `_extract_pdf_text` (pypdf) with `_extract_pdf_markdown` (pymupdf4llm/fitz) in `src/writer/services/source_service.py` — detect empty output and raise `PdfParseError("PDF contains no extractable text (may be image-only)")` (see data-model.md for exact function signature)
- [X] T009 [P] [US1] Add `GET /api/sources/{source_id}/view` endpoint to `src/writer/api/sources.py` — fetch source from DB, render `source.content` markdown to HTML using the `markdown` Python library, return rendered HTML for HTMX panel swap
- [X] T010 [P] [US1] Create `templates/partials/source_view.html` for Document View — scrollable `<div>` containing the server-rendered markdown HTML; include a `data-char-offset` attribute on each paragraph so JS can scroll to a character offset
- [X] T011 [US1] Add side panel to `templates/document.html` — two tabs: "Document View" (HTMX `hx-get` to `/api/sources/{id}/view`) and "Snippet Bank" (HTMX `hx-get` to `/api/documents/{doc_id}/snippets`); panel renders alongside the main editor
- [X] T012 [US1] Register the updated sources router (with new `/view` endpoint) in `src/writer/main.py`

**Checkpoint**: User Story 1 fully functional — source ingests as markdown, Document View tab loads and displays content.

---

## Phase 4: User Story 2 — Save Text Snippets to the Scratchpad (Priority: P1)

**Goal**: Allow users to highlight text in Document View and save it as a snippet card in the Snippet Bank, with source attribution, optional note/tag, delete, and scroll-back navigation.

**Independent Test**: Open source in Document View → highlight text → save as snippet → Snippet Bank tab shows the card with source name → delete snippet → it disappears. No search or generation needed.

### Tests for User Story 2 (TDD — write and confirm FAILING before implementing)

- [X] T013 [P] [US2] Write failing unit tests for `snippet_service` in `tests/unit/test_snippet_service.py`: `create_snippet` (happy path, document not found 404), `list_snippets` (empty list, multiple ordered by created_at desc), `delete_snippet` (happy path, not found, wrong user), `update_snippet` (note/tag update, not found), `get_snippet_with_source_title` (joins source.title, source deleted → `source_title=None`) — mock the DB session; confirm all tests FAIL before proceeding

### Implementation for User Story 2

- [X] T014 [US2] Implement `create_snippet`, `list_snippets`, `delete_snippet`, `update_snippet`, `get_snippet_with_source_title` in `src/writer/services/snippet_service.py` — all functions take async SQLAlchemy session; `list_snippets` returns `list[SnippetResponse]` ordered `created_at DESC`; log start/success/error in every function
- [X] T015 [US2] Implement Snippet CRUD endpoints in `src/writer/api/snippets.py`: `POST /api/documents/{doc_id}/snippets` (create), `GET /api/documents/{doc_id}/snippets` (list, returns `snippet_bank.html` partial), `DELETE /api/snippets/{snippet_id}` (delete, returns updated bank partial), `PATCH /api/snippets/{snippet_id}` (update note/tag)
- [X] T016 [P] [US2] Create `templates/partials/snippet_card.html` — displays snippet text, source document name (or "Source unavailable" if `source_id` is null), optional note/tag, delete button (HTMX `hx-delete`), and "Go to source" link that triggers `char_offset` scroll in Document View
- [X] T017 [US2] Create `templates/partials/snippet_bank.html` — renders the full list of snippet cards using `snippet_card.html`; includes search input at top wired to Phase 5 search endpoint via HTMX (search input should be disabled or render a "search not yet available" message until Phase 5 is complete)
- [X] T018 [US2] Add text-selection handler and `scrollToCharOffset(sourceId, offset)` function to `static/editor.js` — on `mouseup` within the Document View panel, detect selection text and char offset, show a "Save to Scratchpad" tooltip; on confirm, POST to `/api/documents/{doc_id}/snippets` via HTMX and refresh Snippet Bank tab; `scrollToCharOffset` finds the paragraph `<div>` with nearest `data-char-offset` ≤ offset and calls `.scrollIntoView()` for "Go to source" links; run `npm run build:dev` after this change
- [X] T019 [US2] Register the snippets router in `src/writer/main.py`

**Checkpoint**: User Story 2 fully functional — snippets saved, listed, deleted, notes editable, source scroll works.

---

## Phase 5: User Story 3 — Search the Source Corpus Semantically (Priority: P2)

**Goal**: Users type a query into the Snippet Bank search bar; semantically ranked results appear as cards across all ingested sources; checking a card adds it to the Snippet Bank instantly.

**Independent Test**: Two ingested sources → type query → results appear from both sources with source names → check a result → it appears in Snippet Bank as a snippet. No generation needed.

### Tests for User Story 3 (TDD — write and confirm FAILING before implementing)

- [X] T020 [P] [US3] Write failing unit tests for `search_service` in `tests/unit/test_search_service.py`: mock `query_sources_with_metadata` to return sample `list[ChunkResult]`; verify `search_document_corpus` resolves source titles from DB and returns `SearchResponse` with correct `SearchResultItem` list; test no-results path returns empty list (not an error) — confirm all tests FAIL before proceeding

### Implementation for User Story 3

- [X] T021 [US3] Implement `search_document_corpus(query: str, user_id: UUID, doc_id: UUID, session: AsyncSession) -> SearchResponse` in `src/writer/services/search_service.py` — calls `query_sources_with_metadata`, resolves `source_id` → `source.title` via DB lookup, returns `SearchResponse`; log query and result count; if no results return empty `SearchResponse` (not an error)
- [X] T022 [US3] Implement `GET /api/documents/{doc_id}/search?q={query}` endpoint in `src/writer/api/search.py` — calls `search_document_corpus`, returns `search_results.html` partial via HTMX
- [X] T023 [US3] Create `templates/partials/search_results.html` — renders ranked result cards, each showing passage text and source document name; each card has a checkbox; checking it POSTs to `/api/documents/{doc_id}/snippets` to save the result as a snippet and refreshes the Snippet Bank; also update `snippet_bank.html` (T017) to enable the search input now that the endpoint exists
- [X] T024 [US3] Register the search router in `src/writer/main.py`

**Checkpoint**: User Story 3 fully functional — semantic search returns results, checking a result adds it to the Snippet Bank.

---

## Phase 6: User Story 4 — Bundle Snippets and Generate Bounded Text (Priority: P2)

**Goal**: User selects a heading or empty block in the editor, invokes the bundling panel, optionally selects snippets, types an intent, and generates a suggested text block inserted into the editor as a pending suggestion.

**Independent Test**: Snippets in bank + empty block in editor → open bundling panel → check snippets → type intent → confirm → suggested text appears inline in editor → accept → committed to document. All prior stories must work.

### Tests for User Story 4 (TDD — write and confirm FAILING before implementing)

- [X] T025 [P] [US4] Write failing unit tests for `invoke_bounded_drafter` in `tests/unit/test_bounded_generation.py`: mock `run_agent_text` to return `"generated text"`; verify prompt passed to `run_agent_text` contains the full document content, each snippet formatted as `"{text} (Source: {source_title})"`, the `cursor_context`, and the `intent` string; test with zero snippets (intent still required); test empty intent raises `ValueError` — confirm all tests FAIL before proceeding

### Implementation for User Story 4

- [X] T026 [US4] Implement `invoke_bounded_drafter(snippets: list[tuple[str, str]], intent: str, cursor_context: str, document_content: str) -> str` in `src/writer/services/agent_service.py` — `snippets` is a list of `(text, source_title)` pairs; builds prompt per research.md Decision 6 message format (FULL DOCUMENT / EVIDENCE SNIPPETS as `"{text} (Source: {source_title})"` / INSERTION POINT / Intent sections); calls existing `run_agent_text` with `drafter_agent`; raises `ValueError` if `intent` is empty; log all inputs at DEBUG, result at INFO
- [X] T027 [US4] Implement `POST /api/documents/{doc_id}/bounded-generate` endpoint in `src/writer/api/generation.py` — accepts `BoundedGenerateRequest` (snippet_ids, intent, cursor_context); fetches snippets with source titles from DB using `get_snippet_with_source_title`; builds `list[tuple[str, str]]` of (text, source_title) pairs; fetches document content; calls `invoke_bounded_drafter`; returns `bounded_suggestion.html` partial
- [X] T028 [P] [US4] Create `templates/partials/bounded_suggestion.html` — renders the `suggested_text` in a visually distinct state (e.g. highlighted/bordered block); triggers `insertBoundedSuggestion(text)` using HTMX `hx-on::htmx:afterSwap` attribute only — no inline `<script>` tags (CLAUDE.md: all JS must be in static files)
- [X] T029 [P] [US4] Add `insertBoundedSuggestion(text: string): void` function to `static/editor.js` — inserts `text` at the current cursor position using the existing TipTap suggestion insertion mechanism (see existing `insertSuggestion` usage in editor.js); this function must be globally accessible so the `hx-on` attribute in T028 can call it
- [X] T030 [US4] Add bundling panel UI to `static/editor.js` — detects cursor on heading or empty paragraph block (TipTap selection events); shows a floating panel listing all snippet bank cards with checkboxes (fetched via HTMX from `/api/documents/{doc_id}/snippets`); includes intent `<textarea>` (max 500 chars); "Generate" button disabled until intent is non-empty; on confirm, POSTs to `/api/documents/{doc_id}/bounded-generate` via HTMX and swaps in `bounded_suggestion.html` result; panel has a "Cancel / type myself" dismiss affordance
- [X] T031 [US4] Run `npm run build:dev` to rebuild `static/editor.bundle.js` after all editor.js changes in T018, T029, and T030
- [X] T032 [US4] Register the generation router in `src/writer/main.py`

**Checkpoint**: User Story 4 fully functional — full Search → Select → Synthesize loop works end-to-end.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, final integration verification, and smoke testing.

- [X] T033 Run `cd /Users/will/projects/document-projects/documentLM && uv run pytest` — all tests must pass; fix any failures before proceeding
- [X] T034 [P] Run `cd /Users/will/projects/document-projects/documentLM && uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/` — zero violations
- [X] T035 [P] Run `cd /Users/will/projects/document-projects/documentLM && uv run mypy src/` — zero type errors
- [ ] T036 Manual smoke test: ingest a PDF source → open Document View in side panel → verify markdown headings render → highlight a passage → save as snippet → verify snippet card appears in Snippet Bank → type a semantic search query → verify ranked results → check a result to add it to bank → place cursor on empty block in editor → invoke bundling panel → select snippets → type intent → confirm generation → verify suggestion appears inline → accept → confirm text committed to document

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — no dependency on US2/US3/US4
- **Phase 4 (US2)**: Depends on Phase 2 — builds on US1's side panel but independently testable at service level
- **Phase 5 (US3)**: Depends on Phase 2 — independently testable; integrates with US2 Snippet Bank UI
- **Phase 6 (US4)**: Depends on US1 (document content), US2 (snippet retrieval), and US3 (search results as snippets)
- **Phase 7 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: Independent after Phase 2
- **US2 (P1)**: Independent after Phase 2; builds on US1 side panel UI (can be developed in parallel at service level)
- **US3 (P2)**: Independent after Phase 2; integrates snippet add button into US2 Snippet Bank template
- **US4 (P2)**: Depends on US1 (document fetch), US2 (snippet retrieval), and US3 (snippets added via search)

### Within Each User Story

1. Write service tests (confirm they FAIL)
2. Implement service logic (make tests pass)
3. Implement API endpoints
4. Implement templates
5. Register router in main.py

---

## Parallel Opportunities

### Phase 1

```
T001 (install deps) → T003 (re-export)
T002 (documentlm_core changes) → T003 (re-export)
```

T001 and T002 can run in parallel; T003 depends on both.

### Phase 2

T004 (ORM model) and T005 (schemas) can run in parallel; T006 (migration) depends on T004.

### Phase 3 (US1)

T007 (PDF extraction tests) must complete before T008 (implementation). After T008, T009 (view endpoint) and T010 (source_view.html template) can run in parallel — different files.

### Phase 4 (US2)

T013 (snippet service tests) and T016 (snippet_card.html template) can run in parallel once Phase 2 is complete.

### Phase 5 (US3)

T020 (search service tests) runs in parallel with T022 (search endpoint scaffold) once Phase 2 is complete.

### Phase 6 (US4)

T025 (bounded drafter tests), T028 (bounded_suggestion.html template), and T029 (insertBoundedSuggestion function) can all run in parallel — different files, no shared dependencies.

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T006)
3. Complete Phase 3: US1 (T007–T012)
4. Complete Phase 4: US2 (T013–T019)
5. **STOP and VALIDATE**: ingest PDF → browse → save snippets → bank persists across reload
6. Demo if ready — Search and Generation are additive

### Incremental Delivery

1. Phase 1 + 2 → Infrastructure ready
2. Phase 3 (US1) → PDF ingestion + Document View browsing (standalone value)
3. Phase 4 (US2) → Snippet curation (core differentiator, standalone note-taking tool)
4. Phase 5 (US3) → Semantic search accelerates evidence gathering
5. Phase 6 (US4) → Bounded generation completes the Search → Select → Synthesize loop

---

## Notes

- All `uv run` commands must be prefixed with `cd /Users/will/projects/document-projects/documentLM &&`
- Run `npm run build:dev` (T031) after all editor.js changes — covers T018, T029, and T030
- Never call `run_agent_text` or `query_sources_with_metadata` in tests — mock both
- `Source.content` changes format (plain text → markdown) for new PDFs; existing sources retain plain text — no migration required for content column
- `Snippet.source_id` is nullable (SET NULL on source delete) — snippet cards must handle `source_id = None` gracefully with "Source unavailable" display
- Alembic and docker-compose commands require user confirmation before execution
- `invoke_bounded_drafter` takes `list[tuple[str, str]]` (text, source_title) pairs — T027 must build this list before calling the service
