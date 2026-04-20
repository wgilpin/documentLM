---
description: "Task list for feature 017: Chapter-Scoped Sources and Snippets (Phase 1 — Manual Tagging)"
---

# Tasks: Chapter-Scoped Sources and Snippets (Phase 1)

**Input**: Design documents from `/specs/017-chapter-scoped-research/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: TDD is MANDATORY for backend service code (Constitution II). No tests for API endpoints, Jinja templates, or frontend JS. No remote API calls in tests.

**Organization**: Tasks are grouped by user story. US1 (sources) is the MVP — independently testable end-to-end. US2 (snippets) and US3 (auto-default filter) are independent increments.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to user story from spec.md (US1, US2, US3)
- File paths are absolute under repo root `/Users/will/projects/document-projects/documentLM/`

---

## Phase 1: Setup

**Purpose**: Confirm baseline before any work begins.

- [X] T001 Confirm working tree clean and on branch `017-chapter-scoped-research`
- [X] T002 [P] Verify baseline gates pass (`uv run pytest`, `uv run ruff check src/ tests/`, `uv run mypy src/`) before any edits

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-story shared types and partials. Must complete before any user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Add `FilterScopeAll`, `FilterScopeDocLevel`, `FilterScopeChapter` Pydantic models and the discriminated `FilterScope = Annotated[…, Field(discriminator="kind")]` alias in `src/writer/models/schemas.py`
- [X] T004 [P] Add `ChapterAssociationUpdate` schema (`chapter_ids: list[uuid.UUID]`) for retroactive replace endpoints in `src/writer/models/schemas.py`
- [X] T005 [P] Write failing unit tests for `parse_filter_scope(raw: str) -> FilterScope` — valid `all` / `doc-level` / `chapter:<uuid>`; malformed input raises a domain error — in `tests/unit/test_filter_scope.py`
- [X] T006 Implement `parse_filter_scope` helper module in `src/writer/services/filter_scope.py` to make T005 pass
- [X] T007 [P] Create reusable `src/writer/templates/partials/chapter_picker.html` partial: a `<details>` with a checkbox per chapter (form name `chapter_ids`), accepting context vars `chapters`, `selected_chapter_ids`, `form_id`; renders nothing when `chapters | length == 0`

**Checkpoint**: Foundational types + parser + reusable partial in place. User story implementation can now begin.

---

## Phase 3: User Story 1 — Source chapter tagging + filter (Priority: P1) 🎯 MVP

**Goal**: Sources can be tagged to chapters on add, retroactively re-tagged from the source list, and filtered by scope (all / doc-level / chapter). Untagged sources are document-level.

**Independent Test**: Quickstart steps 1–4 + 7 — create 3 chapters and 5 sources, tag two on add, retag one, filter by each mode, delete a chapter and confirm tagged sources survive.

### Tests for User Story 1 (TDD — write first, confirm fail, then implement)

- [X] T008 [P] [US1] Test `assign_source_to_chapter` (idempotent insert) in `tests/unit/test_source_service.py`
- [X] T009 [P] [US1] Test `assign_source_to_chapter` raises `ChapterDocumentMismatchError` on cross-document attempt in `tests/unit/test_source_service.py`
- [X] T010 [P] [US1] Test `unassign_source_from_chapter` (no-op when association absent) in `tests/unit/test_source_service.py`
- [X] T011 [P] [US1] Test `replace_source_chapter_associations` replaces full set, idempotent on identical input, validates cross-doc, in `tests/unit/test_source_service.py`
- [X] T012 [P] [US1] Test `list_sources_by_scope` for `scope=all` returns same set as `list_sources` in `tests/unit/test_source_service.py`
- [X] T013 [P] [US1] Test `list_sources_by_scope` for `scope=doc-level` returns only sources with zero associations in `tests/unit/test_source_service.py`
- [X] T014 [P] [US1] Test `list_sources_by_scope` for `scope=chapter:<uuid>` returns only sources tagged to that chapter (multi-tagged appears) in `tests/unit/test_source_service.py`
- [X] T015 [P] [US1] Test `list_sources_by_scope` with stale chapter UUID degrades to `all` and emits a WARNING log in `tests/unit/test_source_service.py`
- [X] T016 [P] [US1] Test `add_source` with non-empty `chapter_ids` creates source + associations atomically; with empty list stays document-level in `tests/unit/test_source_service.py`
- [X] T017 [P] [US1] Test `list_sources` populates `chapter_ids` on each `SourceResponse` in `tests/unit/test_source_service.py`

### Implementation for User Story 1

- [X] T018 [US1] Add `ChapterSource` ORM class with composite PK + `chapter_sources_source_idx` index in `src/writer/models/db.py`; add `"ChapterSource"` to `__all__`
- [X] T019 [US1] Create Alembic migration `migrations/versions/<timestamp>_add_chapter_sources.py` creating `chapter_sources` table with CASCADE FKs and the secondary index (use `uv run alembic revision -m "add_chapter_sources"` to scaffold)
- [X] T020 [US1] Ask user before running `uv run alembic upgrade head` (per CLAUDE.md infrastructure-command rule); verify table exists with `\d chapter_sources` in psql
- [X] T021 [US1] Extend `SourceCreate` schema with `chapter_ids: list[uuid.UUID] = []` in `src/writer/models/schemas.py`
- [X] T022 [US1] Extend `SourceResponse` schema with `chapter_ids: list[uuid.UUID] = []` in `src/writer/models/schemas.py`
- [X] T023 [US1] Add `ChapterDocumentMismatchError` exception class in `src/writer/services/source_service.py`
- [X] T024 [US1] Implement `assign_source_to_chapter(db, chapter_id, source_id)` (idempotent via `db.merge`, validates same-document) in `src/writer/services/source_service.py`
- [X] T025 [US1] Implement `unassign_source_from_chapter(db, chapter_id, source_id)` (no-op safe) in `src/writer/services/source_service.py`
- [X] T026 [US1] Implement `replace_source_chapter_associations(db, source_id, chapter_ids, *, document_id, user_id)` (single-tx replace; validates each chapter belongs to `document_id`) in `src/writer/services/source_service.py`
- [X] T027 [US1] Implement `list_sources_by_scope(db, document_id, user_id, scope: FilterScope) -> list[SourceResponse]` in `src/writer/services/source_service.py`; handles stale-chapter degradation with WARNING log
- [X] T028 [US1] Extend `add_source(db, data: SourceCreate, user_id)` to call `replace_source_chapter_associations` with `data.chapter_ids` in same transaction in `src/writer/services/source_service.py`
- [X] T029 [US1] Extend `add_source_pdf(db, document_id, title, file_bytes, user_id, chapter_ids: list[uuid.UUID] = ())` to persist chapter associations in `src/writer/services/source_service.py`
- [X] T030 [US1] Extend `list_sources` and `get_source` to populate `chapter_ids` on every `SourceResponse` (one batch SELECT from `chapter_sources` keyed by source_id set) in `src/writer/services/source_service.py`
- [X] T031 [US1] Run `uv run pytest tests/unit/test_source_service.py -v` and confirm all US1 service tests (T008–T017) now pass; fix any regressions
- [X] T032 [US1] Extend `POST /api/documents/{doc_id}/sources` in `src/writer/api/sources.py` to accept multi-value `chapter_ids` form field (`Annotated[list[uuid.UUID], Form()] = []`); thread into `SourceCreate` for note/url path and into new `add_source_pdf` parameter for PDF path; return 422 on cross-document chapter ID
- [X] T033 [US1] Add `PUT /api/documents/{doc_id}/sources/{source_id}/chapters` endpoint accepting `ChapterAssociationUpdate` JSON body in `src/writer/api/sources.py`; calls `replace_source_chapter_associations`; returns rendered `partials/sources.html` row on `HX-Request`
- [X] T034 [US1] Extend `GET /api/documents/{doc_id}/sources` in `src/writer/api/sources.py` to accept `scope: str = "all"` query param, parse via `parse_filter_scope`, and call `list_sources_by_scope`
- [X] T035 [US1] Add `POST` and `DELETE` single-association endpoints `/api/documents/{doc_id}/chapters/{chapter_id}/sources/{source_id}` in `src/writer/api/chapters.py` (mirror of existing snippet endpoints from spec-016)
- [X] T036 [US1] Update `src/writer/templates/partials/sources.html` to render chapter chips (one per `source.chapter_ids`, looking up names from a `chapter_id_to_title` map passed in context) and a tag-edit button that issues `hx-get` against the new edit endpoint
- [X] T037 [US1] Add `GET /api/documents/{doc_id}/sources/{source_id}/chapters/edit` endpoint returning `partials/chapter_picker.html` wrapped in a `<form hx-put="…/chapters">` for popover use, in `src/writer/api/sources.py`
- [X] T038 [US1] Add chapter-picker disclosure to all three add-source forms (note/url/pdf) in `src/writer/templates/document.html` by including `partials/chapter_picker.html` with `chapters=chapters`; renders nothing when `chapters | length == 0` (FR-009)
- [X] T039 [US1] Add filter `<select id="source-filter">` above the source list in `src/writer/templates/document.html` with options All / Document-level only / one per chapter; default `value` from `scope=chapter:<active_chapter_id>` when active else `scope=all`; `hx-get` on change to `/api/documents/{doc.id}/sources?scope=…` swapping `#source-list`
- [X] T040 [US1] Add empty-state messaging in `partials/sources.html` (or wrapper) when filter yields zero items, naming the active filter and offering a one-click "Show all" link that resets the filter (FR-022)
- [X] T041 [US1] Pass `chapters` and `chapter_id_to_title` map into `document.html` context — extend the document GET handler in `src/writer/api/documents.py` to fetch chapters and build the title map

