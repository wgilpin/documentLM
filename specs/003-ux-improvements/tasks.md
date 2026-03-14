# Tasks: UX Improvements

**Input**: Design documents from `/specs/003-ux-improvements/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: TDD is MANDATORY for `chat_service.py` only (new backend service). No tests for templates, CSS, or API endpoint handlers. No remote API calls in tests — mock the `ChatAgent`.

**Organization**: Tasks grouped by user story to enable independent delivery of each UX improvement.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: User story label (US1–US6) from spec.md

---

## Phase 1: Setup

**Purpose**: Create the only new infrastructure artifact that US6 depends on.

- [X] T001 Create Alembic migration file for `chat_messages` table and `chatrole` enum in `migrations/versions/`; include index on `(document_id, created_at)`

---

## Phase 2: Foundational

No shared prerequisites block US1–US5. All user story phases can start after Phase 1 completes. US6 has its own prerequisite chain (enums → model → service) within Phase 8.

---

## Phase 3: User Story 1 – Global Command Modal (Priority: P1) 🎯 MVP

**Goal**: Replace the permanent "ASK AI" sidebar form with an on-demand `<dialog>` modal triggered by a floating button and `Ctrl+K`/`Cmd+K`.

**Independent Test**: Open document → press `Ctrl+K` → modal appears → submit instruction → modal closes and suggestion appears in suggestion area → Escape key closes modal without submitting.

### Implementation

- [X] T002 [P] [US1] Update `submit_comment` in `src/writer/api/suggestions.py` to skip selection-validity check when `selection_start == selection_end == 0` (global command with no text selection)
- [X] T003 [P] [US1] Add `<dialog id="command-modal">` element with HTMX form (targeting `#inline-suggestions`) to the end of the document body in `src/writer/templates/document.html`
- [X] T004 [US1] Add floating action button `<button id="cmd-fab">` and `<script>` block with `showModal()` call + `keydown` listener for `Ctrl+K`/`Cmd+K` to `src/writer/templates/document.html`
- [X] T005 [US1] Add CSS for `dialog`, `dialog::backdrop`, `#cmd-fab`, and modal form layout to `static/style.css`

**Checkpoint**: US1 fully functional — global AI commands work without the sidebar form.

---

## Phase 4: User Story 2 – Contextual AI Triggers (Priority: P2)

**Goal**: A floating menu appears near any text selection in the editor, offering "Add AI Instruction" which opens the command modal pre-loaded with the selection.

**Independent Test**: Select text in editor → floating menu appears near selection → click "Add AI Instruction" → command modal opens → submit → suggestion associated with selected passage appears.

### US2 Implementation

- [X] T006 [P] [US2] Add `<div id="floating-menu">` (hidden by default, contains "Add AI Instruction" button) to the editor pane in `src/writer/templates/document.html`
- [X] T007 [US2] Extend the existing textarea `mouseup` handler in `src/writer/templates/document.html` to: compute floating menu position using `textarea.getBoundingClientRect()`, set `style.top/left` on `#floating-menu`, and toggle its visibility based on selection length; wire the "Add AI Instruction" button to open `#command-modal`
- [X] T008 [US2] Add CSS for `#floating-menu` (position: fixed, z-index, background, shadow, button styles) to `static/style.css`

**Checkpoint**: US2 fully functional — text selection triggers contextual menu leading to command modal.

---

## Phase 5: User Story 3 – Inline Track Changes (Priority: P3)

**Goal**: AI suggestion cards appear as an absolute-positioned overlay inside the editor pane, not in the sidebar. The "AI Suggestions" sidebar section is removed.

**Independent Test**: Submit an AI instruction → suggestion card appears visually within the editor pane area (not in sidebar) → Accept replaces textarea content → Reject removes the card.

### US3 Implementation

- [X] T009 [P] [US3] Add `<div id="inline-suggestions">` overlay container (position: absolute, right edge of editor pane) to `.editor-pane` in `src/writer/templates/document.html`; remove the "AI Suggestions" `<div class="sidebar-section">` block entirely
- [X] T010 [US3] Update all HTMX targets in `src/writer/templates/document.html` that previously pointed to `#suggestion-panel` to point to `#inline-suggestions` (comment form, suggestion load trigger)
- [X] T011 [P] [US3] Update `src/writer/templates/partials/suggestion.html`: remove sidebar-specific inline styles; add `suggestion-card--inline` class to the root div; ensure accept target remains `#document-content` and reject target remains `#suggestion-{{ s.id }}`
- [X] T012 [US3] Add CSS for `.editor-pane` (`position: relative`), `#inline-suggestions` (absolute overlay, right edge), and `.suggestion-card--inline` styling to `static/style.css`

