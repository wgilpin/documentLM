# Tasks: Universal App Settings

**Input**: Design documents from `/specs/007-universal-settings/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅

**Tests**: TDD is MANDATORY for `settings_service.py` (service layer). Write failing tests FIRST.
Tests MUST NOT be written for API endpoints or frontend/template code.
Tests MUST NOT call remote APIs — mock all external dependencies.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project dependencies or tooling are required. All infrastructure already exists.

- [x] T001 Verify Alembic environment is configured and `uv run alembic upgrade head` runs cleanly before starting

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `UserSettings` ORM model, Pydantic schemas, service layer + TDD tests, and Alembic migration.
These are consumed by every user story — MUST be complete before any Phase 3+ work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### TDD: Write failing tests FIRST (confirm they fail before implementing)

- [x] T002 Write failing unit tests for `get_settings` (default values when no row exists) and `upsert_settings` (create + update) in `tests/unit/test_settings_service.py` — confirm all tests FAIL before proceeding to T005/T006

### ORM + Schema

- [x] T003 [P] Add `UserSettings` ORM model (id=1, display_name, language_code, ai_instructions, updated_at) to `src/writer/models/db.py` and update `__all__`
- [x] T004 [P] Add `UserSettingsUpdate` (writable, ai_instructions max_length=2000) and `UserSettingsResponse` (from_attributes=True) Pydantic schemas to `src/writer/models/schemas.py`

### Service layer (implement after T002 confirms tests fail)

- [x] T005 Implement `async def get_settings(db: AsyncSession) -> UserSettingsResponse` in `src/writer/services/settings_service.py` — fetches row id=1 or returns `UserSettingsResponse` defaults (depends on T003, T004)
- [x] T006 Implement `async def upsert_settings(db: AsyncSession, data: UserSettingsUpdate) -> UserSettingsResponse` in `src/writer/services/settings_service.py` — upsert id=1 row (depends on T003, T004)

### Migration

- [x] T007 Generate Alembic migration `add_user_settings` for the `user_settings` table in `migrations/versions/` and verify `uv run alembic upgrade head` succeeds (depends on T003)

### Verify

- [x] T008 Run `uv run pytest tests/unit/test_settings_service.py -v` and confirm all tests pass (depends on T005, T006)

**Checkpoint**: `UserSettings` service is fully tested and working. User story implementation can now begin.

---

## Phase 3: User Story 1 — Settings Modal Access (Priority: P1) 🎯 MVP

**Goal**: A gear icon appears left of the Delete button; clicking it opens a modal with name, language, and AI instructions fields; Save persists data, Cancel discards changes.

**Independent Test**: Click the ⚙ icon on any document page → modal opens → fill fields → Save → refresh page → reopen modal → fields pre-populated with saved values.

### Implementation

- [x] T009 [P] [US1] Create `src/writer/api/settings.py` with `GET /api/settings` (returns `UserSettingsResponse`) and `POST /api/settings` (upserts via `settings_service`, returns `UserSettingsResponse` + `HX-Trigger: settingsSaved` header)
- [x] T010 [US1] Register settings API router in `src/writer/main.py` (depends on T009)
- [x] T011 [US1] Modify `src/writer/api/documents.py` (or the document page view) to fetch `UserSettingsResponse` from `settings_service.get_settings` and pass it to the `document.html` Jinja2 template context as `user_settings` (depends on T005)
- [x] T012 [US1] Add settings gear icon button (`⚙`) immediately left of the Delete button in `src/writer/templates/document.html` — `onclick="document.getElementById('settings-dialog').showModal()"`
- [x] T013 [US1] Add `<dialog id="settings-dialog">` modal to `src/writer/templates/document.html` containing: `display_name` text input, `language_code` select with 11 locale options (en, en-GB, fr, de, es, it, pt, nl, ja, zh, ar), `ai_instructions` textarea (maxlength=2000), Save and Cancel buttons (depends on T012)
- [x] T014 [US1] Wire modal form to HTMX in `src/writer/templates/document.html`: `hx-post="/api/settings"` on form submit, `hx-target="#settings-response"`, and inline JS event listener on `htmx:afterRequest` to close dialog when `HX-Trigger: settingsSaved` is received (depends on T013)
- [x] T015 [US1] Pre-populate modal fields from `user_settings` template context in `src/writer/templates/document.html` (depends on T011, T013)

**Checkpoint**: Settings modal opens, all fields visible, save persists to DB, cancel discards, fields pre-populated on next open. Fully functional independently of AI wiring.

---

## Phase 4: User Story 2 — Universal AI Instructions (Priority: P1)

**Goal**: Saved AI instructions are automatically appended to the system prompt for every AI chat session — no per-session setup required.

**Independent Test**: Enter an instruction ("Always respond formally") in settings, save, send any chat message → AI response reflects the instruction style.

### Implementation

- [x] T016 [US2] Modify `src/writer/agents/chat_agent.py`: update `make_chat_agent` signature to accept `user_settings: UserSettingsResponse | None = None`; build an instruction suffix from `ai_instructions`, `display_name`, and `language_code`; append the suffix to `_INSTRUCTION` before creating the `Agent`
- [x] T017 [US2] Modify `src/writer/services/chat_service.py`: update `invoke_chat_agent` signature to accept `user_settings: UserSettingsResponse | None = None` and pass it to `make_chat_agent` (depends on T016)
- [x] T018 [US2] Modify `src/writer/services/chat_service.py`: update `process_chat` to call `await settings_service.get_settings(db)` and pass the result to `invoke_chat_agent` (depends on T017)
- [x] T019 [US2] Add `ai_instructions` live character counter (inline `<span>` + 3-line `oninput` handler on the textarea) to the modal in `src/writer/templates/document.html`

**Checkpoint**: AI instructions from settings appear in every new chat session. Character counter works in modal.

---

## Phase 5: User Stories 3 & 4 — Display Name & Language (Priority: P2)

**Goal**: Display name and language preference are also injected into the AI system prompt. The AI addresses the user by name and responds in the chosen language.

**Independent Test (US3)**: Set name to "Alice", save, send chat message → AI uses "Alice" in response or context.
**Independent Test (US4)**: Set language to "French", save, send chat message → AI responds in French.

*Note: The agent wiring for name and language was included in T016 (`make_chat_agent` suffix). These tasks verify and complete the end-to-end flow for each field.*

### Implementation

- [x] T020 [P] [US3] Verify `display_name` is included in the agent instruction suffix in `src/writer/agents/chat_agent.py` (e.g., "The user's name is {display_name}.") — add if missing from T016
- [x] T021 [P] [US4] Verify `language_code` is included in the agent instruction suffix in `src/writer/agents/chat_agent.py` (e.g., "Respond in {language_name} ({language_code}).") — add if missing from T016; confirm the 11 supported languages resolve to human-readable names via static dict in `src/writer/agents/chat_agent.py` or `src/writer/services/settings_service.py`

**Checkpoint**: All four user stories are fully functional and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T022 [P] Run `uv run ruff check --fix src/ tests/` and `uv run ruff format src/ tests/` — fix any violations
- [x] T023 [P] Run `uv run mypy src/` — fix any type errors introduced by new code
- [x] T024 Run `uv run pytest` — confirm all existing + new tests pass
- [x] T025 Follow quickstart.md end-to-end verification steps manually to confirm full feature works

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user story phases
- **Phase 3 (US1)**: Depends on Phase 2 completion
- **Phase 4 (US2)**: Depends on Phase 2 completion; integrates with Phase 3 UI (modal character counter)
- **Phase 5 (US3+US4)**: Depends on Phase 2 + Phase 4 (T016 must exist)
- **Phase 6 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on US2/US3/US4
- **US2 (P1)**: Can start after Phase 2 — T016 is the entry point
- **US3 + US4 (P2)**: Can start after T016 (agent wiring base) is merged — T020 and T021 are parallel

### Within Each User Story

- Service tests MUST fail before implementation begins (TDD)
- ORM model (T003) before migration (T007)
- Service (T005/T006) before API endpoint (T009)
- API endpoint (T009) before router registration (T010)
- Icon button (T012) before dialog (T013) before HTMX wiring (T014)

---

## Parallel Opportunities

### Phase 2 Parallel Set

```
T003 — Add UserSettings ORM model to db.py
T004 — Add Pydantic schemas to schemas.py
       (can both run after T002 confirms tests fail)
