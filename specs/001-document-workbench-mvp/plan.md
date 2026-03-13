# Implementation Plan: Document Workbench MVP

**Branch**: `001-document-workbench-mvp` | **Date**: 2026-03-13 | **Spec**: docs/PRD.md

**Input**: Feature specification from `docs/PRD.md`

## Summary

Build the core AI Document Workbench MVP: a document-first AI collaboration tool where users
create documents, add trusted source materials to a Core Bucket, interact with the AI via
margin comments, and receive AI-generated suggestions in a "suggested" state that they
explicitly accept or reject. The underlying AI agent system uses Google ADK with a Root
coordinator dispatching to a Drafter sub-agent. Frontend is HTMX-driven with minimal JS.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x (async), asyncpg, Alembic, Jinja2
**Storage**: PostgreSQL (Docker container)
**Testing**: pytest (backend services only — TDD; no tests for frontend components or API endpoints)
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: web-service
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save
**Scale/Scope**: Demo/prototype — YAGNI; no new features without explicit user confirmation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify each principle before proceeding:

- [x] **I. Python + uv**: All new code is Python; uv used for deps
- [x] **II. TDD scope**: Tests planned for service layer only (not endpoints, not HTMX templates)
- [x] **III. No remote APIs in tests**: ADK/Gemini calls mocked in all service tests
- [x] **IV. Simplicity**: Scope confirmed — MVP only (no ripple effect, no web research, no multi-doc)
- [x] **V. Strong typing**: All function signatures use Pydantic/TypedDict; no plain dicts; no Any
- [x] **VI. Functional style**: Services are module-level functions; no unnecessary classes
- [x] **VII. Ruff**: ruff check + ruff format enforced before every save
- [x] **VIII. Containers**: PostgreSQL + FastAPI server run in Docker; docker-compose provided
- [x] **IX. Logging**: Every except block logs; all service operations emit log entries
- [x] **ADK architecture**: Root + Drafter agents only; matches docs/agents.md

**Constitution Check post-design**: Re-evaluate after Phase 1 (data-model.md + contracts/).

## MVP Scope

**In scope** (this plan):
- Document creation, listing, editing (markdown textarea)
- Core Bucket source ingestion: typed note, URL reference, PDF upload (text extraction)
- Margin comments on text selections → triggers Drafter Agent → creates Suggestion
- Suggested state: pending suggestions shown inline; accept commits to document, reject discards
- Single implicit workspace (no multi-doc, no workspace management UI)

**Explicitly deferred** (post-MVP, require explicit user confirmation to add):
- Web research / Holding Pen (PRD §5)
- Cascading Auto-Updates / Ripple Effect (PRD §6)
- Multi-Document Ecosystem (PRD §7)
- Contradiction detection between Core Bucket and General Research
- Document version history / git-like backend
- Knowledge Graph

## Project Structure

### Documentation (this feature)

```text
specs/001-document-workbench-mvp/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output
    ├── documents-api.md
    ├── sources-api.md
    └── suggestions-api.md
```

### Source Code (repository root)

```text
src/writer/
├── __init__.py
├── main.py                    # FastAPI app entry point
├── api/
│   ├── __init__.py
│   ├── documents.py           # Document CRUD endpoints
│   ├── sources.py             # Source ingestion endpoints
│   └── suggestions.py        # Comment submit + accept/reject endpoints
├── core/
│   ├── __init__.py
│   ├── config.py              # Settings (env vars via pydantic-settings)
│   ├── database.py            # Async SQLAlchemy engine + session factory
│   └── logging.py             # Structured logging setup
├── models/
│   ├── __init__.py
│   ├── db.py                  # SQLAlchemy ORM models
│   └── schemas.py             # Pydantic request/response schemas
├── services/
│   ├── __init__.py
│   ├── document_service.py    # Document CRUD logic (TDD)
│   ├── source_service.py      # Source management logic (TDD)
│   └── agent_service.py       # ADK agent orchestration (TDD, mocked in tests)
├── agents/
│   ├── __init__.py
│   ├── root_agent.py          # Root coordinator agent
│   └── drafter_agent.py       # Drafter sub-agent
└── templates/
    ├── base.html
    ├── index.html              # Document list
    ├── document.html           # Editor + sidebar
    └── partials/
        ├── suggestion.html     # HTMX partial — pending suggestion
        └── sources.html        # HTMX partial — source list

static/
└── style.css                  # Minimal CSS; no custom JS files

tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_document_service.py
│   ├── test_source_service.py
│   └── test_agent_service.py
└── integration/
    ├── __init__.py
    └── test_db.py

migrations/                    # Alembic migrations
docker-compose.yml
Dockerfile
.env.example
```

**Structure Decision**: Single-project web application. Frontend is server-rendered HTML via
Jinja2 + HTMX. No separate frontend build step. DB migrations managed by Alembic.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `agents/` sub-package | ADK agent definitions require dedicated module structure | Inline agent definition in services would couple business logic to ADK specifics |
