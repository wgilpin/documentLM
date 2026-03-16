# Quickstart: Universal App Settings

**Feature**: 007-universal-settings

## How to verify this feature works end-to-end

### 1. Start the stack

```bash
docker-compose up -d postgres
uv run alembic upgrade head
uv run uvicorn writer.main:app --reload
```

### 2. Open a document

Navigate to `http://localhost:8000`, open or create a document.

### 3. Open settings

Click the **⚙** gear icon in the toolbar (left of the Delete button). The settings modal opens.

### 4. Configure settings

- Enter your name (e.g., `Alice`)
- Select a language (e.g., `French`)
- Enter an AI instruction (e.g., `Always respond in a formal academic tone.`)
- Click **Save**

### 5. Verify persistence

Refresh the page, reopen the settings modal — your name, language, and instructions are still populated.

### 6. Verify AI instruction injection

Type a message in the chat panel (e.g., `Summarise this document`). The AI response should reflect the saved instruction (formal tone in French in this example).

### 7. Run tests

```bash
uv run pytest tests/unit/test_settings_service.py -v
```

Expected: all tests pass.

## Key files introduced by this feature

| File | Purpose |
|------|---------|
| `src/writer/models/db.py` | `UserSettings` ORM model added |
| `src/writer/models/schemas.py` | `UserSettingsUpdate`, `UserSettingsResponse` added |
| `src/writer/services/settings_service.py` | `get_settings`, `upsert_settings` |
| `src/writer/api/settings.py` | `GET /api/settings`, `POST /api/settings` |
| `src/writer/agents/chat_agent.py` | `make_chat_agent` accepts optional `UserSettings` |
| `src/writer/services/chat_service.py` | Fetches settings before invoking agent |
| `src/writer/templates/document.html` | Settings icon + modal added |
| `migrations/versions/<hash>_add_user_settings.py` | Alembic migration |
| `tests/unit/test_settings_service.py` | Service layer unit tests |