```

### Phase 3 Parallel Set

```
T009 — Create settings API router (api/settings.py)
T011 — Fetch settings in document view (api/documents.py or equivalent)
       (both can start in parallel after Phase 2 is complete)
```

### Phase 5 Parallel Set

```
T020 — Verify display_name suffix in chat_agent.py
T021 — Verify language_code suffix in chat_agent.py
       (both extend T016, different logical additions — can run in parallel)
```

---

## Implementation Strategy

### MVP (US1 + US2 — both P1)

1. Complete Phase 2: Foundational (TDD tests → ORM/schemas → service → migration)
2. Complete Phase 3: Settings modal (API + router + UI + HTMX)
3. Complete Phase 4: AI instructions wiring
4. **STOP and VALIDATE**: Test US1 + US2 independently via quickstart.md steps 3–6
5. Demo/deploy if ready

### Full Delivery

1. MVP above
2. Phase 5: Name + language wiring (small additions)
3. Phase 6: Polish

---

## Notes

- [P] tasks = different files, no blocking dependencies on each other
- T002 is the TDD gate — tests MUST fail before T005/T006 implementation begins
- T016 (`make_chat_agent` changes) is the single most critical agent-layer task; it covers name, language, and AI instructions in one go
- The `HX-Trigger: settingsSaved` header pattern follows the existing pattern used for other dialogs in the app
- No new Python packages are required — all dependencies already present
