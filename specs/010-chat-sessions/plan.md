# Implementation Plan: Chat Session Management

**Branch**: `010-chat-sessions` | **Date**: 2026-03-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-chat-sessions/spec.md`

## Summary

Add multi-session chat support to the document workbench. Users can start new chat sessions (clearing visible history while preserving prior conversations), and access archived sessions via a dropdown in the chat panel. Each session is private to its user. At most one session per `(user_id, document_id)` pair is active at a time. The feature requires a new `chat_sessions` table, a `session_id` FK on `chat_messages`, a new service layer, three new API endpoints, and HTMX-driven UI changes to the document template.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX 2.0, Pydantic v2, SQLAlchemy 2.x / asyncpg
**Storage**: PostgreSQL (Docker container) — one new table: `chat_sessions`; one column added to `chat_messages`
**Testing**: pytest (TDD on service layer only — `chat_session_service.py`)
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: Web service (FastAPI + HTMX)
**Performance Goals**: Session switch completes within 3 seconds (SC-004); new chat ready within 2 seconds (SC-002)
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save; minimize-JS (HTMX OOB for multi-element updates)
**Scale/Scope**: Small number of sessions per document (tens) — no pagination required

## Constitution Check

- [x] **I. Python + uv**: All new code is Python; uv used for deps — no new packages needed
- [x] **II. TDD scope**: Tests planned for `chat_session_service.py` only; not for endpoints or templates
- [x] **III. No remote APIs in tests**: `invoke_chat_agent` already mocked in existing tests; new session service has no external calls
- [x] **IV. Simplicity**: Scope confirmed with user via spec + clarification. No extra features (no rename, delete, share)
- [x] **V. Strong typing**: All new functions use Pydantic models (`ChatSessionResponse`) or typed ORM returns; no plain dicts; no Any
- [x] **VI. Functional style**: New `chat_session_service.py` is module-level async functions; no stateful classes
- [x] **VII. Ruff**: ruff check + ruff format run before every save
- [x] **VIII. Containers**: PostgreSQL in Docker; migration runs via `alembic upgrade head`
- [x] **IX. Logging**: All `except` blocks in new service will log at ERROR; session state transitions emit INFO entries
- [x] **ADK architecture**: No new agent types introduced. `ChatAgent` reused unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/010-chat-sessions/
├── plan.md                          # This file
├── research.md                      # Phase 0 output
├── data-model.md                    # Phase 1 output
├── quickstart.md                    # Phase 1 output
├── contracts/
│   └── api-chat-sessions.md         # Phase 1 output
└── tasks.md                         # Phase 2 output (/speckit.tasks)
```

### Source Code Changes

```text
src/writer/
├── models/
│   ├── db.py                        # Add ChatSession ORM; add session_id to ChatMessage
│   ├── enums.py                     # Add SessionStatus enum
│   └── schemas.py                   # Add ChatSessionResponse; update ChatMessageResponse
├── services/
│   ├── chat_session_service.py      # NEW — session CRUD + state transitions
│   └── chat_service.py              # Update to scope messages to active session
└── api/
    └── chat.py                      # Add 3 new endpoints; update existing 3 endpoints

src/writer/templates/
├── document.html                    # Add "New Chat" button + dropdown anchor
└── partials/
    └── chat_session_dropdown.html   # NEW — session selector partial

migrations/versions/
└── XXXX_add_chat_sessions.py        # NEW — add table, backfill, add FK

tests/
├── unit/
│   └── test_chat_session_service.py # NEW — TDD for session service
└── integration/
    └── test_chat_sessions.py        # NEW — DB integration tests for session transitions
```

**Structure Decision**: Single web service project (unchanged from existing layout). No new top-level directories.

## Complexity Tracking

No constitution violations. All principles satisfied without justification needed.

## Phase 0: Research

**Status**: Complete. See [research.md](research.md).

Key decisions resolved:

