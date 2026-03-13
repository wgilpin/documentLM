# Research: Source Management

**Branch**: `002-source-management` | **Date**: 2026-03-13

## Summary

No external research required. The backend (service layer, API, data model) is **already fully implemented**. This feature is primarily a UI/template enhancement to surface the existing backend capabilities properly.

## Current Implementation Audit

### What exists

| Component | File | Status |
|-----------|------|--------|
| ORM model (`Source`) | `src/writer/models/db.py:43-58` | ✅ Complete |
| Pydantic schemas (`SourceCreate`, `SourceResponse`) | `src/writer/models/schemas.py:39-56` | ✅ Complete |
| Service layer (`add_source`, `add_source_pdf`, `list_sources`, `delete_source`) | `src/writer/services/source_service.py` | ✅ Complete |
| API endpoints (GET list, POST add, DELETE) | `src/writer/api/sources.py` | ✅ Complete |
| Source item partial (type badge + title + delete button) | `src/writer/templates/partials/sources.html` | ⚠️ Missing date |
| Sources panel in document view (sidebar with add tabs) | `src/writer/templates/document.html:38-111` | ⚠️ See gaps below |

### Gaps vs. specification

| Spec Requirement | Gap | Resolution |
|-----------------|-----|------------|
| FR-002: Show date added | `partials/sources.html` shows type + title only; `created_at` is in `SourceResponse` but not rendered | Add date to partial template |
| FR-003: Empty state message | `#source-list` is empty when no sources exist; no message shown | Server returns empty-state HTML when list is empty |
| FR-009–011: Inline validation errors | Form submission failures (server-side) are silent; HTML5 `required`/`type="url"` catches client-side cases | Add HTMX error handling + server-side error partial |
| Cosmetic: section title | Sidebar section heading reads "Core Bucket" | Rename to "Sources" |

### What does NOT need to be built

- No new database migrations (schema unchanged)
- No new service functions (CRUD is complete)
- No new API endpoints (routes are complete)
- No new Pydantic schemas

## Decisions

### Decision 1: Empty state delivery

**Decision**: Modify the `list_sources` endpoint to return an empty-state `<li>` element when no sources exist, rather than empty HTML.

**Rationale**: Keeps the empty state server-rendered and consistent with HTMX swap. No JS required.

**Alternative considered**: Client-side detection with HTMX `hx-on::after-request` script — rejected because it requires custom JS, violating the constitution's minimize-JS principle.

### Decision 2: Validation error display

**Decision**: For server-side errors (PDF parse failure, URL validation failure), the API returns an `<div class="error">` HTML fragment when an HTMX request fails. HTMX `hx-target` for errors uses an `#error-{type}` element near each form.

**Rationale**: HTMX supports `hx-swap-oob` for out-of-band swaps; a dedicated error element per form keeps error messaging inline without JS.

**Alternative considered**: HTTP 422 response with JSON — renders nothing in the UI without custom JS error handling; rejected.

### Decision 3: Date formatting

**Decision**: Format `created_at` in the Jinja2 template using the `strftime` filter (e.g., `%b %d, %Y`). No client-side formatting needed.

**Rationale**: Server-rendered, no JS, consistent with existing template patterns.
