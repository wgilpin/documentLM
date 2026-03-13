# Tasks: Source Management

**Input**: Design documents from `/specs/002-source-management/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/sources-ui.md ✅

**Tests**: TDD is MANDATORY for backend service code. Tests MUST NOT be written for API endpoints or frontend components. Write failing tests FIRST, confirm they fail, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Key context**: The backend (service, API, data model) is **already fully implemented**. All work is template/UI changes plus one service layer improvement (`PdfParseError`). No migrations needed.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Foundational (Blocking Prerequisite)

**Purpose**: The `PdfParseError` exception must exist before US2 implementation. No other foundational work is required — the project is already set up.

**⚠️ Write the test FIRST and confirm it FAILS before implementing.**

- [X] T001 Write failing unit test for `PdfParseError` being raised on invalid PDF bytes in `tests/unit/test_source_service.py`
- [X] T002 Add `PdfParseError` exception class to `src/writer/services/source_service.py` and raise it (instead of swallowing) inside `_extract_pdf_text` when `PdfReader` fails — confirm T001 now passes

**Checkpoint**: `uv run pytest tests/unit/test_source_service.py` passes; `PdfParseError` is importable

---

## Phase 2: User Story 1 — View Sources (Priority: P1) 🎯 MVP

**Goal**: Users can see all sources for a document — with title, type badge, and date added — and see a clear empty state when no sources exist.

**Independent Test**: Open a document with sources; confirm each entry shows title, type, and date. Open a document with no sources; confirm empty state message appears. No code changes to service or API needed to demo this.

### Implementation for User Story 1

- [X] T00X [P] [US1] Update `src/writer/templates/partials/sources.html` to add `created_at` date display and restructure layout per `contracts/sources-ui.md`
- [X] T00X [P] [US1] Update the HTMX list response in `src/writer/api/sources.py` to return an empty-state `<li class="source-empty-state">` when the source list is empty
- [X] T00X [P] [US1] Rename sidebar section heading from "Core Bucket" to "Sources" in `src/writer/templates/document.html`

**Checkpoint**: Open a document — sources panel shows "Sources" heading; existing sources show title, type, and date; empty documents show "No sources added yet."

---

## Phase 3: User Story 2 — Add a New Source (Priority: P2)

**Goal**: Users can add URL, PDF, and note sources and see inline error messages when input is invalid (bad URL, invalid PDF, empty title).

**Independent Test**: Add one source of each type; confirm each appears in the list. Submit an invalid URL and empty title; confirm inline errors appear without losing entered data. Upload a non-PDF; confirm error message.

### Implementation for User Story 2

- [X] T00X [US2] Update `src/writer/api/sources.py` add_source endpoint to catch `PdfParseError` and return HTTP 422 HTML error fragment for HTMX requests (depends on T002)
- [X] T00X [US2] Add error container `<div>` elements (`#source-error-note`, `#source-error-url`, `#source-error-pdf`) adjacent to each add form in `src/writer/templates/document.html` and update HTMX error target attributes on each form

**Checkpoint**: PDF upload with non-PDF file shows inline error message. URL and note forms still work. Note form shows error when title is empty (HTML5 `required` handles client-side).

---

## Phase 4: User Story 3 — Remove a Source (Priority: P3)

**Goal**: Users can remove any source from the list; it disappears immediately after confirming the prompt.

**Status**: Already fully implemented. The delete button with `hx-confirm` and HTMX outerHTML swap exists in `src/writer/templates/partials/sources.html`.

**Independent Test**: Click × on any source, confirm the prompt, verify it disappears without page reload. Cancel the prompt; verify source remains.

- [X] T00X [US3] Verify remove-source flow manually using `quickstart.md` — no code changes required; mark complete after manual verification passes

**Checkpoint**: Delete flow works end-to-end.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T00X [P] Run `uv run ruff check --fix src/ tests/` and `uv run ruff format src/ tests/` — fix any violations
- [X] T010 [P] Run `uv run mypy src/` — fix any type errors introduced by `PdfParseError` change
- [X] T011 Run full test suite: `uv run pytest` — all tests must pass
- [ ] T012 Walk through `quickstart.md` end-to-end to validate all three user stories in the running app

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: No dependencies — start immediately
- **Phase 2 (US1)**: Independent of Phase 1 — can start in parallel with Phase 1
- **Phase 3 (US2)**: Depends on Phase 1 (T001, T002) — `PdfParseError` must exist
- **Phase 4 (US3)**: No dependencies — already implemented, can verify anytime
- **Phase 5 (Polish)**: Depends on all phases complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories; can start immediately
- **US2 (P2)**: Depends on Phase 1 (`PdfParseError`); independent of US1
- **US3 (P3)**: Already done; no dependencies

### Within Each User Story

- T001 (test) must FAIL before T002 (implementation) — TDD
- T003, T004, T005 are fully independent (different files) — run in parallel
- T006 depends on T002 (PdfParseError must exist)
- T007 is independent of T006 (different file)

### Parallel Opportunities

```bash
# Phase 1 and US1 can start together:
Task T001: Write failing PdfParseError test
Task T003: Update partials/sources.html with date
Task T004: Update list endpoint empty state
Task T005: Rename heading in document.html

# After T002 (PdfParseError implemented):
Task T006: Catch PdfParseError in API endpoint
Task T007: Add error containers in document.html

# Polish (all parallel):
Task T009: ruff
Task T010: mypy
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete T003, T004, T005 (all parallel, no blockers)
2. **STOP and VALIDATE**: Open the app — sources panel shows date, empty state, correct heading
3. Demo-ready

### Full Feature Delivery

1. Phase 1 (T001–T002) + Phase 2 US1 (T003–T005) in parallel → US1 complete
2. Phase 3 US2 (T006–T007) → US2 complete
3. Phase 4 US3 (T008) → US3 verified
4. Phase 5 Polish (T009–T012) → Ship

---

## Notes

- [P] tasks = different files, no dependencies on each other
- Story labels map tasks to spec.md user stories for traceability
- US3 is already implemented — T008 is a verification-only task
- The entire feature is 7 implementation tasks + 1 verification + 4 polish tasks = 12 total
- No migrations, no new schemas, no new routes