**Checkpoint US1**: Sources can be tagged on add, retag from list, filtered three ways, and survive chapter deletion. Quickstart steps 1–4, 7, 8 pass for sources.

---

## Phase 4: User Story 2 — Snippet chapter tagging + filter (Priority: P2)

**Goal**: Snippets can be tagged to chapters on save (search-result "Add to Bank" and highlight-tooltip "Save to Scratchpad"), retroactively re-tagged from the snippet bank, and filtered by scope. Reuses spec-016's `chapter_snippets` table.

**Independent Test**: Quickstart step 6 — save snippets with and without chapter tags via both entry points, retag from the bank, filter the bank three ways.

### Tests for User Story 2 (TDD)

- [X] T042 [P] [US2] Test `replace_snippet_chapter_associations` replaces full set, idempotent, validates cross-doc, in `tests/unit/test_snippet_service.py`
- [X] T043 [P] [US2] Test `list_snippets_by_scope` for `scope=all` returns same set as `list_snippets` in `tests/unit/test_snippet_service.py`
- [X] T044 [P] [US2] Test `list_snippets_by_scope` for `scope=doc-level` returns only snippets with zero associations in `tests/unit/test_snippet_service.py`
- [X] T045 [P] [US2] Test `list_snippets_by_scope` for `scope=chapter:<uuid>` matches existing `list_snippets_by_chapter`, plus stale-uuid degradation, in `tests/unit/test_snippet_service.py`
- [X] T046 [P] [US2] Test `create_snippet` with non-empty `chapter_ids` creates associations atomically; with empty list stays document-level, in `tests/unit/test_snippet_service.py`
- [X] T047 [P] [US2] Test `list_snippets`, `list_snippets_by_chapter`, and `get_snippet_with_source_title` populate `chapter_ids` on each `SnippetResponse` in `tests/unit/test_snippet_service.py`

