# Quickstart: UX Improvements (003)

**Branch**: `003-ux-improvements`

## Prerequisites

The `001` and `002` features must be merged and the database migrated (`alembic upgrade head`) before working on this branch.

## Run the Migration

```bash
uv run alembic upgrade head
```

This adds the `chat_messages` table and `chatrole` enum.

## Start the Stack

```bash
docker-compose up -d postgres
uv run uvicorn writer.main:app --reload
```

## Run Tests

```bash
uv run pytest tests/unit/test_chat_service.py   # new tests (TDD)
uv run pytest tests/unit/                        # all unit tests
```

## Lint and Type-check

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Feature Touch-map

| File                                          | Change Type | Notes                                         |
| --------------------------------------------- | ----------- | --------------------------------------------- |
| `src/writer/models/enums.py`                  | UPDATE      | Add `ChatRole` enum                           |
| `src/writer/models/db.py`                     | UPDATE      | Add `ChatMessage` ORM model                   |
| `src/writer/models/schemas.py`                | UPDATE      | Add `ChatMessageCreate`, `ChatMessageResponse` |
| `src/writer/services/chat_service.py`         | NEW         | TDD — chat message CRUD + agent invocation    |
| `src/writer/agents/chat_agent.py`             | NEW         | Google ADK `ChatAgent`                        |
| `src/writer/api/chat.py`                      | NEW         | GET + POST `/api/documents/{id}/chat`         |
| `src/writer/main.py`                          | UPDATE      | Register `chat` router                        |
| `src/writer/api/suggestions.py`               | UPDATE      | Allow empty-selection comments (global modal) |
| `src/writer/templates/document.html`          | UPDATE      | Modal, floating menu, inline overlay, chat    |
| `src/writer/templates/partials/sources.html`  | UPDATE      | `<details>` wrapper + hover-delete class      |
| `src/writer/templates/partials/suggestion.html` | UPDATE    | Remove sidebar target; style for overlay      |
| `src/writer/templates/partials/chat_message.html` | NEW     | Single chat turn partial                      |
| `static/style.css`                            | UPDATE      | ~80 new lines for all new UI elements         |
| `migrations/versions/XXXX_add_chat_messages.py` | NEW       | Alembic migration                             |
