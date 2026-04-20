# Implementation Plan: Chapter-Scoped Sources and Snippets (Phase 1)

**Branch**: `017-chapter-scoped-research` | **Date**: 2026-04-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-chapter-scoped-research/spec.md`

## Summary

Add an organisational axis to the sources and snippets sidebars: each item can be tagged to zero or more chapters of its document. The chapter-snippet half is partially built (spec 016 already shipped `chapter_snippets`, plus assign/unassign/list-by-chapter services). This feature completes the snippet UI surface and adds the parallel source-side stack from scratch: a new `chapter_sources` join table, parallel service/API layer, and shared UI affordances — multi-select chapter picker in add/save flows, retroactive tag editing in list rows, and a per-pane filter control with three modes (all, document-level only, specific chapter) that defaults to the active chapter when no override is set.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, Jinja2, Alembic
**Storage**: PostgreSQL (Docker container) — one new table (`chapter_sources`); `chapter_snippets` already exists
**Testing**: pytest (service layer only — TDD; no tests for API endpoints or UI per Constitution II)
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: Web service (single FastAPI app, HTMX frontend)
**Performance Goals**: N/A — prototype/demo; one extra small query per pane render is the only added cost
**Constraints**: No remote API calls in tests; no plain dicts; no `Any`; ruff must pass; minimise JS (filter UI driven by HTMX `hx-get` on a `<select>`, no custom JS)
**Scale/Scope**: A single document is unlikely to exceed ~hundreds of sources / ~thousands of snippets across ~tens of chapters; standard B-tree indexes on the join tables are sufficient

## Constitution Check

- [x] **I. Python + uv**: All new code is Python; uv used for deps
- [x] **II. TDD scope**: Tests planned for service-layer functions (`source_service` chapter helpers, `snippet_service` chapter helpers, filter-list functions). No tests for endpoints or templates.
- [x] **III. No remote APIs in tests**: Feature has no remote-API surface (DB only). Mocks not needed.
- [x] **IV. Simplicity**: Scope confirmed against spec; no extras (no auto-tag, no semantic search, no bulk edit). Existing `chapter_snippets` table reused; we don't rename it for naming consistency with the user's spec wording (see research.md "Naming convention").
- [x] **V. Strong typing**: All new function signatures use Pydantic models or stdlib types; no plain dicts; no `Any`.
- [x] **VI. Functional style**: New service functions are module-level async functions, parallel to the existing `chapter_service` and `snippet_service` modules. No new classes beyond the SQLAlchemy ORM model and Pydantic schemas.
- [x] **VII. Ruff**: Run `ruff check --fix && ruff format` on all touched files before save.
- [x] **VIII. Containers**: No infra changes — uses the existing PostgreSQL container.
- [x] **IX. Logging**: Every new service function logs operation start + success/failure at INFO/ERROR. No silent excepts.
- [x] **ADK architecture**: No agent changes — feature is pure CRUD + UI.

No violations to record in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/017-chapter-scoped-research/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── source-chapter-api.md
│   └── snippet-chapter-api.md
├── checklists/
│   └── requirements.md  # spec quality checklist (already passes)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

This feature touches the existing single-project layout — no new top-level directories.

```text
src/writer/
├── api/
│   ├── chapters.py        # add: source ↔ chapter assign/unassign endpoints (mirror existing snippet ones)
│   ├── snippets.py        # extend: SnippetCreate accepts chapter_ids; list endpoint gains scope param
│   └── sources.py         # extend: add-source form accepts chapter_ids; list endpoint gains chapter_id + scope
├── models/
│   ├── db.py              # add: ChapterSource ORM model (chapter_snippets already exists)
│   └── schemas.py         # extend: SnippetCreate.chapter_ids, SourceResponse.chapter_ids,
│                          #         SnippetResponse.chapter_ids; new ChapterAssociationUpdate schema
├── services/
│   ├── snippet_service.py # extend: create_snippet accepts chapter_ids; new list-with-scope helper;
│   │                      #         new replace_snippet_chapter_associations helper
│   └── source_service.py  # add: assign/unassign/list-by-chapter helpers (mirror snippet_service);
│                          #     new replace_source_chapter_associations helper;
│                          #     extend list_sources to accept scope filter
├── templates/
│   ├── document.html      # add: chapter picker in 3 add-source forms; filter <select> on source list & snippet bank
│   └── partials/
│       ├── sources.html       # add: chapter chips + tag-edit popover
│       ├── snippet_bank.html  # add: filter <select> at top of pane
│       ├── snippet_card.html  # add: chapter chips + tag-edit popover
│       ├── source_filter.html # NEW: filter <select> partial reused in source list header
│       └── chapter_picker.html# NEW: <details>-based multi-select used in add/save and edit popovers
└── core/                  # no changes

migrations/versions/
└── <timestamp>_add_chapter_sources.py  # NEW: create chapter_sources table + indexes

tests/unit/
├── test_source_service.py   # add: associate/unassociate/list-by-scope tests
└── test_snippet_service.py  # add: create-with-chapters; list-by-scope (doc-level + all + specific) tests
```

**Structure Decision**: Single project (`src/writer/`), reusing the existing `api/`, `models/`, `services/`, `templates/` layout. The work splits cleanly along the existing service modules (`source_service.py`, `snippet_service.py`) and adds one ORM table + one Alembic migration. UI work is two reusable template partials (`chapter_picker.html`, `source_filter.html`) wired into the existing `document.html` and the existing source/snippet partials. No new JS files — the picker is plain `<details>` + checkbox elements with HTMX `hx-post`/`hx-delete`, and the filter is a `<select>` with `hx-get`.

## Complexity Tracking

> No violations to track.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| _none_    | —          | —                                    |