### Implementation for User Story 2

- [X] T048 [US2] Extend `SnippetCreate` with `chapter_ids: list[uuid.UUID] = []` in `src/writer/models/schemas.py`
- [X] T049 [US2] Extend `SnippetResponse` with `chapter_ids: list[uuid.UUID] = []` in `src/writer/models/schemas.py`
- [X] T050 [US2] Add `ChapterDocumentMismatchError` exception class (parallel to source-side) in `src/writer/services/snippet_service.py`
- [X] T051 [US2] Implement `replace_snippet_chapter_associations(db, snippet_id, chapter_ids, *, document_id, user_id)` in `src/writer/services/snippet_service.py`
- [X] T052 [US2] Implement `list_snippets_by_scope(db, document_id, user_id, scope: FilterScope)` in `src/writer/services/snippet_service.py`; degrade stale chapter UUIDs to `all` with WARNING log
- [X] T053 [US2] Extend `create_snippet` to accept `chapter_ids` from `SnippetCreate` and persist associations in same transaction in `src/writer/services/snippet_service.py`
- [X] T054 [US2] Extend `list_snippets`, `list_snippets_by_chapter`, and `get_snippet_with_source_title` to populate `chapter_ids` on every `SnippetResponse` (one batch SELECT from `chapter_snippets` keyed by snippet_id set) in `src/writer/services/snippet_service.py`
- [X] T055 [US2] Run `uv run pytest tests/unit/test_snippet_service.py -v` and confirm all US2 service tests (T042–T047) pass; fix any regressions in existing spec-016 tests
- [X] T056 [US2] Extend `POST /api/documents/{doc_id}/snippets` in `src/writer/api/snippets.py` — `SnippetCreate` already carries `chapter_ids` after T048; threading is automatic but ensure the rendered `partials/snippet_card.html` reflects new chips
- [X] T057 [US2] Add `PUT /api/documents/{doc_id}/snippets/{snippet_id}/chapters` endpoint accepting `ChapterAssociationUpdate` in `src/writer/api/snippets.py`; returns rendered snippet card on `HX-Request`
- [X] T058 [US2] Replace existing `chapter_id: uuid.UUID | None` query param with `scope: str = "all"` on `GET /api/documents/{doc_id}/snippets` in `src/writer/api/snippets.py`; preserve `chapter_id` as a backward-compat alias for one release that maps to `scope=chapter:<uuid>`
- [X] T059 [US2] Add `GET /api/documents/{doc_id}/snippets/{snippet_id}/chapters/edit` endpoint returning the chapter_picker form for popover use in `src/writer/api/snippets.py`
- [X] T060 [US2] Update `src/writer/templates/partials/snippet_card.html` to display chapter chips and a tag-edit affordance (mirror of T036)
- [X] T061 [US2] Wrap the "Add to Bank" button in `src/writer/templates/partials/search_results.html` in a `<details>` form containing the `chapter_picker` partial; submit via `hx-post` carrying `chapter_ids` as JSON-encoded array (use `hx-vals` with `js:` to read checkbox state)
- [X] T062 [US2] Add filter `<select id="snippet-filter">` above the snippet list in `src/writer/templates/partials/snippet_bank.html`, parallel to T039; default value derived from `active_chapter_id` (passed into snippet_bank context); `hx-get` to `/api/documents/{doc_id}/snippets?scope=…`
- [X] T063 [US2] Add `data-chapters` attribute on `#snippet-bank-container` in `src/writer/templates/document.html` carrying a JSON-encoded list of `{id, title}` for chapters, so the editor.js highlight-save flow can render its own chapter picker
- [X] T064 [US2] Update the highlight-save tooltip in `static/editor.js` to: (a) read chapters from `#snippet-bank-container[data-chapters]`, (b) when ≥1 chapter exists, render checkboxes inside the tooltip, (c) include `chapter_ids` array in the POST body
- [X] T065 [US2] Run `npm run build:dev` to rebuild `static/editor.bundle.js` after T064 (REQUIRED per CLAUDE.local.md after any edit to `static/editor.js`)

