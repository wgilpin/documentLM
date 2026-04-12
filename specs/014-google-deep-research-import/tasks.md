# Tasks: Import Google Deep Research

**Input**: Design documents from `/specs/014-google-deep-research-import/`  
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: TDD is MANDATORY for `deep_research_service` (service layer). Tests MUST NOT be written for the API endpoint or the template. Tests MUST NOT call remote APIs.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project structure is needed — the project is already initialized. This phase confirms the feature scope and verifies the test environment.

- [X] T001 Verify `uv run pytest tests/unit/` passes cleanly before any changes (baseline)

---

## Phase 2: Foundational — Deep Research Service (Blocking Prerequisite)

**Purpose**: The `deep_research_service` is the core parsing engine that both user stories depend on. It must exist and be tested before any API or UI work.

**⚠️ CRITICAL**: Write failing tests FIRST (TDD). Confirm they fail before implementing.

### Tests (write first, confirm they FAIL)

- [X] T002 [P] Write failing unit tests for `extract_urls` covering: standard `[text](url)` links, duplicate URL dedup, non-http links ignored, display-text-equals-URL fallback to domain name — in `tests/unit/test_deep_research_service.py`
- [X] T003 [P] Write failing unit tests for `parse_markdown_document` covering: title extracted from first H1/H2/H3, filename fallback when no heading, body equals full content, references list populated from `extract_urls` — in `tests/unit/test_deep_research_service.py`

### Implementation

- [X] T004 Create `src/writer/services/deep_research_service.py` with `ExtractedReference` TypedDict (`title: str`, `url: str`), `DeepResearchParseResult` TypedDict (`title: str`, `body: str`, `references: list[ExtractedReference]`), `extract_urls(markdown: str) -> list[ExtractedReference]` pure function (regex `\[([^\]]+)\]\((https?://[^)]+)\)`, dedup by URL, domain-name fallback), and `parse_markdown_document(content: str, filename: str) -> DeepResearchParseResult` pure function — depends on T002, T003

**Checkpoint**: `uv run pytest tests/unit/test_deep_research_service.py` passes. Service is independently testable.

---

## Phase 3: User Story 1 — Upload and Ingest Deep Research Document (Priority: P1) 🎯 MVP

**Goal**: User clicks "Import Google Deep Research", sees instructions, selects a `.md` file, and the document body + all reference URLs are added as sources and queued for ingestion.

**Independent Test**: Navigate to any document's sources panel, click "Import Deep Research", follow modal instructions, select `docs/AI Product Management in Rapid Development.md`, confirm the research document appears as a `note` source and 39 URL sources appear in the sources list.

### Implementation

- [X] T005 [US1] Add `POST /{doc_id}/sources/import-deep-research` endpoint to `src/writer/api/sources.py`: accept `UploadFile` (`.md`), decode UTF-8, call `parse_markdown_document`, create document body source via `source_service.add_source` with `SourceType.note`, create one source per reference URL via `source_service.add_source` with `SourceType.url`, `await db.commit()`, enqueue `run_indexing` background task for each newly created source, return concatenated `partials/sources.html` HTML fragments for HTMX or JSON list for non-HTMX

- [X] T006 [US1] Add "Import Deep Research" button below the `<details class="source-add-details">` block in `src/writer/templates/document.html`: button with `onclick="document.getElementById('import-deep-research-dialog').showModal()"`, consistent styling with existing buttons in the sources panel

- [X] T007 [US1] Add `<dialog id="import-deep-research-dialog">` to `src/writer/templates/document.html` (below the existing `source-note-modal` dialog): include static step-by-step instructions ("1. In Google Deep Research, click Share > Export to Docs", "2. Open the Google Doc", "3. File > Download > Markdown (.md)"), a `<div id="import-deep-research-error">` error container, a `<form>` with `hx-post="/api/documents/{{ doc.id }}/sources/import-deep-research"`, `hx-target="#source-list"`, `hx-swap="beforeend"`, `hx-encoding="multipart/form-data"`, `hx-on::after-request` to close the dialog on success, `<input type="file" name="file" accept=".md" required>`, and a submit button

