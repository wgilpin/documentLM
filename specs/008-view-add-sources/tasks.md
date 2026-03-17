# Tasks: Document Sources Pane – View and Add Sources

**Input**: Design documents from `/specs/008-view-add-sources/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: TDD is MANDATORY for `get_source()` service function. No tests for API endpoints or templates.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Key Finding: US2/US3/US4 Already Complete

From research.md: The "Add Source" feature (URL / paste text / PDF upload) is **fully implemented** in the existing codebase. The document page already contains a three-tab "Add Source" section with all three input methods. **No new work is required for US2, US3, or US4.**

All remaining work is for **US1 (View Source)**.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new setup is required — no new dependencies, no schema changes, no new migrations.

*This phase is intentionally empty. The existing project infrastructure is sufficient.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational changes required — the `sources` table and all service/model infrastructure already exists.

*This phase is intentionally empty.*

---

## Phase 3: User Story 1 – View an Existing Source (Priority: P1) 🎯 MVP

**Goal**: Add a "View" action to every source item in the sources pane. URL sources open their stored URL in a new tab; note/PDF sources render their stored text via a new lightweight endpoint.

**Independent Test**: Start the dev server, open a document with at least one source of each type, click "View" on each — URL sources should open the external page, note/PDF sources should show their content in a new tab.

### Tests for User Story 1 (service layer — TDD mandatory)

> **Write tests FIRST and confirm they FAIL before any implementation.**
> Tests go in `tests/unit/test_source_service.py`. No endpoint tests. No remote API calls.

- [x] T001 [P] [US1] Add failing unit test `test_get_source_returns_source` to `tests/unit/test_source_service.py` — asserts that `get_source(db, source_id)` returns the correct `SourceResponse` for an existing source
- [x] T002 [P] [US1] Add failing unit test `test_get_source_raises_not_found` to `tests/unit/test_source_service.py` — asserts that `get_source(db, unknown_id)` raises `SourceNotFoundError`

### Implementation for User Story 1

- [x] T003 [US1] Implement `get_source(db: AsyncSession, source_id: UUID) -> SourceResponse` in `src/writer/services/source_service.py` — queries sources table by `source_id`, raises `SourceNotFoundError` (with ERROR-level log) if not found (depends on T001, T002 failing)
- [x] T004 [P] [US1] Create template `src/writer/templates/source_view.html` — standalone HTML page (not a partial) that renders `source.title`, a source-type badge, and `source.content` in a preformatted text block; no JavaScript required
- [x] T005 [US1] Add endpoint `GET /{doc_id}/sources/{source_id}/view` to `src/writer/api/sources.py` — calls `get_source(db, source_id)`, returns 404 if `source.document_id != doc_id` or source not found, renders `source_view.html` (depends on T003, T004)
- [x] T006 [US1] Update `src/writer/templates/partials/sources.html` — add a "View" link next to the existing delete button on each source `<li>`; for `url`-type sources use `<a href="{{ source.url }}" target="_blank" rel="noopener noreferrer">View</a>`; for `note`/`pdf` types use `<a href="/api/documents/{{ doc_id }}/sources/{{ source.id }}/view" target="_blank" rel="noopener noreferrer">View</a>`; guard against null `url` on URL sources; ensure `doc_id` is available in template context (check render call in `GET /{doc_id}/sources` endpoint and pass it if missing) (depends on T005)

**Checkpoint**: At this point, US1 is fully functional — View links appear on all sources, and clicking them opens the correct content in a new tab.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Verification and any final adjustments.

- [x] T007 Run `uv run pytest tests/unit/test_source_service.py` and confirm T001/T002 tests pass (depends on T003)
- [x] T008 [P] Run `uv run ruff check --fix src/ tests/` and `uv run ruff format src/ tests/` to confirm zero lint violations
- [x] T009 [P] Run `uv run mypy src/` and confirm zero type errors in new code
- [x] T010 Manually verify existing Add Source UI: open a document in the dev server, confirm the "Add Source" collapsible contains Note/URL/PDF tabs, and that adding a source via each tab works correctly (smoke test — no automated test needed)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Empty — nothing to do
- **Foundational (Phase 2)**: Empty — nothing to do
- **User Story 1 (Phase 3)**: Can start immediately
- **Polish (Phase 4)**: Depends on Phase 3 completion

### User Story 1 Internal Dependencies

```
T001, T002 (write failing tests)
    ↓
T003 (implement get_source — make tests pass)
T004 (create source_view.html — parallel with T003)
    ↓
T005 (add view endpoint — needs T003 + T004)
    ↓
T006 (update sources.html partial — needs T005)
    ↓
T007, T008, T009, T010 (polish — parallel with each other)
```

### Parallel Opportunities

- T001 and T002 can be written together (same file, sequential within it)
- T003 and T004 can be worked in parallel (different files)
- T007, T008, T009, T010 are fully parallel

---

## Parallel Example: User Story 1

```bash
# Phase 1 of US1: Write failing tests
Task: T001 "Write test_get_source_returns_source in tests/unit/test_source_service.py"
Task: T002 "Write test_get_source_raises_not_found in tests/unit/test_source_service.py"

# Phase 2 of US1: Implement (once tests fail confirmed)
Task: T003 "Implement get_source() in src/writer/services/source_service.py"
Task: T004 "Create src/writer/templates/source_view.html"  ← parallel with T003

# Phase 3 of US1: Wire up
Task: T005 "Add view endpoint to src/writer/api/sources.py"  ← needs T003 + T004
Task: T006 "Update src/writer/templates/partials/sources.html"  ← needs T005

# Polish (all parallel)
Task: T007 "Run pytest"
Task: T008 "Run ruff"
Task: T009 "Run mypy"
Task: T010 "Smoke test add-source UI"
```

---

## Implementation Strategy

### MVP (Single Story)

This feature has only one new user story to implement:

1. Write failing tests (T001, T002) — confirm they fail
2. Implement `get_source()` (T003) — make tests pass
3. Create `source_view.html` template (T004)
4. Add view endpoint (T005)
5. Update sources partial (T006)
6. **STOP and VALIDATE**: Check View links appear and open correct content
7. Run polish tasks (T007–T010)

### Notes

- US2/US3/US4 (Add Source) require **zero implementation work** — already shipped
- The only new file is `src/writer/templates/source_view.html`
- All other changes are additions to existing files
- Total new production code: ~30–50 lines (service function + endpoint + template)
- Total new test code: ~20–30 lines (2 unit tests)
