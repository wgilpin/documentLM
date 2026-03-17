# Implementation Plan: Document Sources Pane – View and Add Sources

**Branch**: `008-view-add-sources` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-view-add-sources/spec.md`

## Summary

Add a "View" action to each source in the document sources pane, opening the source content in a new browser tab. URL sources open their stored URL directly; note and PDF sources render their extracted text via a new lightweight endpoint. The "Add Source" functionality (URL / paste-text / PDF upload) is **already fully implemented** — no backend or UI changes are needed for that feature.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX 2.0, Pydantic v2, SQLAlchemy 2.x / asyncpg
**Storage**: PostgreSQL (Docker container) — no schema changes required
**Testing**: pytest (backend services only — TDD for `get_source()` service function)
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: Web service (FastAPI + HTMX)
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save
**Scale/Scope**: Demo/prototype — YAGNI; minimal change only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Python + uv**: All new code is Python; uv used for deps — no new deps added
- [x] **II. TDD scope**: TDD applied to `get_source()` service function only; endpoint and template are excluded per constitution
- [x] **III. No remote APIs in tests**: View feature makes no external calls; URL sources redirect via link, not server
- [x] **IV. Simplicity**: Scope confirmed — View button only; Add Source is already done; no extras
- [x] **V. Strong typing**: `get_source()` returns `SourceResponse`; no plain dicts; no Any
- [x] **VI. Functional style**: `get_source()` is a module-level function; no new classes
- [x] **VII. Ruff**: ruff check + ruff format applied before every save
- [x] **VIII. Containers**: No infrastructure changes; existing Docker setup unchanged
- [x] **IX. Logging**: `get_source()` logs on SourceNotFoundError; view endpoint logs errors
- [x] **ADK architecture**: No new agents introduced

## Project Structure

### Documentation (this feature)

```text
specs/008-view-add-sources/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/api.md     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code Changes

```text
src/writer/
├── api/
│   └── sources.py              # Add GET /{doc_id}/sources/{source_id}/view endpoint
├── services/
│   └── source_service.py       # Add get_source(db, source_id) → SourceResponse
└── templates/
    ├── partials/
    │   └── sources.html         # Add "View" link to each source item
    └── source_view.html         # New standalone page for note/pdf content display

tests/
└── unit/
    └── test_source_service.py   # Add tests for get_source()
```

## Implementation Design

### 1. New Service Function: `get_source`

```python
get_source(db: AsyncSession, source_id: UUID) -> SourceResponse
```

- Queries `sources` table by `source_id`
- Raises `SourceNotFoundError` if not found (logs at ERROR)
- Returns `SourceResponse`

**Tests** (TDD — write first):

- `test_get_source_returns_source` — happy path with existing source
- `test_get_source_raises_not_found` — raises `SourceNotFoundError` for unknown ID

### 2. New Template: `source_view.html`

Standalone HTML page (not a partial). Displays:

- Page title = source title
- Source type badge
- Content as preformatted text block (preserves line breaks)

No JavaScript required. Accessible without authentication check (same as current pattern — document pages are not auth-gated in the prototype).

### 3. New API Endpoint: `GET /{doc_id}/sources/{source_id}/view`

- Calls `get_source(db, source_id)`
- If `source.document_id != doc_id` → 404
- Renders `source_view.html` with source data
- On `SourceNotFoundError` → 404

### 4. Template Update: `sources.html` partial

Add a "View" link to each source `<li>`:

- **URL sources**: `<a href="{{ source.url }}" target="_blank" rel="noopener noreferrer">View</a>`
- **Note/PDF sources**: `<a href="/api/documents/{{ doc_id }}/sources/{{ source.id }}/view" target="_blank" rel="noopener noreferrer">View</a>`

The partial already receives `source` objects; `doc_id` must be passed through (check if already available in template context; add to render call if not).

## Key Risks & Mitigations

| Risk | Mitigation |
| ---- | ---------- |
| `doc_id` not in template context for `sources.html` | Check existing render call in `GET /{doc_id}/sources`; add if missing |
| Note/PDF content is very large — slow page render | Content is stored text; no concern for prototype scale |
| URL source has `null` url field | Guard in template: only render URL link if `source.url` is not None |

## Out of Scope (confirmed)

- "Add Source" backend and UI — already fully implemented (URL / note / PDF tabs in document.html)
- Authentication/authorization beyond existing prototype behaviour
- PDF byte storage or in-browser PDF rendering — extracted text is displayed as text
- Duplicate URL warning UI — deferred per spec assumptions
