# Tasks: Multi-User Access with Invite Codes and Document Privacy

**Input**: Design documents from `/specs/009-multi-user-invite/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅

**Tests**: TDD is MANDATORY for backend service code. Write failing tests FIRST, confirm they fail, then implement. Tests MUST NOT be written for API endpoint handlers or frontend templates. Tests MUST NOT call remote APIs — mock all external dependencies.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no inter-task dependency)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies and configuration before any schema or code changes.

- [ ] T001 Add `passlib[bcrypt]` dependency by running `uv add "passlib[bcrypt]"` (updates pyproject.toml and uv.lock)
- [ ] T002 [P] Add `SECRET_KEY: str` field to `Settings` class in `src/writer/core/config.py` (default empty string; document that it must be set in `.env`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schema and infrastructure changes that MUST be complete before any user story can be implemented. No user story work can begin until this phase is done.

- [ ] T003 [P] Add `User` and `InviteCode` ORM models to `src/writer/models/db.py`; `User.email` MUST have `unique=True` in the column definition; add `user_id UUID NOT NULL FK→users` to `Document`, `Source`, `ChatMessage`; add `is_private BOOLEAN NOT NULL DEFAULT FALSE` to `Document`; replace `UserSettings.id INTEGER` PK with `user_id UUID PK FK→users`
- [ ] T004 [P] Add `UserResponse`, `RegisterRequest`, `LoginRequest`, `InviteCodeResponse` Pydantic v2 schemas to `src/writer/models/schemas.py`; add `is_private: bool` field to `DocumentResponse` and `DocumentSummary`
- [ ] T005 Create Alembic migration in `migrations/versions/` that: (1) DELETEs all rows from `chat_messages`, `suggestions`, `comments`, `sources`, `documents`, `user_settings`; (2) CREATEs `users` table (with UNIQUE constraint on `email`) and `invite_codes` table; (3) ADDs `user_id UUID NOT NULL` + `is_private BOOLEAN NOT NULL DEFAULT FALSE` to `documents`; (4) ADDs `user_id UUID NOT NULL` to `sources` and `chat_messages`; (5) RECREATEs `user_settings` with `user_id UUID PK`; (6) ADDs FK constraints with `ON DELETE CASCADE`
- [ ] T006 [P] Add `SessionMiddleware` to `src/writer/main.py` using `SECRET_KEY` from `settings`; ensure middleware is registered before all routers

**Checkpoint**: Run `uv run alembic upgrade head` — migration must apply cleanly with no errors before proceeding.

---

## Phase 3: User Story 1 — Invite-Only Registration and Login (Priority: P1) 🎯 MVP

**Goal**: New users register with an invite code (email + password). Existing users log in. All unauthenticated requests redirect to login. Invite codes are single-use.

**Independent Test**: (1) Generate invite code via CLI. (2) Register with that code. (3) Confirm second registration with same code is rejected. (4) Confirm unauthenticated GET to `/` redirects to `/auth/login`. (5) Confirm login with wrong credentials is rejected.

### Tests — User Story 1 (write first, confirm they FAIL)

- [ ] T007 [P] [US1] Write failing unit tests for `hash_password`, `verify_password`, `register_user` (valid code, used code, duplicate email, short password), and `authenticate_user` (correct/wrong credentials) in `tests/unit/test_auth_service.py`
- [ ] T008 [P] [US1] Write failing integration tests for full registration flow (valid invite → account created, code marked used) and login flow (correct → session set, incorrect → None returned) in `tests/integration/test_auth_service.py`

### Implementation — User Story 1

- [ ] T009 [US1] Implement `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`, `register_user(db, invite_code, email, password) -> UserResponse`, `authenticate_user(db, email, password) -> UserResponse | None` in `src/writer/services/auth_service.py`
- [ ] T010 [P] [US1] Implement `get_current_user(request: Request, db) -> UserResponse` dependency that reads `user_id` from session cookie and raises redirect to `/auth/login` if missing or invalid in `src/writer/core/auth.py`
- [ ] T011 [P] [US1] Create `src/writer/templates/login.html` extending `base.html` with email + password form posting to `POST /auth/login`
- [ ] T012 [P] [US1] Create `src/writer/templates/register.html` extending `base.html` with invite_code + email + password form posting to `POST /auth/register`
- [ ] T013 [US1] Implement auth routes in `src/writer/api/auth.py`: `GET /auth/login` (render login page, redirect if already authed), `POST /auth/login` (authenticate, set session, redirect or re-render with error), `GET /auth/register` (render register page), `POST /auth/register` (validate invite, create user, set session, redirect or re-render with error), `POST /auth/logout` (clear session, redirect to login)
- [ ] T014 [US1] Register auth router in `src/writer/main.py`; add `get_current_user` as dependency to all existing route handlers in `src/writer/api/documents.py`, `sources.py`, `chat.py`, `suggestions.py`, `settings.py`

**Checkpoint**: User Story 1 is complete when: a user can register with an invite code, log in, and the app rejects unauthenticated access. Run `uv run pytest tests/unit/test_auth_service.py tests/integration/test_auth_service.py` — all must pass.

---

## Phase 4: User Story 2 — Complete Data Isolation Between Users (Priority: P1)

**Goal**: All document, source, chunk, and settings queries are scoped to the authenticated user. Direct URL access to another user's resource returns 404. Agent searches never cross user boundaries.

**Independent Test**: Create two users (A and B). User A creates a document and adds a source. Log in as user B. Verify: (1) document list is empty; (2) direct URL to user A's document returns 404; (3) source list is empty.

### Tests — User Story 2 (write first, confirm they FAIL)

- [ ] T015 [US2] Write failing integration tests in `tests/integration/test_user_isolation.py` covering: user B's document list excludes user A's docs; user B gets 404 on user A's document ID; user B's source list excludes user A's sources; vector store query for user B returns zero chunks from user A's collection

### Implementation — User Story 2

- [ ] T016 [P] [US2] Update all functions in `src/writer/services/document_service.py` to accept `user_id: UUID` and add `WHERE documents.user_id = :user_id` to all queries; raise 404 (not 403) when a document is not found for that user
- [ ] T017 [P] [US2] Update all functions in `src/writer/services/source_service.py` to accept `user_id: UUID`; filter list/get by user_id; set `source.user_id` on creation
- [ ] T018 [P] [US2] Update `src/writer/services/settings_service.py` to accept `user_id: UUID`; replace `WHERE id = 1` with `WHERE user_id = :user_id`; upsert by user_id
- [ ] T019 [P] [US2] Update `src/writer/services/vector_store.py` to route all operations through a per-user collection named `user_{user_id.hex}` (UUID without dashes); update `add`, `query`, and `delete` functions to accept `user_id: UUID`
- [ ] T020 [US2] Update all route handlers in `src/writer/api/documents.py`, `sources.py`, `chat.py`, `suggestions.py`, `settings.py` to extract `user.id` from the injected `get_current_user` result and pass it to every service call
- [ ] T021 [US2] Replace hardcoded `_USER_ID = "default_user"` and all literal `"default_user"` strings with `str(user_id)` in `src/writer/services/chat_service.py` and `src/writer/services/agent_service.py`

**Checkpoint**: Run `uv run pytest tests/integration/test_user_isolation.py` — all must pass. Manually verify two-user isolation in the running app.

---

## Phase 5: User Story 3 — Admin CLI for Invite Code Generation (Priority: P2)

**Goal**: Administrator can generate one or more invite codes from the command line. Administrator can reset any user's password from the command line.

**Independent Test**: Run `uv run python -m writer.cli.admin generate-invite --count 3` — prints 3 lines of 32-char hex codes. Use one code to register. Run it again with the same code in registration — should fail. Run `uv run python -m writer.cli.admin reset-password user@example.com newpass123` — confirms success; user can then log in with the new password.

### Tests — User Story 3 (write first, confirm they FAIL)

- [ ] T022 [US3] Extend `tests/unit/test_auth_service.py` with failing unit tests for `create_invite_codes(db, count=3)` (returns 3 unique 32-char codes, persists to DB) and `reset_password(db, email, new_password)` (updates hash; wrong email raises error)

### Implementation — User Story 3

- [ ] T023 [US3] Implement `create_invite_codes(db, count: int) -> list[str]` and `reset_password(db, email: str, new_password: str) -> None` in `src/writer/services/auth_service.py`
- [ ] T024 [US3] Create `src/writer/cli/__init__.py` (empty) and `src/writer/cli/admin.py` with `argparse`-based CLI; implement `generate-invite [--count N]` (calls `create_invite_codes`, prints codes to stdout) and `reset-password <email> <new_password>` (calls `reset_password`); wire database connection using `asyncio.run` with the existing async session factory

**Checkpoint**: Both CLI commands run without error. Invite codes generated are accepted by the registration form. Password reset allows login with the new password.

---

## Phase 6: User Story 4 — Shared Knowledge Pool Within a User (Priority: P2)

**Goal**: An agent working on any non-private document can retrieve chunks from sources added to any other non-private document owned by the same user.

**Independent Test**: User creates Document A and Document B. Adds a source to Document A (indexed). Opens chat in Document B. Asks a question whose answer is only in the Document A source. Agent returns the relevant content.

### Tests — User Story 4 (write first, confirm they FAIL)

- [ ] T025 [US4] Write failing integration tests in `tests/integration/test_shared_knowledge.py`: index a chunk under doc A (non-private), query with doc B context for same user → chunk returned; query with doc B context for a different user → chunk not returned

### Implementation — User Story 4

- [ ] T026 [US4] Update `src/writer/services/indexer.py` to store `user_id` (str), `document_id` (str), and `is_private` (bool, default `False`) as chunk metadata on every `collection.add()` call
- [ ] T027 [US4] Update `src/writer/services/vector_store.py` query function to accept `is_private_doc: bool` and `doc_id: UUID`; when `is_private_doc=False` filter by `{"is_private": False}` (cross-document pool); when `is_private_doc=True` filter by `{"document_id": {"$eq": str(doc_id)}}` (self-only)
- [ ] T028 [US4] Update `src/writer/services/chat_service.py` to look up the current document's `is_private` flag and pass both `is_private_doc` and `doc_id` to vector store queries

**Checkpoint**: Run `uv run pytest tests/integration/test_shared_knowledge.py` — all must pass.

---

## Phase 7: User Story 5 — Private Document Mode (Priority: P3)

**Goal**: A user can mark any document Private. Private documents' chunks are excluded from all other documents' agent searches. Toggling privacy takes effect immediately. Private documents are visually marked in the list.

**Independent Test**: Mark Document A private. Open chat in Document B. Ask a question answered only by Document A's source. Agent returns no results from Document A. Unmark Document A. Ask again. Agent now returns results from Document A.

### Tests — User Story 5 (write first, confirm they FAIL)

- [ ] T029 [US5] Write failing integration tests in `tests/integration/test_privacy.py`: toggle doc A to private → chunks excluded from doc B query; toggle back → chunks included; within private doc A itself → own chunks still accessible; `update_privacy()` correctly updates ChromaDB `is_private` metadata

### Implementation — User Story 5

- [ ] T030 [US5] Implement `toggle_privacy(db, doc_id: UUID, user_id: UUID, is_private: bool) -> DocumentResponse` in `src/writer/services/document_service.py`; call `vector_store.update_privacy()` after updating the database
- [ ] T031 [P] [US5] Implement `update_privacy(user_id: UUID, doc_id: UUID, is_private: bool) -> None` in `src/writer/services/vector_store.py`; retrieve all chunk IDs for the document from the user's collection and call `collection.update()` to set `is_private` metadata
- [ ] T032 [US5] Add `PATCH /api/documents/{doc_id}/privacy` endpoint to `src/writer/api/documents.py`; accept `{"is_private": bool}` JSON body; call `toggle_privacy`; return updated `DocumentResponse`
- [ ] T033 [P] [US5] Add a privacy toggle control (button or checkbox) to `src/writer/templates/document.html` that POPs `PATCH /api/documents/{doc_id}/privacy` via HTMX and updates the UI state
- [ ] T034 [P] [US5] Add a "Private" badge (e.g., lock icon or label) to private documents in `src/writer/templates/index.html`

**Checkpoint**: Run `uv run pytest tests/integration/test_privacy.py` — all must pass. Manual test of toggle behaviour in running app.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [ ] T035 Run `uv run pytest` and fix all failures before marking any task complete
- [ ] T036 [P] Run `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/` and commit clean output
- [ ] T037 [P] Run `uv run mypy src/` and fix all type errors (no `Any`, no plain dicts, all function signatures typed)
- [ ] T038 Perform end-to-end validation per `specs/009-multi-user-invite/quickstart.md`: generate invite code, register two separate users, verify each user's documents are invisible to the other, test private document mode, reset a password via CLI

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — blocks all user stories
- **US1 (Phase 3)**: Depends on Foundational — no dependency on other stories
- **US2 (Phase 4)**: Depends on US1 (auth dependency injection wired in T014 is the hook point for user_id propagation)
- **US3 (Phase 5)**: Depends on Foundational only — can be done concurrently with US2 by a second developer
- **US4 (Phase 6)**: Depends on US2 (per-user vector store in T019 must exist)
- **US5 (Phase 7)**: Depends on US4 (privacy-aware query in T027 is extended, not replaced)
- **Polish (Final Phase)**: Depends on all desired stories being complete

### Within Each User Story

- Service-layer tests MUST be written and confirmed failing before implementation
- ORM models before Pydantic schemas (T003 before T004 if modifying the same entity)
- Services before API route handlers
- Core auth dependency (T010) before route integration (T013, T014)

### Parallel Opportunities

| Phase | Parallel group |
|-------|---------------|
| Phase 2 | T003 + T004 + T006 (different files) |
| Phase 3 tests | T007 + T008 |
| Phase 3 impl | T010 + T011 + T012 (after T009 starts, different files) |
| Phase 4 impl | T016 + T017 + T018 + T019 (all different service files) |
| Phase 5 impl | T031 + T033 + T034 |
| Polish | T036 + T037 |

---

## Parallel Example: User Story 2

```bash
# After T015 (tests written), launch all service updates together:
Task: "Update document_service.py to filter by user_id — src/writer/services/document_service.py"
Task: "Update source_service.py to filter by user_id — src/writer/services/source_service.py"
Task: "Update settings_service.py for per-user rows — src/writer/services/settings_service.py"
Task: "Update vector_store.py for per-user collections — src/writer/services/vector_store.py"

