# Quickstart: Chat Session Management

**Branch**: `010-chat-sessions` | **Date**: 2026-03-18

## Prerequisites

- Docker running (`docker-compose up -d postgres`)
- `uv` installed
- Feature branch checked out: `git checkout 010-chat-sessions`

## Setup

```bash
# Install dependencies (no new packages needed)
uv sync

# Run new migration
uv run alembic upgrade head

# Start dev server
uv run uvicorn writer.main:app --reload
```

## Verify the Migration

```bash
# Check chat_sessions table exists
docker-compose exec postgres psql -U writer -d writer -c "\d chat_sessions"

# Check session_id column added to chat_messages
docker-compose exec postgres psql -U writer -d writer -c "\d chat_messages"

# Check existing messages were backfilled (should return 0)
docker-compose exec postgres psql -U writer -d writer \
  -c "SELECT COUNT(*) FROM chat_messages WHERE session_id IS NULL;"
```

## Manual Test Flow

1. Open a document with an existing chat history
2. Verify the session dropdown shows "Current Chat" with the existing messages
3. Click "New Chat" — verify the chat area clears and dropdown updates
4. Send a message in the new session — verify it doesn't contain prior history
5. Open the dropdown — verify the previous session appears with a date label
6. Select the archived session — verify its messages reappear
7. Reload the page — verify both sessions are still present in the dropdown

## Run Tests

```bash
uv run pytest tests/unit/test_chat_session_service.py -v
uv run pytest tests/integration/test_chat_sessions.py -v
uv run pytest  # full suite
```

## Key Files Changed

| File | Change |
|------|--------|
| `migrations/versions/XXXX_add_chat_sessions.py` | New migration |
| `src/writer/models/db.py` | Add `ChatSession` model; update `ChatMessage` with `session_id` |
| `src/writer/models/enums.py` | Add `SessionStatus` enum |
| `src/writer/models/schemas.py` | Add `ChatSessionResponse`; update `ChatMessageResponse` |
| `src/writer/services/chat_session_service.py` | New service: session CRUD + state transitions |
| `src/writer/services/chat_service.py` | Update to use active session for messages |
| `src/writer/api/chat.py` | Add 3 new endpoints; update existing endpoints |
| `src/writer/templates/document.html` | Add "New Chat" button + session dropdown |
| `src/writer/templates/partials/chat_session_dropdown.html` | New partial |
| `tests/unit/test_chat_session_service.py` | New unit tests |
| `tests/integration/test_chat_sessions.py` | New integration tests |