**Checkpoint US2**: Snippets can be tagged on save (search and highlight paths), retag from bank, filter three ways, survive chapter deletion. Quickstart step 6 + step 7 (snippet drift) pass.

---

## Phase 5: User Story 3 — Filter defaults to current chapter context (Priority: P3)

**Goal**: When the writer's caret is in a chapter, the source-list and snippet-bank filters default to that chapter. Manual override persists until the chapter context changes. No auto-tagging on add.

**Independent Test**: Quickstart step 5 — click into chapters, verify auto-default; manually override, verify persistence; switch chapters, verify override clears.

(No new service-layer code, so no new TDD tests. UI/template wiring only.)

- [X] T066 [US3] In `src/writer/api/documents.py` (or wherever `document.html` is rendered), pass `active_chapter_id` into both the source-list and snippet-bank context so each can derive its initial `scope` query parameter
- [X] T067 [US3] Update the `#source-list hx-get` URL in `src/writer/templates/document.html` (the `<ul id="source-list" hx-get="…" hx-trigger="load">`) to include `?scope=chapter:{{ active_chapter_id }}` when `active_chapter_id` is set, else `?scope=all`
- [X] T068 [US3] Update the snippet-bank `hx-get` in `src/writer/templates/document.html` (the `<div id="snippet-bank-container">`) to include the same conditional `?scope=…`
- [X] T069 [US3] Update the chapter-open trigger in `src/writer/templates/partials/chapter_card.html` (or `partials/toc.html`) to additionally re-fetch `#source-list` and `#snippet-list` with `scope=chapter:<chapter.id>`, using `hx-on::after-request` to call `htmx.ajax('GET', …)` against both targets — clears any prior manual override automatically (FR-020)
- [X] T070 [US3] Confirm `<select>` elements retain user-chosen value across HTMX swaps **within** the same chapter context — easiest path: have the GET endpoints render the `<select>` with the active scope value pre-selected, and rely on the swap target being the list itself (not the wrapper containing the select), so the select isn't replaced

