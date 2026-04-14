# API Contracts: Bounded Generation & Curation Workflow

**Feature**: 015-bounded-generation
**Date**: 2026-04-13
**Style**: FastAPI JSON + HTMX partial responses

All endpoints require an authenticated session (cookie-based, matching existing auth pattern).

---

## Snippets

### Create Snippet

```http
POST /api/documents/{doc_id}/snippets
Content-Type: application/json
```

**Request body** (`SnippetCreate`):

```json
{
  "source_id": "uuid | null",
  "text": "The highlighted passage text",
  "char_offset": 1234,
  "note": "optional note",
  "tag": "optional tag"
}
```

**Response 201** (`SnippetResponse`):

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "source_id": "uuid | null",
  "text": "The highlighted passage text",
  "char_offset": 1234,
  "note": null,
  "tag": null,
  "source_title": "My PDF Title",
  "created_at": "2026-04-13T12:00:00Z"
}
```

**HTMX response**: If `HX-Request` header present, returns a rendered `partials/snippet_card.html` partial instead.

**Errors**: 404 if `doc_id` not found or not owned by user.

---

### List Snippets

```http
GET /api/documents/{doc_id}/snippets
```

**Response 200**: `list[SnippetResponse]` ordered by `created_at DESC`.

**HTMX response**: If `HX-Request` header, returns rendered `partials/snippet_bank.html`.

---

### Delete Snippet

```http
DELETE /api/snippets/{snippet_id}
```

**Response 204**: No content.

**HTMX response**: If `HX-Request`, returns empty `200` with `HX-Trigger: snippetDeleted` so the snippet card removes itself via `hx-swap="outerHTML"`.

**Errors**: 404 if snippet not found or not owned by user.

---

### Update Snippet Note/Tag

```http
PATCH /api/snippets/{snippet_id}
Content-Type: application/json
```

**Request body** (`SnippetUpdate`):

```json
{
  "note": "updated note",
  "tag": "updated tag"
}
```

**Response 200**: `SnippetResponse`.

**HTMX response**: If `HX-Request`, returns rendered `partials/snippet_card.html`.

---

## Source Document View

### Get Source Markdown Content

```http
GET /api/sources/{source_id}/view
```

**Response 200**: `text/html` — Server-rendered markdown as HTML fragment, wrapped in a `<div id="source-view">` with per-paragraph `data-offset` attributes for anchor navigation.

**HTMX usage**: Called via `hx-get` when user clicks a source in Document View tab. Swaps into `#source-view-container`.

**Errors**: 404 if source not found or not owned by user.

---

## Semantic Search

### Search Corpus

```http
GET /api/documents/{doc_id}/search?q={query}&top_k=10
```

**Query params**:

- `q` (required): search query string
- `top_k` (optional, default 10, max 20): number of results

**Response 200** (`SearchResponse`):

```json
{
  "query": "first hand accounts of health impacts",
  "results": [
    {
      "text": "Residents reported...",
      "source_id": "uuid",
      "source_title": "Interview Transcripts 2024"
    }
  ]
}
```

**HTMX response**: If `HX-Request`, returns rendered `partials/search_results.html` with one result card per item, each card having a checkbox form to POST to `/api/documents/{doc_id}/snippets`.

**Errors**: 404 if doc not found; 400 if `q` is empty.

---

## Bounded Generation

### Generate Bounded Text

```http
POST /api/documents/{doc_id}/bounded-generate
Content-Type: application/json
```

**Request body** (`BoundedGenerateRequest`):

```json
{
  "snippet_ids": ["uuid", "uuid"],
  "intent": "Synthesise these quotes to highlight a contradiction...",
  "cursor_context": "## Climate Impact\n\n"
}
```

The full document content is fetched server-side from the document record — the client does not need to send it. `cursor_context` is the heading or surrounding paragraph at the insertion point, used to identify which section the AI is writing into.

**Validation**:

- `intent` must be non-empty (min 1 char, max 500 chars) — 422 if violated. If the user does not want to provide intent, they dismiss the UI and type directly.
- `snippet_ids` may be empty — snippets are optional.

**Response 200** (`BoundedGenerationResponse`):

```json
{
  "suggested_text": "The generated paragraph text..."
}
```

**HTMX response**: If `HX-Request`, returns rendered `partials/bounded_suggestion.html` containing the suggested text and JavaScript to trigger the editor's `insertBoundedSuggestion(text)` function.

**Errors**:

- 404: document not found
- 422: intent is empty
- 502: LLM/agent error

---

## Router Registration

New routers added to `writer/main.py`:

- `snippets_router` from `writer/api/snippets.py` — no prefix (paths above are full)
- Search endpoint added to a new `writer/api/search.py` router
- Bounded generation endpoint added to a new `writer/api/generation.py` router