**Checkpoint**: Full import flow works end-to-end with the sample file. Sources appear in the panel. `uv run pytest` still passes.

---

## Phase 4: User Story 2 — Partial Reference Ingestion (Priority: P2)

**Goal**: When a reference URL is inaccessible or the file is invalid, the system reports failures clearly without blocking the rest of the import.

**Independent Test**: Import a `.md` file containing a mix of valid URLs and a dead link; confirm valid sources are ingested and the failed source shows `indexing_status: failed` with an error message. Import a non-Markdown file; confirm the modal stays open with an inline error.

### Tests (write first, confirm they FAIL)

- [X] T008 [US2] Write failing unit tests for `parse_markdown_document` empty-content case (empty string body and empty references list returns a result with empty body and zero references), and `extract_urls` with a file containing no `https://` links returns empty list — in `tests/unit/test_deep_research_service.py` (append to existing test file — depends on T004)

### Implementation

- [X] T009 [US2] Update `import-deep-research` endpoint in `src/writer/api/sources.py`: if decoded content is empty or `parse_markdown_document` returns empty body and zero references, return HTTP 422 with `HX-Retarget: #import-deep-research-error` and `HX-Reswap: innerHTML` and an inline error HTML fragment; modal must remain open (no `hx-on::after-request` close fires on error status)

- [X] T010 [US2] Verify the `<div id="import-deep-research-error">` added in T007 is correctly targeted by HTMX on 422 responses — confirm via manual test with an empty `.md` file; no code change needed if T007 wired it correctly

**Checkpoint**: Invalid file shows inline error in modal. Valid file with mixed URLs ingests partial results. `uv run pytest` passes.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Code quality gates before the feature is considered done.

- [X] T011 [P] Run `uv run ruff check --fix src/writer/services/deep_research_service.py src/writer/api/sources.py tests/unit/test_deep_research_service.py` and fix any violations
- [X] T012 [P] Run `uv run ruff format src/writer/services/deep_research_service.py src/writer/api/sources.py tests/unit/test_deep_research_service.py`
- [X] T013 Run `uv run mypy src/writer/services/deep_research_service.py src/writer/api/sources.py` and resolve all type errors
- [X] T014 Run `uv run pytest` and confirm all tests pass (no regressions)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **blocks Phases 3 and 4**
- **Phase 3 (US1)**: Depends on Phase 2 — main feature delivery
- **Phase 4 (US2)**: Depends on Phase 2; Phase 3 recommended first (shares endpoint and dialog)
- **Phase 5 (Polish)**: Depends on Phases 3 and 4

### Within Phase 2

- T002 and T003 are parallel (both write to the same file but cover independent functions — write sequentially if only one developer)
- T004 depends on T002 and T003 (tests must exist and fail before implementing)

### Within Phase 3

- T005 (endpoint) → T006 (button) → T007 (dialog) — sequential (dialog references the endpoint URL)
- T005 depends on Phase 2 (calls `deep_research_service`)

### Parallel Opportunities

```
Phase 2:
  T002 ─┐
        ├─→ T004 (implement service)
  T003 ─┘

Phase 3 → Phase 4 (sequential, share endpoint and dialog)

Phase 5:
  T011 ─┐
  T012 ─┤─→ T013 → T014
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Phase 1: Baseline check
2. Phase 2: Service TDD + implementation
3. Phase 3: Endpoint + UI
4. **STOP and VALIDATE**: Import `docs/AI Product Management in Rapid Development.md` — verify 1 note source + 39 URL sources appear

### Full Delivery

1. MVP above
2. Phase 4: Error handling (invalid file inline error, partial ingestion already handled by existing pipeline)
3. Phase 5: Polish

---

## Notes

- No DB migrations required — feature reuses existing `Source` table
- `source_service.add_source` already deduplicates by `(document_id, url, user_id)` — no new dedup logic needed
- `run_indexing` already marks failed sources with `indexing_status: failed` and `error_message` — no new failure-tracking code needed
- The sample file (`docs/AI Product Management in Rapid Development.md`) is the ideal manual test fixture — 39 references, mixed URL styles
- T010 is a verification step, not a code change — if wiring in T007 is correct, T010 is a checkbox tick
