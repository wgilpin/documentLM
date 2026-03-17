# writer Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-13

## Active Technologies
- Python 3.13+ + FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, pypdf, Jinja2 (002-source-management)
- PostgreSQL (Docker container) — no schema changes (002-source-management)
- Python 3.13+ + google-adk (local), FastAPI, HTMX 2.0, Pydantic v2, SQLAlchemy 2.x / asyncpg (003-ux-improvements)
- PostgreSQL (Docker container) — one new table: `chat_messages` (003-ux-improvements)
- Python 3.13+ + google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, chromadb (new), nlp-utils (local) (005-vector-rag-sources)
- PostgreSQL (Docker container) + ChromaDB (local persistent directory `./data/chroma`) (005-vector-rag-sources)
- Python 3.13+ + google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, TipTap v2 (CDN) (006-editor-undo-redo)
- PostgreSQL (Docker container) — no changes (006-editor-undo-redo)
- PostgreSQL (Docker container) — one new table: `user_settings` (007-universal-settings)
- PostgreSQL (Docker container) — no schema changes required (008-view-add-sources)

- Python 3.13+ + google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x (async), asyncpg, Alembic, Jinja2 (001-document-workbench-mvp)

## Project Structure

```text
src/writer/
├── api/           # FastAPI routes (no tests)
├── core/          # DB, config, logging
├── models/        # SQLAlchemy ORM + Pydantic schemas
├── services/      # Business logic (TDD here)
├── agents/        # Google ADK agent definitions
└── templates/     # Jinja2 HTML templates

static/            # CSS only — no JS files
tests/
├── unit/          # Service layer tests (pytest)
└── integration/   # DB integration tests
migrations/        # Alembic migrations
```

## Commands

```bash
uv run pytest                              # all tests
uv run pytest tests/unit/                 # unit only (no DB)
uv run ruff check --fix src/ tests/       # lint
uv run ruff format src/ tests/            # format
uv run mypy src/                           # type check
uv run alembic upgrade head               # run migrations
uv run uvicorn writer.main:app --reload   # dev server
docker-compose up -d postgres             # start DB
docker-compose up --build                 # full stack
```

## Code Style

Python 3.13+: Follow standard conventions

## Recent Changes
- 009-multi-user-invite: Added Python 3.13+ + google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg
- 008-view-add-sources: Added Python 3.13+ + google-adk (local), FastAPI, HTMX 2.0, Pydantic v2, SQLAlchemy 2.x / asyncpg
- 007-universal-settings: Added Python 3.13+ + google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg


<!-- MANUAL ADDITIONS START -->
## Quality Gates

Always run `uv run pytest` before reporting a task as complete or writing a commit message. If tests fail, fix them or report the failures — do not proceed.
<!-- MANUAL ADDITIONS END -->
