# Research: Document Sources Pane – View and Add Sources

**Branch**: `008-view-add-sources` | **Date**: 2026-03-17

## Key Finding: "Add Source" Already Implemented

The codebase already contains a full "Add Source" UI and backend:

- **Three tabs** in the document page: Note (paste text), URL, PDF — all functional
- **Endpoints**: `POST /{doc_id}/sources` handles all three types
- **Service layer**: `add_source()`, `add_source_pdf()` fully implemented
- **Source types**: `SourceType` enum has `url`, `pdf`, `note` — "note" is the "paste text" case

**Decision**: No new "Add Source" work is needed. Only the "View source" feature is new.

---

## Decision 1: View Endpoint for URL Sources

**Decision**: For URL sources, render a direct `<a target="_blank">` link in the template — no new endpoint needed. The URL is already stored in `source.url`.

**Rationale**: Zero new backend code; the URL is already known. A server-side redirect adds a round-trip with no benefit.

**Alternatives considered**: A redirect endpoint (`/sources/{id}/view` → 302 to URL). Rejected as unnecessary complexity.

---

## Decision 2: View Endpoint for Note and PDF Sources

**Decision**: Add a new `GET /{doc_id}/sources/{source_id}/view` endpoint that returns a simple HTML page displaying the stored `content` text. Served with `text/html` content type.

**Rationale**: Note and PDF sources store extracted text in `content` (PDFs have their text extracted by pypdf at add-time). A new tab needs a URL to open — a lightweight render endpoint is the minimal solution.

**Alternatives considered**:
- Serve raw text (`text/plain`): opens as a plain file in browser but loses any formatting context. Rejected for UX.
- Store raw PDF bytes and serve as `application/pdf`: would require schema change and additional storage. Rejected — extracted text is sufficient and already stored.

---

## Decision 3: "View" Button Placement in Template

**Decision**: Add a "View" link next to the existing "Delete" button in `sources.html` partial. For URL sources: `<a href="{url}" target="_blank">View</a>`. For note/pdf sources: `<a href="/api/documents/{doc_id}/sources/{source_id}/view" target="_blank">View</a>`.

**Rationale**: Consistent placement with existing delete action; requires only template changes for URL type, plus one new endpoint for note/pdf types.

**Alternatives considered**: A "View" button that triggers HTMX to fetch content into a modal. Rejected — the spec says "open in new tab", and HTMX modals would require JS or additional complexity.

---

## Decision 4: No New DB Schema

**Decision**: No database schema changes are required for this feature.

**Rationale**: All required data (`url`, `content`, `source_type`) is already stored in the `sources` table. The view endpoint reads existing columns only.

---

## Decision 5: Service Layer for View

**Decision**: Add a `get_source(db, source_id)` service function that fetches a single source by ID, returning `SourceResponse`. The API endpoint calls this function.

**Rationale**: Follows existing service-layer pattern; keeps DB queries out of API handlers; enables unit testing.

---

## Summary of New Work

| Item | Type | Notes |
|------|------|-------|
| `GET /{doc_id}/sources/{source_id}/view` | New API endpoint | Returns HTML page with source content |
| `get_source(db, source_id)` | New service function | Fetches single source; TDD |
| `templates/partials/source_view.html` | New template | Simple page rendering source content |
| `sources.html` partial | Update | Add "View" link to each source item |
| "Add Source" backend | No change | Already fully implemented |
| "Add Source" UI | No change | Already fully implemented (Note/URL/PDF tabs) |