**Checkpoint US3**: Auto-default filter follows chapter context. All three user stories fully functional. Quickstart step 5 passes.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T071 [P] Run `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/` on all touched files; ensure zero violations
- [X] T072 [P] Run `uv run mypy src/` and resolve any type errors introduced by new schemas, services, and endpoints (also fixed 4 pre-existing `import_deep_research` errors; mypy now reports zero errors)
- [X] T073 Run full `uv run pytest` and confirm zero regressions in pre-existing tests (201/201 pass)
- [ ] T074 Walk through `specs/017-chapter-scoped-research/quickstart.md` end-to-end (steps 1–9) against the running dev server; record any UX issues against the spec — **manual step for user**
- [X] T075 Verify backward-compat: `chapter_id` query parameter alias implemented on `GET /snippets` (T058); pre-existing snippets/sources have empty `chapter_ids` → document-level by default (no backfill)
- [X] T076 Confirm CLAUDE.md was updated by `/speckit.plan` (checked — CLAUDE.md already lists 017-chapter-scoped-research tech stack)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1. **BLOCKS** all user stories.
- **Phase 3 (US1)**: Depends on Phase 2. Independent of US2 and US3.
- **Phase 4 (US2)**: Depends on Phase 2. Independent of US1 and US3 (but reuses the chapter_picker partial from T007 and the parse_filter_scope helper from T006).
- **Phase 5 (US3)**: Depends on **both** US1 and US2 because it wires the auto-default filter into both panes simultaneously. (Could ship after just US1 to default sources only — but spec defines US3 as covering both panes.)
- **Phase 6 (Polish)**: Depends on US1, US2, US3 being complete (or whichever subset is shipped).

### User Story Dependencies

