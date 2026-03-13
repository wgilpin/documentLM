# Research: Document Workbench MVP

## 1. Google ADK — Local Setup

**Decision**: Use `google-adk` Python package with Gemini 2.0 Flash (via `GOOGLE_API_KEY`),
run entirely in-process within FastAPI (no separate `adk run` process needed for production).

**How it works**:
- Install: `uv add google-adk`
- Agents are Python objects created with `google.adk.Agent`
- Session state (`session.state`) is an in-memory dict scoped to a runner call
- For our prototype, we don't use ADK's session persistence — document context is
  passed directly to the agent on each invocation
- The agent runner (`google.adk.runners.Runner`) is called with an `InMemorySessionService`
- ADK wraps the underlying Gemini API; all calls go through `google.generativeai`

**Key pattern** (Drafter invocation):
```python
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

drafter = Agent(name="drafter", model="gemini-2.0-flash", instruction="...")
runner = Runner(agent=drafter, session_service=InMemorySessionService(), app_name="writer")
```

**In tests**: The `Runner` and `Agent` classes MUST be mocked. Agent invocations MUST NOT
reach the Gemini API. Use `unittest.mock.AsyncMock` on the runner's `run_async` method.

**Rationale**: In-process invocation is simpler than running a separate ADK server for a
prototype. Session state is not persisted — document context is injected per call.

**Alternatives considered**:
- Anthropic SDK (already in pyproject.toml): rejected — user explicitly chose Google ADK
- LangChain: rejected — unnecessary abstraction layer for a prototype

---

## 2. Database Access — SQLAlchemy 2.x Async + asyncpg + Alembic

**Decision**: `sqlalchemy[asyncio]` with `asyncpg` as the async driver. Alembic for
schema migrations.

**Rationale**: SQLAlchemy 2.x async API is idiomatic with FastAPI's async endpoints.
Alembic provides deterministic migration history. Raw `asyncpg` would require manual
SQL and offer no migration story.

**Dependency additions** (to pyproject.toml):
```
sqlalchemy[asyncio]>=2.0
asyncpg>=0.30
alembic>=1.14
pydantic-settings>=2.0
```

**Connection pattern**:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine("postgresql+asyncpg://...", echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

**FastAPI dependency injection** (in `core/database.py`):
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

**Alternatives considered**:
- Raw `asyncpg`: simpler but no migration tooling and no ORM type safety
- Tortoise-ORM: less mature FastAPI integration

---

## 3. HTMX Frontend Pattern

**Decision**: Jinja2 templates served by FastAPI + HTMX for dynamic partial updates.
No custom JavaScript. Editor is a plain `<textarea>`. Suggestions displayed in a
right-hand sidebar via HTMX partial swaps.

**Key HTMX patterns used**:

| Interaction | HTMX attribute |
|---|---|
| Submit margin comment | `hx-post="/api/comments" hx-target="#suggestion-panel" hx-swap="innerHTML"` |
| Accept suggestion | `hx-post="/api/suggestions/{id}/accept" hx-target="#document-content" hx-swap="innerHTML"` |
| Reject suggestion | `hx-post="/api/suggestions/{id}/reject" hx-target="#suggestion-{id}" hx-swap="outerHTML"` |
| Add source | `hx-post="/api/sources" hx-target="#source-list" hx-swap="beforeend"` |

**Text selection for margin comments**: A small inline `<script>` block (not a JS file)
captures `document.getSelection()` and writes to a hidden form field on mouseup. This is the
minimum JS required and cannot be replaced by an HTMX attribute — justified under Constitution
Principle VII (minimize JS; MUST NOT write JS when HTMX achieves the same result, but this
specific interaction requires selection capture).

**Rationale**: HTMX eliminates a full SPA framework. The editor textarea is sufficient for
a prototype — no CodeMirror or ProseMirror needed.

---

## 4. Suggested State Representation

**Decision**: Store suggestions in a `suggestions` DB table with fields for the original
text span, the suggested replacement text, and a status (pending/accepted/rejected).
On acceptance, the document `content` field is updated by substituting the original span
with the suggested text.

**Text position strategy**: Store `selection_start` and `selection_end` as character offsets
into the markdown content. Simple substring replace on accept. If the document is edited
between comment submission and acceptance, the suggestion is automatically invalidated
(status → `stale`) because the offset no longer matches.

**Rationale**: Character offsets are the simplest stable reference for a textarea-based
editor. Diff/patch approaches are too complex for a prototype.

---

## 5. PDF Text Extraction

**Decision**: Use `pypdf` (pure Python, no system dependencies) for PDF text extraction
on upload. Store extracted text as the source `content` field.

**Dependency addition**: `pypdf>=4.0`

**Rationale**: `pypdf` has no native binary dependencies, making it Docker-friendly.
`pdfminer` and `pymupdf` require native libraries. Extraction quality is sufficient for
a prototype.

---

## 6. pyproject.toml Changes Required

The existing `pyproject.toml` has `anthropic>=0.39.0` but the project uses Google ADK.
Plan: add `google-adk`, add `google-generativeai`, add SQLAlchemy/asyncpg/Alembic/pypdf/
pydantic-settings. Remove `anthropic` (or leave it — confirm with user before removing).

Also: `black` is in dev deps but constitution requires `ruff format`. Plan: remove `black`,
ensure `ruff format` is used consistently.

**NEEDS CLARIFICATION**: Should `anthropic` be removed from dependencies?

---

## 7. Docker Setup

**Decision**: Two containers — `postgres` (official image) and `app` (Python/uv Dockerfile).

```yaml
# docker-compose.yml (outline)
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: writer
      POSTGRES_USER: writer
      POSTGRES_PASSWORD: writer
  app:
    build: .
    depends_on: [postgres]
    env_file: .env
    ports: ["8000:8000"]
```

**Dockerfile** uses `python:3.13-slim`, installs `uv`, copies project, runs
`uv sync --no-dev`, starts with `uvicorn`.
