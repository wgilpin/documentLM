# UI Contract: Source Management

**Branch**: `002-source-management` | **Date**: 2026-03-13

This document defines the HTMX-driven UI contracts for source management: what the server returns for each interaction and what elements the templates must provide.

---

## Existing Endpoints (unchanged)

All backend routes are pre-existing. No new routes are introduced.

| Method | Path | Used for |
|--------|------|---------|
| GET | `/api/documents/{doc_id}/sources` | Load source list on page open |
| POST | `/api/documents/{doc_id}/sources` | Add a new source |
| DELETE | `/api/documents/{doc_id}/sources/{source_id}` | Remove a source |

---

## Template Contract: Source List (`#source-list`)

The `<ul id="source-list">` element in [document.html](../../src/writer/templates/document.html) is the target for all source list operations.

### On page load

```
GET /api/documents/{doc_id}/sources
HX-Request: true

→ If sources exist:
   One <li> fragment per source (rendered from partials/sources.html)

→ If no sources:
   <li class="source-empty-state">No sources added yet.</li>
```

### On source added (success)

```
POST /api/documents/{doc_id}/sources
Content-Type: multipart/form-data
HX-Request: true

→ 200 OK
   hx-swap="beforeend" on #source-list
   One <li> fragment for the new source (partials/sources.html)
```

### On source added (error)

```
POST /api/documents/{doc_id}/sources
HX-Request: true

→ 422 Unprocessable Entity
   Content: <div class="source-error">Error message here.</div>
   hx-target="#source-error-{type}" (e.g. #source-error-pdf)
   hx-swap="innerHTML"
```

Each add form must have a sibling error container:
```html
<div id="source-error-note" class="source-error-container"></div>
<div id="source-error-url"  class="source-error-container"></div>
<div id="source-error-pdf"  class="source-error-container"></div>
```

### On source deleted (success)

```
DELETE /api/documents/{doc_id}/sources/{source_id}
HX-Request: true

→ 200 OK, empty body
   hx-target="#source-{source_id}"
   hx-swap="outerHTML"
   → Removes the <li> from DOM
```

---

## Template Contract: Source Item (`partials/sources.html`)

Each source is rendered as a `<li>` with:

| Element | Content |
|---------|---------|
| Type badge | `source.source_type.value` (url / pdf / note) |
| Title | `source.title` |
| Date | `source.created_at` formatted as `Mon DD, YYYY` |
| Delete button | HTMX delete trigger; `hx-confirm` before removal |

### HTML structure

```html
<li class="source-item" id="source-{{ source.id }}">
  <div class="source-meta">
    <span class="type-badge">{{ source.source_type.value }}</span>
    <span class="source-title">{{ source.title }}</span>
    <span class="source-date">{{ source.created_at.strftime('%b %d, %Y') }}</span>
  </div>
  <button class="btn btn-danger btn-xs"
          hx-delete="/api/documents/{{ source.document_id }}/sources/{{ source.id }}"
          hx-target="#source-{{ source.id }}"
          hx-swap="outerHTML"
          hx-confirm="Remove this source?">×</button>
</li>
```

---

## API Behaviour Changes

### PDF error surface

**Current**: `add_source_pdf` catches PDF parse exceptions and silently stores `content=""`. The endpoint returns 200 with a source that has empty content.

**Required**: When `pypdf.PdfReader` raises an exception during parsing, the endpoint MUST return HTTP 422 with a plain-text or HTML error body instead of silently succeeding.

The service function should raise a new `PdfParseError` exception; the API handler should catch it and return 422.

### Empty state response

**Current**: `list_sources` returns an empty list; the HTMX `innerHTML` swap results in an empty `<ul>`.

**Required**: When the list is empty, the GET endpoint (HTMX path) returns an empty-state `<li>` element instead of empty HTML.

---

## Section label change

The sidebar heading "Core Bucket" in [document.html:39](../../src/writer/templates/document.html) should be renamed to **"Sources"**.