- **US1 (P1, MVP)**: Independent. Ships the source side end-to-end. **First and minimum shippable slice.**
- **US2 (P2)**: Independent of US1. Could ship before US1 if priorities flipped, but P1 priority means sources first.
- **US3 (P3)**: Cross-cutting refinement on top of US1+US2. Depends on both panes existing.

### Within Each User Story

- **TDD strict for service layer**: write tests, see them fail, implement to green. Tests for endpoints/templates are **not** written.
- Schemas → services → endpoints → templates within each phase.
- Migration (T019, T020) blocks all source-side service tests since they need the table.

### Parallel Opportunities

- **Setup**: T002 is [P] (read-only check).
- **Foundational**: T003, T004, T007 are [P] (different concerns in `schemas.py` and a new template). T005/T006 sequential (test → implement).
- **US1**: T008–T017 are all [P] tests in the same file but adding distinct test functions; can be staged as one TDD pass. T018, T021–T023 are independent file/section edits — can be parallelised before any service implementation begins. Service implementations T024–T030 should be sequential within a single agent (same file), but the unit-test pass T031 gates all subsequent endpoint/template work.
- **US2**: T042–T047 are all [P] tests. T048–T054 are mostly within `snippet_service.py`/`schemas.py` so sequential per file, then endpoints T056–T059 in `api/snippets.py` (sequential per file) plus templates T060–T063 [P] (different files).
- **US3**: T066–T070 are sequential in their dependence on context wiring; little parallelism here.
- **Polish**: T071, T072, T073 are [P] (independent gates). T074 is the manual quickstart, sequential.

---

## Parallel Example: User Story 1 TDD pass

Spawn the test-writing tasks together since they touch distinct test functions in the same file:

```bash
# Single agent writing tests/unit/test_source_service.py adds these new test functions in one pass:
- test_assign_source_to_chapter_idempotent       # T008
- test_assign_source_to_chapter_cross_doc_raises # T009
- test_unassign_source_from_chapter_noop         # T010
- test_replace_source_chapter_associations       # T011
- test_list_sources_by_scope_all                 # T012
- test_list_sources_by_scope_doc_level           # T013
- test_list_sources_by_scope_chapter             # T014
- test_list_sources_by_scope_stale_uuid          # T015
- test_add_source_with_chapter_ids               # T016
- test_list_sources_populates_chapter_ids        # T017
```

Confirm all fail (red), then implement T024–T030 to drive them green (T031).

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and validate** against quickstart steps 1–4, 7, 8.
3. Ship if useful — the source side alone delivers a navigable, filterable corpus.

### Incremental Delivery

1. MVP (US1) — sources gain chapter organisation.
2. Add US2 — snippets gain the same.
3. Add US3 — auto-default filter on both panes.
4. Polish gates last.

### Parallel Team Strategy

After Phase 2 completes:

- Developer A: US1 (sources end-to-end).
- Developer B: US2 (snippets end-to-end), starting independently.
- Developer C: deferred to US3 (depends on both A and B landing).

---

## Notes

- **TDD scope**: tests required for services in `src/writer/services/`. Tests **not** written for endpoints (`src/writer/api/*.py`) or templates (`src/writer/templates/**`) per Constitution II.
- **No remote APIs** (Constitution III): this feature is pure DB + UI; no external calls to mock.
- **Strong typing** (Constitution V): every new function signature uses Pydantic models, `uuid.UUID`, `list[uuid.UUID]`, or the `FilterScope` discriminated union — no plain dicts, no `Any`.
- **Logging** (Constitution IX): every new service function logs operation start + success/failure at INFO; every except logs at ERROR.
- **Infrastructure commands**: T020 (`alembic upgrade head`) requires user confirmation per CLAUDE.md.
- **JS rebuild**: T065 (`npm run build:dev`) is mandatory after T064 per CLAUDE.local.md.
- **Backward-compat**: T058 keeps the spec-016 `chapter_id` query param working for one release as a `scope=chapter:<uuid>` alias.
- Commit per logical group (e.g. each user story's checkpoint).
