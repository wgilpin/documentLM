# Tasks: Chat Session Management

**Input**: Design documents from `/specs/010-chat-sessions/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: TDD is MANDATORY for backend service code (business logic, data access, transformations).
Tests MUST NOT be written for frontend components or API endpoint handlers.
Tests MUST NOT call remote APIs (LLMs, external HTTP) — use mocks.
Write failing tests FIRST, confirm they fail, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in every description

---

## Phase 1: Setup

**Purpose**: No new project or tooling setup required — existing structure is used unchanged.

Skipped — project infrastructure already in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New database table, ORM models, enum, and Pydantic schemas that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 Add `SessionStatus` enum (`active`, `archived`) to `src/writer/models/enums.py`
- [X] T002 [P] Write Alembic migration `migrations/versions/XXXX_add_chat_sessions.py`: create `chat_sessions` table, backfill existing `chat_messages` rows into per-`(user_id, document_id)` default sessions, add `session_id` NOT NULL FK column to `chat_messages`, add partial unique index on `chat_sessions(user_id, document_id) WHERE status = 'active'`, add index `ix_chat_messages_session_created` on `chat_messages(session_id, created_at)` — see data-model.md for full migration steps
- [X] T003 [P] Add `ChatSession` ORM model and `session_id` mapped column to `ChatMessage` in `src/writer/models/db.py` — see data-model.md for field definitions and relationships
- [X] T004 Add `ChatSessionResponse` Pydantic schema with computed `label` field; add `session_id: uuid.UUID` field to `ChatMessageResponse` in `src/writer/models/schemas.py` (depends on T003)

**Checkpoint**: Run `uv run alembic upgrade head` and verify `chat_sessions` table exists and all existing `chat_messages` rows have a non-null `session_id`

---

## Phase 3: User Story 1 — Start a New Chat (Priority: P1) 🎯 MVP

**Goal**: Users can click "New Chat" to start a fresh session. Prior session is archived. New session has empty message history but inherits document context.

**Independent Test**: Click "New Chat" on a document with existing messages → chat area clears → old session appears in dropdown → new message has no knowledge of prior conversation.

### Tests for User Story 1 (service layer — MANDATORY, write and confirm failing FIRST)

- [X] T005 [P] [US1] Write failing unit tests for `get_or_create_active_session` (creates session when none exists; returns existing active session when one exists) and `session_has_messages` (returns True/False correctly) in `tests/unit/test_chat_session_service.py`
- [X] T006 [P] [US1] Write failing integration tests for `create_new_session`: archives current session when it has messages; returns None when current session is empty; creates new active session; only one active session exists after creation — in `tests/integration/test_chat_sessions.py`

### Implementation for User Story 1

- [X] T007 [US1] Create `src/writer/services/chat_session_service.py` with three functions: `get_or_create_active_session(db, user_id, document_id) -> ChatSession`, `create_new_session(db, user_id, document_id) -> ChatSession | None`, `session_has_messages(db, session_id) -> bool` — all functions must pass T005/T006 tests
- [X] T008 [US1] Update `src/writer/services/chat_service.py`: modify `create_chat_message` call sites to include `session_id`; modify `list_chat_messages` (or its call site) to filter by `session_id` instead of `document_id`
- [X] T009 [US1] Update `GET /api/documents/{doc_id}/chat` in `src/writer/api/chat.py` to call `get_or_create_active_session` and filter message history by `session.id`
- [X] T010 [US1] Update `POST /api/documents/{doc_id}/chat`, `POST /api/documents/{doc_id}/chat/find-sources`, and `POST /api/documents/{doc_id}/chat/suggest-outline` in `src/writer/api/chat.py` to retrieve the active session via `get_or_create_active_session` and pass `session_id` when saving messages — all three endpoints call `create_chat_message` which requires `session_id` NOT NULL after migration
- [X] T011 [US1] Update `GET /api/documents/{doc_id}/chat/stream` in `src/writer/api/chat.py` to call `get_or_create_active_session` before seeding; guard prevents re-seeding on already-seeded sessions
- [X] T012 [US1] Add `POST /api/documents/{doc_id}/chat/sessions` endpoint to `src/writer/api/chat.py`: calls `create_new_session`; returns HTMX response clearing `#chat-history` with OOB swap updating `#chat-session-dropdown`; returns 200 (no-op) if current session has no messages
- [X] T013 [US1] Create `src/writer/templates/partials/chat_session_dropdown.html`: renders a `<select id="chat-session-dropdown">` with a single `<option>` for "Current Chat" (active session); HTMX attributes for activate trigger wired up (ready for US2 to populate with archived sessions)
- [X] T014 [US1] Update `src/writer/templates/document.html` chat panel: add `<button id="chat-new-btn">` with `hx-post` to sessions endpoint; add `{% include "partials/chat_session_dropdown.html" %}` above chat history; load dropdown via `hx-get` on page load

