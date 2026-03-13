# Quickstart: Document Workbench MVP

## Prerequisites

- Docker Desktop running
- `uv` installed (`pip install uv` or via installer)
- A Google API key with Gemini access (`GOOGLE_API_KEY`)

## 1. Clone and install

```bash
git clone <repo>
uv sync
```

## 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=your-key-here
```

`.env.example` content:
```
DATABASE_URL=postgresql+asyncpg://writer:writer@localhost:5432/writer
GOOGLE_API_KEY=
```

## 3. Start PostgreSQL

```bash
docker-compose up -d postgres
```

## 4. Run database migrations

```bash
uv run alembic upgrade head
```

## 5. Start the development server

```bash
uv run uvicorn writer.main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000

## 6. Run the full stack in Docker

```bash
docker-compose up --build
```

This starts both `postgres` and `app` containers. App is available at http://localhost:8000.

## 7. Run tests

```bash
uv run pytest tests/unit/           # Unit tests (no DB required)
uv run pytest tests/integration/    # Integration tests (requires Docker postgres)
uv run pytest                        # All tests
```

## 8. Linting and type checking

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Verify the app works

1. Open http://localhost:8000 → document list (empty)
2. Click **New Document** → editor opens
3. Type a title and some markdown content; click **Save**
4. In the sidebar, click **Add Source → Note** → paste some text → **Add**
5. Highlight a sentence in the editor → type a margin comment → **Submit**
6. Wait for the AI suggestion to appear in the right panel
7. Click **Accept** → the document content updates with the AI suggestion
8. Click **Reject** on another suggestion → it disappears

## Common issues

| Issue | Fix |
|---|---|
| `GOOGLE_API_KEY` not set | Set in `.env` and restart the app container |
| `asyncpg` connection refused | Ensure `docker-compose up -d postgres` completed |
| Alembic migration fails | Check `DATABASE_URL` in `.env` matches docker-compose |
| `ruff` violations | Run `uv run ruff check --fix src/` before committing |
