# Tasks: Editor Undo/Redo

**Input**: Design documents from `/specs/006-editor-undo-redo/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: TDD is MANDATORY for `undo_buffer_size` config validation (backend service logic).
No tests for frontend components or API endpoint handlers.
No remote API calls in tests.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend config field and template wiring. Must complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 Write failing unit tests for `undo_buffer_size` config validation in `tests/unit/test_config.py` — cover valid value, default (1000), zero fallback with warning log, negative fallback, non-numeric fallback. **Confirm tests FAIL before T002.**
- [x] T002 Add `undo_buffer_size: int = 1000` field and `validate_buffer_size` `field_validator` (fallback + WARNING log on invalid input) to `src/writer/core/config.py` — makes T001 tests pass
- [x] T003 [P] Add `"undo_buffer_size": settings.undo_buffer_size` to both `TemplateResponse` calls that render `document.html` in `src/writer/main.py` (routes `/documents/new` and `/documents/{doc_id}`)
- [x] T004 [P] Add `UNDO_BUFFER_SIZE=1000` entry to `.env.example`

**Checkpoint**: Run `uv run pytest tests/unit/test_config.py` — all config tests pass. Foundation ready.

---

## Phase 3: User Story 1 — Undo Last Keystroke (Priority: P1) 🎯 MVP

**Goal**: Per-keystroke undo via Ctrl+Z, respecting the configured buffer depth.

**Independent Test**: Open the editor, type 10 characters, press Ctrl+Z 10 times — each press removes exactly one character in reverse order. On the 11th press nothing changes and the keyboard shortcut has no effect (or buffer limit is reached).

- [x] T005 [US1] In `src/writer/templates/document.html`: render `const UNDO_BUFFER_SIZE = {{ undo_buffer_size }};` into the `<script>` block, then configure `StarterKit.configure({ history: { depth: UNDO_BUFFER_SIZE, newGroupDelay: 0 } })` in the TipTap editor initialisation (replacing any existing `history:` option or adding it if absent)

**Checkpoint**: Ctrl+Z undoes one character at a time. Ctrl+Y re-applies (free from TipTap). US1 complete — deliverable without toolbar.

---

## Phase 4: User Story 2 — Undo AI-Generated Change (Priority: P1)

**Goal**: A single Ctrl+Z reverses the entire AI-applied document change atomically.

**Independent Test**: Trigger an AI edit via the chat panel. Press Ctrl+Z once — the document returns to its exact pre-AI state in one step. (The tooltip scenario from US2 S3 requires the toolbar from Phase 5 — verify it there.)

- [x] T006 [US2] In `src/writer/templates/document.html`, inside the `MutationObserver` callback that handles the OOB textarea swap: replace `editor.commands.setContent(parsed)` with a single ProseMirror transaction — `const tr = editor.state.tr; const newDoc = editor.schema.nodeFromJSON(parsed); tr.replaceWith(0, editor.state.doc.content.size, newDoc.content); tr.setMeta('ai-change', true); editor.view.dispatch(tr);`

**Checkpoint**: AI edits land as a single undo entry. Ctrl+Z once reverses the whole AI change. Core US2 complete. Tooltip (US2 S3) verified after Phase 5.

---

## Phase 5: User Story 4 — Toolbar Always Visible (Priority: P2) + User Story 3 — Redo (Priority: P2)

**Goal**: Persistent toolbar above the editor with Undo and Redo buttons that reflect availability. Redo button re-applies undone changes.

**Independent Test (US4)**: Load the editor with no changes — both buttons are disabled. Type one character — Undo enables. Press Ctrl+Z — Undo disables, Redo enables. Type a new character — Redo disables.

**Independent Test (US3)**: Undo a keystroke, then click Redo — the character is restored. Undo an AI change, then click Redo — the full AI change is re-applied.

- [x] T007 [US2] In `src/writer/templates/document.html`, declare `let lastChangeType = null;` at module scope (no DOM dependency — just the variable)
- [x] T008 [P] [US4] Add toolbar HTML immediately above `#tiptap-mount` in `src/writer/templates/document.html`: `<div class="editor-toolbar"><button id="undo-btn" class="toolbar-btn" disabled title="Undo" aria-label="Undo">&#8630; Undo</button><button id="redo-btn" class="toolbar-btn" disabled title="Redo" aria-label="Redo">Redo &#8631;</button></div>`
- [x] T009 [P] [US4] Add `.editor-toolbar`, `.toolbar-btn`, `.toolbar-btn:hover:not(:disabled)`, and `.toolbar-btn:disabled` CSS rules to `static/style.css` (see plan.md Phase 1 §7 for style values)
- [x] T010 [US2] [US3] [US4] In `src/writer/templates/document.html`, after editor initialisation: add `editor.on('transaction', ...)` handler that (a) sets `lastChangeType` to `'ai-change'` when `transaction.getMeta('ai-change')` is truthy, else `'keystroke'` when `transaction.docChanged`, (b) calls `editor.can().undo()` / `editor.can().redo()` to set `undoBtn.disabled` / `redoBtn.disabled`, and (c) sets `undoBtn.title` to `'Undo AI change'` or `'Undo'` based on `lastChangeType`; then attach `click` event listeners on `#undo-btn` → `editor.chain().focus().undo().run()` and `#redo-btn` → `editor.chain().focus().redo().run()`. Depends on T007 (variable) and T008 (buttons in DOM).