**Checkpoint**: US1 fully functional — "New Chat" clears history, prior session preserved. Run `uv run pytest tests/unit/test_chat_session_service.py tests/integration/test_chat_sessions.py -v`

---

## Phase 4: User Story 2 — Access Archived Chats via Dropdown (Priority: P2)

**Goal**: Users can open the session dropdown and select a prior session to view its full message history. Selecting and messaging reactivates that session.

**Independent Test**: Start two new chats on a document → open dropdown → select the first session → its messages appear → send a message → assistant has context of that session's history, not the other.

### Tests for User Story 2 (service layer — MANDATORY, write and confirm failing FIRST)

- [X] T015 [P] [US2] Write failing integration tests for `list_sessions` (ordered most-recent first; labels computed correctly; "Current Chat" for active session) in `tests/integration/test_chat_sessions.py` — `list_sessions` queries the DB so belongs in integration tests alongside T016
- [X] T016 [P] [US2] Write failing integration tests for `activate_session`: archives previous active session; sets target to active; raises on invalid session_id or wrong user_id; get_session_messages returns correct messages — in `tests/integration/test_chat_sessions.py`

### Implementation for User Story 2

- [X] T017 [US2] Add three functions to `src/writer/services/chat_session_service.py`: `list_sessions(db, user_id, document_id) -> list[ChatSessionResponse]`, `activate_session(db, user_id, session_id) -> ChatSession`, `get_session_messages(db, session_id, user_id) -> list[ChatMessageResponse]` — all pass T015/T016 tests
- [X] T018 [US2] Add `GET /api/documents/{doc_id}/chat/sessions` endpoint to `src/writer/api/chat.py`: calls `list_sessions`; returns HTML partial (`chat_session_dropdown.html`) for HTMX or JSON list for non-HTMX; used by dropdown `hx-get` on page load
- [X] T019 [US2] Add `POST /api/documents/{doc_id}/chat/sessions/activate` endpoint to `src/writer/api/chat.py`: accepts `session_id: uuid.UUID` as a form/body parameter; calls `activate_session`; returns HTMX with message history HTML for `#chat-history` and OOB updated dropdown; returns 409 if session already active
- [X] T020 [US2] Update `src/writer/templates/partials/chat_session_dropdown.html` to render all sessions as `<option value="{{ s.id }}">` elements with correct labels ("Current Chat" / "Chat — MMM D, YYYY h:mm A"); wire `hx-post="/api/documents/{{ doc_id }}/chat/sessions/activate"` + `hx-vals="js:{session_id: this.value}"` on the `<select>` change trigger — session_id sent as body param (no path-param URL construction needed)
- [X] T021 [US2] Update `src/writer/templates/document.html` dropdown element to load full session list via `hx-get="/api/documents/{{ doc.id }}/chat/sessions"` on page load trigger

**Checkpoint**: US2 fully functional — dropdown shows all sessions, selecting an archived session loads its history. Run `uv run pytest tests/unit/test_chat_session_service.py tests/integration/test_chat_sessions.py -v`

---

## Phase 5: User Story 3 — Session Persistence Across Page Loads (Priority: P3)