**Checkpoint**: US3 fully functional — suggestions appear inline within the editor pane; sidebar suggestion section gone.

---

## Phase 6: User Story 4 – Collapsed Source Entry (Priority: P4)

**Goal**: The permanent Note/URL/PDF tab form is hidden by default behind a single `<details>/<summary>` "Add Source" control.

**Independent Test**: Open document → source panel shows only "Add Source" button → click it → forms expand → add a source → form collapses back.

### US4 Implementation

- [X] T013 [US4] Replace the `.source-tabs` + three `.tab-panel` blocks in the Sources `sidebar-section` of `src/writer/templates/document.html` with a `<details><summary>Add Source</summary>...tab panels...</details>` wrapper; remove the `switchTab` JS function (no longer needed)
- [X] T014 [US4] Add CSS to style `<details>/<summary>` as the source entry toggle and ensure the expanded panel matches the existing form layout in `static/style.css`

**Checkpoint**: US4 fully functional — source entry collapsed by default, expands on demand.

---

## Phase 7: User Story 5 – De-emphasized Delete (Priority: P5)

**Goal**: Red delete buttons are hidden on source items by default; a subtle gray icon appears only on hover.

**Independent Test**: View source list → no delete buttons visible → hover over a source → gray trash icon appears → click → source removed → move pointer away → icon disappears.

### US5 Implementation

- [X] T015 [P] [US5] In `src/writer/templates/partials/sources.html`: replace `class="btn btn-danger btn-xs"` with `class="btn btn-ghost-danger btn-xs"` on the delete button; change the button text from `×` to a trash icon character (e.g., `🗑` or `✕`)
- [X] T016 [US5] Add CSS: `.btn-ghost-danger { visibility: hidden; background: transparent; color: #9ca3af; border: none; }` and `.source-item:hover .btn-ghost-danger { visibility: visible; }` to `static/style.css`

**Checkpoint**: US5 fully functional — delete buttons hidden until hover; no red persistent controls.

---

## Phase 8: User Story 6 – Global Meta-Chat Panel (Priority: P6)

**Goal**: A collapsible `<details>/<summary>` panel in the sidebar provides conversational AI brainstorming, backed by a new `ChatMessage` DB model and `ChatAgent`.

**Independent Test**: Open document → expand meta-chat panel → send message → AI responds within panel in chat format → collapse panel → re-expand → prior conversation visible → document cursor position unchanged.

### US6 Tests (TDD — write FIRST, confirm they FAIL, then implement)

- [X] T017 [P] [US6] Write failing unit tests for `chat_service` in `tests/unit/test_chat_service.py`: test `create_chat_message` (user role stored), test `list_chat_messages` (ordered by created_at), test `process_chat` (agent called with history, returns assistant message); mock `ChatAgent` — no remote calls

### US6 Implementation

- [X] T018 [P] [US6] Add `ChatRole` enum (`user`, `assistant`) to `src/writer/models/enums.py`
- [X] T019 [P] [US6] Add `ChatMessage` ORM model to `src/writer/models/db.py` (imports `ChatRole` from T018; fields: `id`, `document_id` FK, `role`, `content`, `created_at`)
- [X] T020 [P] [US6] Add `ChatMessageCreate` (content only) and `ChatMessageResponse` (all fields) Pydantic schemas to `src/writer/models/schemas.py` (imports `ChatRole` from T018)
- [X] T021 [US6] Implement `src/writer/services/chat_service.py`: `create_chat_message`, `list_chat_messages`, `process_chat` (invokes ChatAgent with full turn history as context, persists assistant reply); all `except` blocks log at ERROR level (depends on T017 failing, T019, T020)
- [X] T022 [P] [US6] Implement `src/writer/agents/chat_agent.py`: Google ADK `LlmAgent` with brainstorming system prompt (open-ended, no document-edit output format); name it `ChatAgent`
- [X] T023 [US6] Implement `src/writer/api/chat.py`: `GET /api/documents/{doc_id}/chat` (load history, return HTML partials or JSON) and `POST /api/documents/{doc_id}/chat` (create user turn + process agent reply, return two HTML partials via `beforeend` swap) (depends on T021, T022)
- [X] T024 [US6] Register `chat` router in `src/writer/main.py` via `app.include_router(chat.router)` (depends on T023)
- [X] T025 [P] [US6] Create `src/writer/templates/partials/chat_message.html` partial rendering a single `ChatMessageResponse` as a styled chat bubble with role label and content
- [X] T026 [US6] Add collapsible meta-chat `<details><summary>Meta Chat</summary>...</details>` section at the bottom of `.sidebar` in `src/writer/templates/document.html`: includes `<div id="chat-history">` loaded via `hx-trigger="load"` and a chat input form posting via `hx-swap="beforeend"` (depends on T024, T025)
- [X] T027 [US6] Add CSS for meta-chat panel, `.chat-turn`, `.chat-turn--user`, `.chat-turn--assistant`, chat input form to `static/style.css` (depends on T025, T026)

