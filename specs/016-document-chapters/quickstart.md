# Quickstart: Chapter-Centric Documents

**Feature**: 016-document-chapters
**Date**: 2026-04-14

## Prerequisites

- Docker running (PostgreSQL container)
- Python 3.13+ with uv
- Node.js (for esbuild bundling of editor.js)

## Setup

```bash
# Start database
docker-compose up -d postgres

# Install dependencies
cd /Users/will/projects/document-projects/documentLM
uv sync

# Run migration (creates chapters + chapter_snippets tables, migrates data)
cd /Users/will/projects/document-projects/documentLM && uv run alembic upgrade head

# Build editor bundle (after editor.js changes)
npm run build:dev

# Start dev server
cd /Users/will/projects/document-projects/documentLM && uv run uvicorn writer.main:app --reload
```

## Development Workflow

### Running Tests (TDD)

```bash
cd /Users/will/projects/document-projects/documentLM && uv run pytest tests/unit/test_chapter_service.py -v
cd /Users/will/projects/document-projects/documentLM && uv run pytest tests/unit/ -v
```

### Linting

```bash
cd /Users/will/projects/document-projects/documentLM && uv run ruff check --fix src/ tests/
cd /Users/will/projects/document-projects/documentLM && uv run ruff format src/ tests/
cd /Users/will/projects/document-projects/documentLM && uv run mypy src/
```

### Rebuilding Editor Bundle

After any change to `static/editor.js`:

```bash
npm run build:dev
```

## Implementation Order

1. **Models + Migration** — Chapter and ChapterSnippet models, Alembic migration with data migration
2. **Chapter Service (TDD)** — CRUD, reorder, content cache rebuild
3. **Chapter API Endpoints** — HTMX + JSON endpoints for chapter management
4. **Snippet Service Updates** — Chapter filtering, assignment/unassignment
5. **Templates** — document.html chapter layout, TOC, chapter partials
6. **Editor.js** — Single TipTap instance with dynamic chapter mounting
7. **CSS** — Chapter layout, TOC, brief toggle styles

## Testing Strategy

- **Unit tests (TDD)**: chapter_service (create, update, delete, reorder, content rebuild), snippet_service (chapter assignment, filtered listing)
- **No tests for**: API endpoints, frontend templates, editor.js (per constitution)
- **Manual testing**: Create multi-chapter document, verify TOC, test chapter switching, test snippet assignment, verify single-chapter looks standard

## Key Files to Create

| File | Purpose |
|------|---------|
| `src/writer/models/db.py` | Add Chapter + ChapterSnippet models |
| `src/writer/models/schemas.py` | Add chapter Pydantic schemas |
| `src/writer/services/chapter_service.py` | Chapter CRUD + content rebuild |
| `src/writer/api/chapters.py` | Chapter HTMX/JSON endpoints |
| `migrations/versions/xxxx_add_chapters.py` | DB migration |
| `src/writer/templates/partials/chapter_card.html` | Rendered chapter block |
| `src/writer/templates/partials/chapter_editor.html` | Active chapter editor mount |
| `src/writer/templates/partials/toc.html` | Table of contents |

## Key Files to Modify

| File | Change |
|------|--------|
| `src/writer/templates/document.html` | Chapter layout replacing single editor |
| `src/writer/services/snippet_service.py` | Chapter-filtered listing, assignment |
| `src/writer/api/snippets.py` | Chapter filter query param |
| `static/editor.js` | Per-chapter TipTap mounting |
| `static/style.css` | Chapter layout + TOC styles |
| `src/writer/main.py` | Register chapter router |