**Goal**: All sessions survive a page reload; the most recent active session is shown by default on reload.

**Independent Test**: Create 2 sessions → reload page → dropdown still shows both sessions → active session messages still displayed.

### Tests for User Story 3 (integration — MANDATORY, write and confirm failing FIRST)

- [X] T022 [US3] Write failing integration tests in `tests/integration/test_chat_sessions.py` verifying: sessions and messages persist after closing and reopening db connection; `get_or_create_active_session` returns the same active session on second call; `list_sessions` returns all archived sessions after reconnect

No additional implementation tasks — persistence is provided by DB storage implemented in Phase 2/US1. These tests confirm the invariant holds end-to-end.

**Checkpoint**: All three user stories independently validated. Run full test suite: `uv run pytest`

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 [P] Run `uv run ruff check --fix src/ tests/` and `uv run ruff format src/ tests/` on all changed files; fix any violations
- [X] T024 [P] Run `uv run mypy src/` and fix any type errors in new/modified files (`enums.py`, `db.py`, `schemas.py`, `chat_session_service.py`, `chat_service.py`, `chat.py`)
- [X] T025 Run `uv run pytest` (full suite) and confirm all tests pass — fix any regressions in existing chat tests caused by session_id requirement on ChatMessage

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately; BLOCKS all user story phases
- **US1 (Phase 3)**: Depends on Phase 2 completion
- **US2 (Phase 4)**: Depends on Phase 3 completion (extends `chat_session_service.py` and same API file)
- **US3 (Phase 5)**: Depends on Phase 3 completion (tests the persistence guarantee from Phase 2+US1)
- **Polish (Phase 6)**: Depends on all user story phases

### Within Phase 2

- T001 first (enum needed by migration and ORM)
- T002 and T003 can run in parallel (different files: migration vs `db.py`)
- T004 depends on T003

### Within Each User Story Phase

- Tests (T005/T006, T015/T016, T022) written and confirmed failing BEFORE implementation
- T007 depends on T005/T006 (implement to make tests pass)
- T008 depends on T007 (service must exist before updating call sites)
- T009–T012 depend on T008 (API updates depend on updated service)
- T013–T014 depend on T012 (templates reference new endpoint)

### Parallel Opportunities

Within Phase 2: T002 ∥ T003 (different files)

Within Phase 3 tests: T005 ∥ T006 (different files)

Within Phase 4 tests: T015 ∥ T016 (different files)

---

## Parallel Example: User Story 1

```bash
# Run these two test tasks in parallel (different files):
Task T005: "Write failing unit tests in tests/unit/test_chat_session_service.py"
Task T006: "Write failing integration tests in tests/integration/test_chat_sessions.py"

# Then implement sequentially:
Task T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (run migration, implement ORM + schemas)
2. Complete Phase 3: User Story 1 (new chat button works end-to-end)
3. **STOP and VALIDATE**: Manually test "New Chat" flow per quickstart.md
4. Proceed to US2 if MVP is accepted

### Incremental Delivery

1. Phase 2 complete → DB schema ready, migration passes
2. Phase 3 complete → "New Chat" works; prior session preserved in DB; dropdown shows "Current Chat" only
3. Phase 4 complete → Dropdown lists all sessions; archived sessions selectable and reactivatable
4. Phase 5 complete → Persistence confirmed by tests
5. Phase 6 complete → Clean lint, types, full test suite green

### Single Developer Sequence

```text
T001 → (T002 ∥ T003) → T004 →
(T005 ∥ T006) → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 →
(T015 ∥ T016) → T017 → T018 → T019 → T020 → T021 →
T022 →
(T023 ∥ T024) → T025
```

---

## Notes

- [P] tasks = different files, no unresolved dependencies on each other
- [Story] label maps task to specific user story for traceability
- Each phase produces an independently testable increment
- Confirm tests FAIL before implementing (TDD — mandatory for service layer)
- Commit after each checkpoint
- Existing `test_chat_service.py` tests may need updating in T025 if they construct `ChatMessage` without `session_id`
