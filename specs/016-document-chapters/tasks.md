# Tasks: Chapter-Centric Documents

**Input**: Design documents from `/specs/016-document-chapters/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/chapters-api.md

**Tests**: TDD is MANDATORY for backend service code (business logic, data access, transformations).
Tests MUST NOT be written for frontend components or API endpoint handlers.
Tests MUST NOT call remote APIs (LLMs, external HTTP) — use mocks.
Write failing tests FIRST, confirm they fail, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project setup — existing project. This phase is empty.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data model, schemas, migration, and router registration that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 [P] Add Chapter and ChapterSnippet SQLAlchemy models to src/writer/models/db.py — Chapter has id, document_id, user_id, title (String 255, default "Untitled Chapter"), brief (Text, nullable), brief_visible (Boolean, default True), content (Text, default ""), position (Integer), created_at, updated_at. ChapterSnippet has composite PK (chapter_id, snippet_id) with CASCADE FKs. Add indexes: chapters_document_position_idx, chapters_document_user_idx, chapter_snippets_snippet_idx. Add UNIQUE constraint on (document_id, position).
- [x] T002 [P] Add chapter Pydantic schemas to src/writer/models/schemas.py — ChapterCreate (title: str = "Untitled Chapter", brief: str | None = None), ChapterUpdate (title: str | None, content: str | None, brief: str | None), ChapterResponse (id, document_id, title, brief, brief_visible, content, position, created_at, updated_at), ChapterPositionUpdate (position: int), ChapterBriefVisibilityUpdate (brief_visible: bool).
- [x] T003 Create Alembic migration in migrations/versions/xxxx_add_chapters.py — DDL: CREATE chapters table, CREATE chapter_snippets table, add indexes. DML data migration: for each existing document INSERT one chapter (title=doc.title, content=doc.content, position=0, user_id=doc.user_id), for each existing snippet INSERT one chapter_snippets row linking to that document's sole chapter.
- [x] T004 Register chapter API router in src/writer/main.py — import and include the chapters router with prefix /api/documents/{doc_id}/chapters.

**Checkpoint**: Foundation ready — data model exists, migration can run, router is wired up.

---

## Phase 3: User Story 1 — Create and Manage Chapters (Priority: P1) 🎯 MVP

**Goal**: Users can add, rename, reorder, and delete chapters within a document. A single-chapter document looks identical to the current standard document. Multiple chapters display in sequence with the active chapter showing a live TipTap editor.

**Independent Test**: Create a new document, add 3+ chapters with titles, reorder them, delete one, confirm single-chapter mode looks like a standard document.

### Tests for User Story 1 (backend services only — MANDATORY)

> Write tests FIRST and confirm they FAIL before any implementation.
> Tests go in `tests/unit/`. Do NOT write tests for API endpoints or frontend components.

- [x] T005 [P] [US1] Write failing tests for chapter create, get_by_id, and list_by_document in tests/unit/test_chapter_service.py — test create assigns next position, test get returns ChapterResponse, test list returns ordered by position. Use async test fixtures with test DB session.
- [x] T006 [P] [US1] Write failing tests for chapter update (title, content) and delete in tests/unit/test_chapter_service.py — test update persists changes and returns ChapterResponse, test delete removes chapter and recompacts sibling positions, test delete of last chapter leaves document with no chapters.
- [x] T007 [P] [US1] Write failing tests for chapter reorder and content cache rebuild in tests/unit/test_chapter_service.py — test reorder adjusts sibling positions correctly, test rebuild_document_content concatenates all chapters in order with "## {title}" headings and updates Document.content.

### Implementation for User Story 1

- [x] T008 [US1] Implement chapter CRUD functions in src/writer/services/chapter_service.py — create_chapter (assigns position = max+1, triggers content rebuild), get_chapter, list_chapters (ordered by position), update_chapter (triggers content rebuild on title/content change), delete_chapter (recompacts positions, triggers content rebuild). All functions take AsyncSession, return typed Pydantic responses. Include logging for all operations.
- [x] T009 [US1] Implement reorder_chapter and rebuild_document_content in src/writer/services/chapter_service.py — reorder_chapter accepts chapter_id and new position, adjusts sibling positions, triggers rebuild. rebuild_document_content queries all chapters ordered by position, concatenates as "## {title}\n\n{content}" separated by double newlines, writes to Document.content.
- [x] T010 [US1] Create chapter API endpoints in src/writer/api/chapters.py — POST (create), GET list, GET single, PUT (update), DELETE, PATCH position. Each endpoint returns HTML partials for HTMX requests (detect HX-Request header) or JSON for API requests. PUT endpoint is the primary content save target (replaces the document-level content save). DELETE triggers OOB TOC update.
- [x] T011 [US1] Modify document_service.create_document to also create one default chapter in src/writer/services/document_service.py — after creating the document, call chapter_service.create_chapter with the document's title and empty content. This ensures new documents always have at least one chapter.
- [x] T012 [P] [US1] Create chapter_card.html partial in src/writer/templates/partials/chapter_card.html — renders a non-active chapter block: chapter title (h2, editable on click), rendered markdown content (read-only HTML), click handler to activate chapter (hx-get to swap in editor partial). Include chapter position data attribute for reorder controls (up/down buttons). Include delete button with hx-delete and hx-confirm.
- [x] T013 [P] [US1] Create chapter_editor.html partial in src/writer/templates/partials/chapter_editor.html — renders the active chapter: title input (inline editable, hx-put on change), hidden textarea for TipTap sync (#chapter-content-{chapter_id}), TipTap mount div (#tiptap-mount), save trigger (hx-put on tiptap-changed event targeting chapter update endpoint). Include up/down reorder buttons and delete button.
- [x] T014 [US1] Modify document.html for chapter-based layout in src/writer/templates/document.html — replace the single editor area (middle pane) with: document title input (unchanged), chapter list container (iterates chapters, renders chapter_card.html for inactive and chapter_editor.html for active), "Add Chapter" button at bottom (hx-post to create chapter endpoint). First chapter is active by default. Remove the old #document-content textarea and its hx-put trigger. Keep the three-column layout (sources, editor/chapters, chat/snippets).
- [x] T015 [US1] Modify editor.js for per-chapter TipTap mounting in static/editor.js — refactor TipTap initialization to accept a chapter container element. Add activateChapter(chapterId) function: saves current chapter (if any), destroys current TipTap instance, creates new TipTap instance on new chapter's mount point with its content. Update content sync to target chapter-specific textarea and PUT endpoint. Update local history to be per-chapter (tiptap-history-{docId}-{chapterId}). Preserve toolbar, AI button, and suggestion decoration functionality.
- [x] T016 [US1] Add chapter layout and styling in static/style.css — chapter list container styles, chapter card styles (border, padding, hover state to indicate clickable), active chapter highlight, chapter title styling, reorder button styles (up/down arrows), Add Chapter button styling, chapter separator/divider between chapters.

**Checkpoint**: User Story 1 complete — documents support chapters. Single-chapter docs look standard. Multi-chapter docs display in sequence with active editor switching.

---

## Phase 4: User Story 2 — Chapter Brief / Description (Priority: P2)

**Goal**: Each chapter has an optional brief/description for planning. The brief can be toggled visible/hidden and is not part of the editor content.

**Independent Test**: Create a chapter, add a brief, toggle visibility, confirm brief does not appear in editor content.

### Tests for User Story 2 (backend services only — MANDATORY)

> Write tests FIRST and confirm they FAIL before any implementation.

- [x] T017 [US2] Write failing tests for brief update and visibility toggle in tests/unit/test_chapter_service.py — test update_chapter with brief field persists the brief, test brief_visible toggle changes the flag without affecting other fields, test that rebuild_document_content does NOT include brief text in the concatenated output.

### Implementation for User Story 2

- [x] T018 [US2] Ensure chapter_service.update_chapter handles brief field and add toggle_brief_visibility function in src/writer/services/chapter_service.py — toggle_brief_visibility accepts chapter_id and bool, updates brief_visible field. Verify rebuild_document_content excludes brief text.
- [x] T019 [US2] Add brief visibility toggle endpoint (PATCH .../brief-visibility) in src/writer/api/chapters.py — accepts ChapterBriefVisibilityUpdate, returns updated chapter card HTML (HTMX) or ChapterResponse (JSON).
- [x] T020 [US2] Add brief display and toggle UI to chapter_card.html and chapter_editor.html in src/writer/templates/partials/ — show brief text below title (collapsible), toggle button (eye icon or similar) to show/hide, brief textarea in editor partial for editing. Brief area has distinct styling (muted background, italic) to differentiate from content.
- [x] T021 [US2] Add brief styling in static/style.css — brief container (muted background, italic text, collapsible), toggle button, transition animation for show/hide.

**Checkpoint**: Chapters now support planning briefs that can be shown/hidden independently.

---

## Phase 5: User Story 3 — Attach Snippets to Chapters (Priority: P2)

**Goal**: Snippets can be associated with one or more chapters (many-to-many). The snippet panel filters by the active chapter. Snippets are created unassigned and assigned from the snippet bank.

**Independent Test**: Create two chapters, assign different snippets to each, navigate between chapters and confirm snippet panel shows chapter-specific snippets. Assign one snippet to both chapters and verify it appears in both.

### Tests for User Story 3 (backend services only — MANDATORY)

> Write tests FIRST and confirm they FAIL before any implementation.

- [x] T022 [P] [US3] Write failing tests for snippet-chapter assignment in tests/unit/test_snippet_service.py — test assign_snippet_to_chapter creates junction row, test assigning same snippet to second chapter succeeds (many-to-many), test unassign_snippet_from_chapter removes junction row but preserves snippet, test assigning is idempotent (no error on duplicate).
- [x] T023 [P] [US3] Write failing tests for chapter-filtered snippet listing in tests/unit/test_snippet_service.py — test list_snippets_by_chapter returns only snippets associated with that chapter, test list_snippets (no chapter filter) returns all document snippets, test snippet associated with two chapters appears in both filtered lists.

### Implementation for User Story 3

- [x] T024 [US3] Add snippet-chapter assignment functions to src/writer/services/snippet_service.py — assign_snippet_to_chapter (creates ChapterSnippet row, idempotent), unassign_snippet_from_chapter (deletes ChapterSnippet row), list_snippets_by_chapter (joins through ChapterSnippet, returns SnippetResponse list with source titles). Modify existing list_snippets to accept optional chapter_id filter parameter.
- [x] T025 [US3] Add snippet-chapter association endpoints in src/writer/api/chapters.py — POST .../chapters/{chapter_id}/snippets/{snippet_id} (assign, 201), DELETE .../chapters/{chapter_id}/snippets/{snippet_id} (unassign, 204).
- [x] T026 [US3] Modify snippet listing endpoint in src/writer/api/snippets.py — accept optional chapter_id query parameter on GET /documents/{doc_id}/snippets. When present, call list_snippets_by_chapter. When absent, call existing list_snippets (all document snippets).
- [x] T027 [US3] Modify snippet_bank.html in src/writer/templates/partials/snippet_bank.html — add chapter filter toggle (button/tab: "This Chapter" / "All Snippets"). When "This Chapter" is active, pass chapter_id to the snippet listing endpoint via hx-get query param. Update snippet bank to accept active_chapter_id context variable. Show "unassigned" indicator on snippets not linked to any chapter.
- [x] T028 [US3] Modify snippet_card.html in src/writer/templates/partials/snippet_card.html — add chapter assignment control: a dropdown or button to assign/unassign the snippet to the currently active chapter. Show chapter tags (small labels) indicating which chapters the snippet is associated with.

**Checkpoint**: Snippets can be assigned to chapters. The snippet panel filters by active chapter with an "all snippets" toggle.

---

## Phase 6: User Story 4 — Empty Chapters as Outline Placeholders (Priority: P3)

**Goal**: Documents with empty chapters (title + brief only) display cleanly as an outline. No backend changes needed — this is a template/CSS concern.

**Independent Test**: Create a document with 5 empty chapters (titles and briefs only), confirm clean outline rendering, then add content to one chapter and verify mixed display.

- [x] T029 [US4] Ensure chapter_card.html renders cleanly with empty content in src/writer/templates/partials/chapter_card.html — when content is empty, show a subtle "Click to start writing" placeholder instead of blank space. No broken layout or "empty" warnings.
- [x] T030 [US4] Add empty chapter styling in static/style.css — placeholder text styling (muted, italic), minimum height for empty chapter cards so outline looks balanced, visual indicator that the chapter is ready for content.

**Checkpoint**: Empty chapter outlines render cleanly. Mixed empty/content-filled documents display without visual issues.

---

## Phase 7: User Story 5 — Table of Contents Navigation (Priority: P3)

**Goal**: A clickable TOC appears when a document has 2+ chapters. Clicking a TOC entry scrolls to and activates that chapter. TOC is hidden for single-chapter documents.

**Independent Test**: Create a document with 5+ chapters, verify TOC appears, click entries to scroll/activate, then delete chapters down to 1 and verify TOC disappears.

- [x] T031 [P] [US5] Create toc.html partial in src/writer/templates/partials/toc.html — ordered list of chapter titles as clickable links. Each link targets the chapter's DOM element (anchor or data attribute). Conditional rendering: only shown when chapter count >= 2. TOC updates via HTMX OOB swap when chapters are added, deleted, reordered, or renamed.
- [x] T032 [US5] Integrate TOC into document.html in src/writer/templates/document.html — include toc.html partial above the chapter list container. Add hx-swap-oob="true" on TOC container so chapter CRUD endpoints can update it. Pass chapter list to the partial.
- [x] T033 [US5] Add smooth scroll and chapter activation for TOC clicks in static/editor.js — when a TOC link is clicked, scroll the chapter into view (smooth scroll) and activate it (trigger the chapter switching logic from T015). Prevent default link behaviour.
- [x] T034 [US5] Add TOC styling in static/style.css — TOC container (light background, border, sticky position optional), TOC item list, active chapter highlight in TOC, hover states, responsive layout.

**Checkpoint**: TOC appears for multi-chapter documents, navigates to chapters, hidden for single-chapter documents.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validation, regressions, and final integration checks.

- [x] T035 Run all existing tests and fix any regressions caused by model/service changes — cd /Users/will/projects/document-projects/documentLM && uv run pytest
- [x] T036 Run ruff check --fix, ruff format, and mypy on all changed files in src/ and tests/
- [x] T037 Rebuild editor bundle — remind user to run npm run build:dev after editor.js changes
- [x] T038 Manual end-to-end validation following specs/016-document-chapters/quickstart.md — create multi-chapter document, test chapter switching, brief toggle, snippet assignment, TOC navigation, single-chapter mode, and verify existing features (chat, sources, suggestions) still work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — can start immediately. BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Phase 2 completion. This is the MVP.
- **US2 (Phase 4)**: Depends on Phase 2. Can run in parallel with US1 (different files for templates/CSS), but service tests build on US1 chapter_service functions.
- **US3 (Phase 5)**: Depends on Phase 2. Service changes are in snippet_service (separate file from chapter_service), but template changes overlap with US1 document.html.
- **US4 (Phase 6)**: Depends on US1 (chapter_card.html must exist). Template/CSS only.
- **US5 (Phase 7)**: Depends on US1 (chapter list and document.html must exist). New partial + minor JS.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### Recommended Execution Order

```text
Phase 2 (Foundation) → Phase 3 (US1 MVP) → Phase 4 (US2) + Phase 5 (US3) → Phase 6 (US4) + Phase 7 (US5) → Phase 8 (Polish)
```

### Within Each User Story

- Service-layer tests MUST be written and FAIL before implementation (TDD — mandatory)
- Tests for API endpoints and frontend components MUST NOT be written
- Models before services
- Services before endpoints
- Endpoints before templates
- Templates before JS/CSS

### Parallel Opportunities

- **Phase 2**: T001 and T002 can run in parallel (models and schemas are separate files)
- **Phase 3**: T005, T006, T007 can run in parallel (all test files). T012 and T013 can run in parallel (separate template partials)
- **Phase 5**: T022 and T023 can run in parallel (separate test functions)
- **Phase 7**: T031 can run in parallel with other template tasks (new file)
- **Cross-story**: Once Phase 2 completes, US2 backend (T017-T018) can run in parallel with US1 backend (T005-T009) since they touch separate test blocks and the service file grows incrementally

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (write failing tests first):
Task: T005 "Unit tests for chapter create/get/list in tests/unit/test_chapter_service.py"
Task: T006 "Unit tests for chapter update/delete in tests/unit/test_chapter_service.py"
Task: T007 "Unit tests for chapter reorder/content rebuild in tests/unit/test_chapter_service.py"

# After tests written, implement service (sequential — same file):
Task: T008 "Chapter CRUD in src/writer/services/chapter_service.py"
Task: T009 "Reorder + content rebuild in src/writer/services/chapter_service.py"

# Then launch template partials in parallel:
Task: T012 "chapter_card.html in src/writer/templates/partials/chapter_card.html"
Task: T013 "chapter_editor.html in src/writer/templates/partials/chapter_editor.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (models, schemas, migration, router)
2. Complete Phase 3: User Story 1 (chapter CRUD, templates, editor.js)
3. **STOP and VALIDATE**: Create multi-chapter document, verify switching, verify single-chapter mode
4. Deploy/demo if ready

### Incremental Delivery

1. Phase 2 → Foundation ready
2. Phase 3 (US1) → Chapter management works → Demo (MVP!)
3. Phase 4 (US2) → Briefs work → Demo
4. Phase 5 (US3) → Snippet assignment works → Demo
5. Phase 6 + 7 (US4 + US5) → Empty chapters + TOC → Demo
6. Phase 8 → Polish and validate

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Always run `npm run build:dev` after changes to static/editor.js**
- **Always prefix uv commands with `cd /Users/will/projects/document-projects/documentLM &&`**