**Checkpoint**: US6 fully functional — meta-chat panel works end-to-end with persistent history.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T028 [P] Run `uv run ruff check --fix src/ tests/` and `uv run ruff format src/ tests/` on all modified files; fix any violations
- [X] T029 [P] Run `uv run mypy src/` and resolve all type errors in new/modified Python files
- [X] T030 Run `uv run pytest tests/unit/test_chat_service.py` — confirm all chat service tests pass
- [ ] T031 Manual walkthrough: verify all 6 UX improvements per acceptance scenarios in `specs/003-ux-improvements/spec.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: N/A — no shared prerequisites
- **Phase 3–7 (US1–US5)**: Depend only on Phase 1; can start immediately after T001
- **Phase 8 (US6)**: Depends on Phase 1 (migration file); internal dependency chain: T018 → {T019, T020} → T021 → T023 → T024 → T026 → T027
- **Phase 9 (Polish)**: Depends on all desired story phases completing

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories; shares `document.html` sequentially with US2–US4, US6
- **US2 (P2)**: No dependency on US1; extends the selection JS already present in US1
- **US3 (P3)**: No dependency on US1/US2; touches different areas of `document.html`
- **US4 (P4)**: No dependency on prior stories; wraps existing source form section
- **US5 (P5)**: No dependency on prior stories; touches only `sources.html` and `style.css`
- **US6 (P6)**: No dependency on US1–US5; only new backend code + new sidebar section

### Within US6: Internal Dependencies

```text
T017 (tests) ──┐
T018 (enum)  ──┤
               T019 (model) ──┐
               T020 (schema) ─┤── T021 (service) ──┐
T022 (agent)  ──────────────────────────────────────┤── T023 (endpoint) ── T024 (router)
T025 (partial) ─────────────────────────────────────────────────────────────────────────┤── T026 (template) ── T027 (CSS)
```

### Parallel Opportunities

- T002 (suggestions.py) and T003 (document.html) can run in parallel within Phase 3
- T009 (document.html) and T011 (suggestion.html) can run in parallel within Phase 5
- T015 (sources.html) and T016 (style.css) can be done sequentially in ~5 minutes
- Within Phase 8: T017, T018, T022, T025 can all start in parallel; then T019 + T020 in parallel after T018

---

## Parallel Example: User Story 6

```bash
# Start these four tasks in parallel (no inter-dependencies):
Task T017: "Write failing unit tests for chat_service in tests/unit/test_chat_service.py"
Task T018: "Add ChatRole enum to src/writer/models/enums.py"
Task T022: "Implement ChatAgent in src/writer/agents/chat_agent.py"
Task T025: "Create chat_message.html partial in src/writer/templates/partials/chat_message.html"

# After T018 completes, start these in parallel:
Task T019: "Add ChatMessage ORM model to src/writer/models/db.py"
Task T020: "Add ChatMessage schemas to src/writer/models/schemas.py"
```

---

## Implementation Strategy

### MVP First (US1 Only — ~4 tasks)

1. Complete Phase 1: T001
2. Complete Phase 3: T002 → T003 → T004 → T005
3. **STOP and VALIDATE**: Global command modal works end-to-end
4. Demo the highest-impact UX improvement independently

### Incremental Delivery

1. T001 (migration) → US1 (T002–T005) → Demo: command modal ✓
2. US2 (T006–T008) → Demo: contextual triggers ✓
3. US3 (T009–T012) → Demo: inline suggestions ✓
4. US4 (T013–T014) → Demo: collapsed sources ✓
5. US5 (T015–T016) → Demo: clean delete UX ✓
6. US6 (T017–T027) → Demo: meta-chat panel ✓
7. Polish (T028–T031)

### Notes

- US1–US5 are pure frontend (HTML/CSS/minimal JS) — each can be completed and validated in a single working session
- US6 is the only backend-heavy story — plan for TDD cycle and migration run
- `document.html` is touched by US1, US2, US3, US4, US6 — commit after each story's changes to avoid conflicts
- `static/style.css` receives additive-only changes — no existing rules are modified
- `static/style.css` should be edited at the END of each story phase (after HTML structure is confirmed)
