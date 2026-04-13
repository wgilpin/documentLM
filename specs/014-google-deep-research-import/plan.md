# Implementation Plan: Import Google Deep Research

**Branch**: `014-google-deep-research-import` | **Date**: 2026-04-12 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/014-google-deep-research-import/spec.md`

## Summary

Allow users to import a Google Deep Research export (Markdown file) and automatically add the document body and all cited URLs as sources in their workspace. A new `deep_research_service` parses the Markdown and extracts references; a new API endpoint handles the file upload and batch-creates sources using the existing ingestion pipeline. The UI adds a button + dialog in the sources panel — no DB schema changes required.

## Technical Context

**Language/Version**: Python 3.13+  
**Package Manager**: uv  
**Primary Dependencies**: FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg  
**Storage**: PostgreSQL (Docker container) — no schema changes  
**Testing**: pytest (service layer TDD; no tests for API endpoints or templates)  
**Type Checking**: mypy (strict), ruff (linting + formatting)  
**Target Platform**: Docker containers  
**Project Type**: Web service (FastAPI + HTMX)  
**Performance Goals**: N/A — prototype/demo  
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save  
**Scale/Scope**: Demo/prototype — no new features beyond spec

## Constitution Check

- [x] **I. Python + uv**: All new code is Python; uv used for deps
- [x] **II. TDD scope**: Tests written for `deep_research_service` only; API endpoint and templates are untested per policy
- [x] **III. No remote APIs in tests**: Parsing is pure string processing — no external calls at all
- [x] **IV. Simplicity**: Scope confirmed; reuses existing `add_source` + `run_indexing`; no new DB tables
- [x] **V. Strong typing**: `ExtractedReference` and `DeepResearchParseResult` as `TypedDict`; all function signatures typed
- [x] **VI. Functional style**: Two pure functions in `deep_research_service`; no classes
- [x] **VII. Ruff**: ruff check + ruff format applied before every save
- [x] **VIII. Containers**: No infrastructure changes; existing docker-compose unchanged
- [x] **IX. Logging**: All service operations and error paths will emit structured log entries
- [x] **ADK architecture**: No new agents introduced

## Project Structure

### Documentation (this feature)

```text
specs/014-google-deep-research-import/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── import-deep-research.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code Changes

```text
src/writer/
├── services/
│   └── deep_research_service.py     # NEW — Markdown parser + URL extractor
├── api/
│   └── sources.py                   # MODIFIED — add import endpoint
└── templates/
    └── document.html                # MODIFIED — add import button + dialog

tests/unit/
└── test_deep_research_service.py    # NEW — TDD tests for service
```

**No migrations. No new models. No new enums.**

## Implementation Approach

### Service: `deep_research_service.py`

Two pure functions:

**`extract_urls(markdown: str) -> list[ExtractedReference]`**

- Regex: `\[([^\]]+)\]\((https?://[^)]+)\)` across entire document
- Deduplicate by URL (preserve first occurrence)
- Title fallback: if display text == URL, use domain name extracted from URL
- Returns `list[ExtractedReference]` (TypedDict: `title: str`, `url: str`)

**`parse_markdown_document(content: str, filename: str) -> DeepResearchParseResult`**

- Extract title from first H1/H2/H3 heading (`^#{1,3}\s+(.+)`) or fall back to `filename` (strip `.md`)
- Return full `content` as body
- Call `extract_urls` for references
- Returns `DeepResearchParseResult` (TypedDict: `title`, `body`, `references`)

### API Endpoint

`POST /api/documents/{doc_id}/sources/import-deep-research`

1. Read uploaded file bytes; decode as UTF-8
2. Call `parse_markdown_document(content, filename)`
3. If body is empty and references is empty → return 422 with inline error HTML
4. Create document body source: `add_source(db, SourceCreate(source_type=note, title=..., content=body))`
5. For each reference: `add_source(db, SourceCreate(source_type=url, title=..., url=..., content=""))`
   - `add_source` silently skips duplicates (existing behaviour)
6. `await db.commit()`
7. Enqueue `run_indexing` background task for each newly created source
8. Return concatenated `partials/sources.html` fragments (HTMX) or JSON

### UI Changes (`document.html`)

- Add "Import Deep Research" button below the `<details>` accordion in the sources panel
- Add `<dialog id="import-deep-research-dialog">` containing:
  - Step-by-step instructions (static text)
  - `<div id="import-deep-research-error">` for inline errors
  - `<form>` with `<input type="file" accept=".md">` posting via HTMX to the import endpoint
  - `hx-target="#source-list"`, `hx-swap="beforeend"`, `hx-encoding="multipart/form-data"`
  - On success: close dialog via `hx-on::after-request`
  - On error (`422`): HTMX retargets `#import-deep-research-error` — modal stays open

## Complexity Tracking

No constitution violations — nothing to justify here.