**Checkpoint**: Toolbar buttons visible and reactive. Redo works via button and Ctrl+Y. Hover over Undo after an AI edit — tooltip reads "Undo AI change". All US2, US3, US4 acceptance scenarios complete.

---

## Phase 6: Polish & Validation

**Purpose**: Quality gates and end-to-end verification.

- [x] T011 [P] Run `uv run pytest` — confirm all tests pass (especially `tests/unit/test_config.py`)
- [x] T012 [P] Run `uv run ruff check --fix src/ tests/` and `uv run ruff format src/ tests/` — zero violations
- [x] T013 [P] Run `uv run mypy src/` — zero errors (verify `undo_buffer_size` field and `main.py` template context are correctly typed)
- [ ] T014 Perform manual walkthrough per `specs/006-editor-undo-redo/quickstart.md` — verify all 7 verification steps pass, plus: (a) undo a keystroke then type a new character and confirm the Redo button disables (FR-006); (b) reload the page and confirm both Undo and Redo are disabled (FR-012)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 (Phase 3)**: Depends on Phase 2 (T003 must pass `undo_buffer_size` to template)
- **US2 (Phase 4)**: Depends on Phase 3 (history must be active for AI transaction to land in it)
- **US3 + US4 (Phase 5)**: Depends on Phase 3 (TipTap editor must be initialised); T010 depends on T008 (buttons must exist in DOM)
- **Polish (Phase 6)**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: Start after Phase 2 — no dependency on other stories
- **US2 (P1)**: Start after US1 (Phase 3) — AI change entry requires history to be active
- **US3 (P2)**: Start alongside US4 (Phase 5) — redo button wired in same T010 task
- **US4 (P2)**: Start after US1 (Phase 3) — toolbar JS references `editor` object

### Within Each Phase

- T001 (tests) must FAIL before T002 (implementation)
- T003 and T004 are parallel (different files)
- T007, T008, T009 can all start after Phase 4 — T007 and T008 are in the same file but non-overlapping (variable declaration vs HTML); T009 is a different file
- T010 depends on T007 (variable) and T008 (button DOM elements)

### Parallel Opportunities

- T003 + T004 can run in parallel (different files)
- T008 + T009 can run in parallel (different files)
- T011 + T012 + T013 can run in parallel in Phase 6

---

## Parallel Example: Phase 5

```bash
# Launch T008 and T009 together (different files):
Task: "T008 — Add toolbar HTML to src/writer/templates/document.html"
Task: "T009 — Add toolbar CSS to static/style.css"

# Then T010 after T008:
Task: "T010 — Wire button handlers + onTransaction listener in document.html"
```

---

## Implementation Strategy

### MVP (User Story 1 Only — Ctrl+Z works)

1. Complete Phase 2: Foundational (T001–T004)
2. Complete Phase 3: US1 — T005
3. **STOP and VALIDATE**: Ctrl+Z undoes keystrokes per spec
4. Keyboard undo fully functional — deliverable without toolbar

### Incremental Delivery

1. Phase 2 + Phase 3 → Ctrl+Z/Ctrl+Y work (MVP)
2. Phase 4 → AI changes become undoable
3. Phase 5 → Toolbar visible with reactive buttons
4. Phase 6 → Quality gates passed

### Parallel Team Strategy

With two developers after Phase 2:

- Developer A: Phase 3 (US1) → Phase 4 (US2)
- Developer B: Phase 5 T008 + T009 (markup and CSS, no JS dependency)
- Merge: Developer B completes T010 after Developer A finishes T005 (editor init exists)

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete prior tasks
- `[Story]` label maps task to specific user story for traceability
- TDD applies to `test_config.py` only — no frontend or endpoint tests
- Commit after each phase checkpoint
- Ctrl+Z and Ctrl+Y keyboard shortcuts are provided automatically by TipTap once `history` is configured — no separate keyboard listener needed