# Then (sequentially after the above):
Task: "Update all API route handlers to pass user.id — src/writer/api/*.py"
Task: "Replace default_user constant — src/writer/services/chat_service.py + agent_service.py"
```

---

## Implementation Strategy

### MVP (User Story 1 Only — Phases 1–3)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T006) — run migration
3. Complete Phase 3: User Story 1 (T007–T014)
4. **STOP and VALIDATE**: Any user with an invite code can register and log in; all unauthenticated access redirected
5. Deploy/demo if ready

### Incremental Delivery

- Setup + Foundational → Foundation ready (invite codes in DB, session middleware running)
- + US1 → Authenticated access, registration, login (MVP)
- + US2 → Full user isolation (privacy/security complete)
- + US3 → Admin CLI operational
- + US4 → Shared knowledge pool active
- + US5 → Private document mode active

---

## Summary

| Phase | Tasks | Parallel? | Story |
|-------|-------|-----------|-------|
| 1 — Setup | T001–T002 | T002 | — |
| 2 — Foundational | T003–T006 | T003, T004, T006 | — |
| 3 — Registration & Login | T007–T014 | T007–T008, T010–T012 | US1 |
| 4 — Data Isolation | T015–T021 | T016–T019 | US2 |
| 5 — Admin CLI | T022–T024 | — | US3 |
| 6 — Shared Knowledge | T025–T028 | — | US4 |
| 7 — Private Documents | T029–T034 | T031, T033–T034 | US5 |
| Final — Polish | T035–T038 | T036–T037 | — |
| **Total** | **38 tasks** | **17 parallelizable** | |

- [P] tasks = different files, no inter-task dependency within the phase
- Story label maps each task to its user story for traceability
- Each user story phase is independently completable and testable
- Write failing tests first — confirm red before implementing green
