# Quickstart: Source Management

**Branch**: `002-source-management` | **Date**: 2026-03-13

## Prerequisites

Full stack already running. If not:

```bash
docker-compose up -d postgres
uv run alembic upgrade head
uv run uvicorn writer.main:app --reload
```

Open `http://localhost:8000`, create or open a document.

## Test the feature manually

### View sources panel

1. Open any document — the right sidebar shows a **"Sources"** section.
2. If no sources are added, the list reads: *"No sources added yet."*

### Add a Note source

1. Click the **Note** tab in the sources panel.
2. Enter a title (e.g., "Background context") and some text.
3. Click **Add Note** — the note appears in the list immediately with a date.

### Add a URL source

1. Click the **URL** tab.
2. Enter a title and a URL starting with `https://`.
3. Click **Add URL** — appears in list instantly.
4. Try submitting with an invalid URL (e.g., `not-a-url`) — an error message appears inline.

### Add a PDF source

1. Click the **PDF** tab.
2. Provide a title and select a `.pdf` file.
3. Click **Upload PDF** — text is extracted server-side; the source appears in the list.
4. Try uploading a non-PDF file — an error message appears inline.

### Remove a source

1. Click the **×** button next to any source.
2. Confirm the removal prompt — the source disappears from the list immediately.

## Run tests

```bash
uv run pytest tests/unit/test_source_service.py -v
uv run pytest tests/integration/ -v
```

## Lint and type-check

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```
