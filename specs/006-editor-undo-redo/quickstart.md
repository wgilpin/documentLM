# Quickstart: Editor Undo/Redo

**Branch**: `006-editor-undo-redo`

## No New Dependencies

This feature adds no new Python packages or JS libraries. All required capabilities are already present:

- TipTap `history` extension — included in `StarterKit` (already on CDN)
- Pydantic `field_validator` — already in use

## Environment Setup

Add `UNDO_BUFFER_SIZE` to your `.env` (optional — defaults to 1000):

```ini
UNDO_BUFFER_SIZE=1000
```

## Running the Stack

```bash
docker-compose up -d postgres   # start DB (if not already running)
uv run uvicorn writer.main:app --reload
```

## Running Tests

```bash
uv run pytest tests/unit/test_config.py   # new unit tests for this feature
uv run pytest                             # full suite
```

## Verifying the Feature

1. Open a document at `http://localhost:8000/documents/{doc_id}`
2. A toolbar with **Undo** and **Redo** buttons appears above the editor
3. Type some text — Undo becomes enabled
4. Press **Ctrl+Z** or click **Undo** — each click removes one character
5. Trigger an AI edit via the chat panel — Undo button shows "Undo AI change" tooltip
6. Click Undo once — entire AI change is reversed
7. Click Redo — AI change is re-applied