- One active session per `(user_id, document_id)` — enforced by partial unique index
- Migration backfills existing messages into synthetic default sessions
- HTMX OOB swaps for dropdown + history simultaneous updates
- Document context always uses current state (no snapshotting)
- ADK `InMemorySessionService` unchanged — it is a per-request transport, not persistence
- "New Chat" on empty session is a no-op (FR-011)
- Reactivating a session does not re-run overview initialization

## Phase 1: Design

### Data Model

See [data-model.md](data-model.md) for full schema, state machine, and migration plan.

**New table**: `chat_sessions` (`id`, `user_id`, `document_id`, `status`, `created_at`)

**Modified table**: `chat_messages` — add `session_id UUID FK NOT NULL`

**New enum**: `SessionStatus` (`active`, `archived`)

**Partial unique index** on `chat_sessions(user_id, document_id) WHERE status = 'active'` — database-enforced single-active invariant.

### API Contracts

See [contracts/api-chat-sessions.md](contracts/api-chat-sessions.md).

**New endpoints**:

1. `POST /api/documents/{doc_id}/chat/sessions` — create new session
2. `GET /api/documents/{doc_id}/chat/sessions` — list sessions for dropdown
3. `POST /api/documents/{doc_id}/chat/sessions/{session_id}/activate` — reactivate archived session

**Modified endpoints** (no contract shape change; internal filter changed):

- `GET /api/documents/{doc_id}/chat` — now filters by `session_id` not `document_id`
- `POST /api/documents/{doc_id}/chat` — attaches `session_id` to new message
- `GET /api/documents/{doc_id}/chat/stream` — creates session if none exists before seeding

### Service Design: `chat_session_service.py`

```python
# All functions are async; all return typed Pydantic models or ORM instances

async def get_or_create_active_session(
    db: AsyncSession, user_id: UUID, document_id: UUID
) -> ChatSession:
    """Return current active session, creating one if none exists."""

async def create_new_session(
    db: AsyncSession, user_id: UUID, document_id: UUID
) -> ChatSession | None:
    """
    Archive current active session (if it has messages) and create a new active one.
    Returns new session, or None if current session was empty (no-op).
    """

async def activate_session(
    db: AsyncSession, user_id: UUID, session_id: UUID
) -> ChatSession:
    """
    Set given session to active, archiving the previously active session.
    Raises ValueError if session not found or doesn't belong to user.
    """

async def list_sessions(
    db: AsyncSession, user_id: UUID, document_id: UUID
) -> list[ChatSessionResponse]:
    """Return all sessions ordered most-recent first, with computed labels."""

async def get_session_messages(
    db: AsyncSession, session_id: UUID, user_id: UUID
) -> list[ChatMessageResponse]:
    """Return all messages for a session ordered oldest-first."""

async def session_has_messages(
    db: AsyncSession, session_id: UUID
) -> bool:
    """Check whether a session has any messages (used by create_new_session guard)."""
```

### Template Design

**`document.html` chat panel additions** (no JS):

```html
<!-- Session dropdown — above chat history -->
<div class="meta-chat-sessions">
  <select id="chat-session-dropdown"
          hx-post="/api/documents/{{ doc.id }}/chat/sessions/activate"
          hx-target="#chat-history"
          hx-swap="innerHTML"
          hx-trigger="change"
          hx-vals="js:{session_id: this.value}">
    ... rendered by partial ...
  </select>
  <button id="chat-new-btn"
          hx-post="/api/documents/{{ doc.id }}/chat/sessions"
          hx-target="#chat-history"
          hx-swap="innerHTML">
    New Chat
  </button>
</div>
```

Note: HTMX OOB swap updates `#chat-session-dropdown` from the server response simultaneously with `#chat-history`.

### Quickstart

See [quickstart.md](quickstart.md).

## Implementation Order

Tasks are designed for sequential execution with parallel opportunities within each phase. See `/speckit.tasks` for the full task breakdown.

**Sequence**:

1. Migration + ORM + enums + schemas (foundation — everything depends on this)
2. `chat_session_service.py` (TDD) — no UI dependency
3. Update `chat_service.py` to use session ID
4. New + updated API endpoints
5. Template changes (dropdown + New Chat button)
6. Integration tests
