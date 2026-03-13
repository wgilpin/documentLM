# Contract: Comments & Suggestions API

## Comments — trigger AI drafting

### POST /api/documents/{document_id}/comments

Submit a margin comment on a text selection. The server:
1. Validates the selection against the current document content.
2. Creates a `Comment` record.
3. Invokes the Drafter Agent (via `agent_service`) with the comment + Core Bucket sources.
4. Creates a `Suggestion` record (status: `pending`).
5. Returns an HTMX partial (HTML) to swap into the suggestion panel.

**Request body**:
```json
{
  "selection_start": 42,
  "selection_end": 97,
  "selected_text": "initial draft of this section",
  "body": "Expand this paragraph with three concrete examples."
}
```

**Validation**:
- `selection_start` >= 0
- `selection_end` > `selection_start`
- `selected_text` MUST match `document.content[selection_start:selection_end]` exactly
- `body` MUST be non-empty

**Response 201** (JSON — used by non-HTMX clients):
```json
{
  "comment": {
    "id": "uuid",
    "document_id": "uuid",
    "selection_start": 42,
    "selection_end": 97,
    "selected_text": "initial draft of this section",
    "body": "Expand this paragraph with three concrete examples.",
    "status": "open",
    "created_at": "2026-03-13T10:00:00Z"
  },
  "suggestion": {
    "id": "uuid",
    "comment_id": "uuid",
    "original_text": "initial draft of this section",
    "suggested_text": "initial draft of this section...[expanded]",
    "status": "pending",
    "created_at": "2026-03-13T10:00:00Z"
  }
}
```

**HTMX response** (when `HX-Request: true` header present): returns `partials/suggestion.html`
rendered with the suggestion data, swapped into `#suggestion-panel`.

**Error 404**: document not found
**Error 409**: `selected_text` does not match document content (document has been edited)
**Error 422**: validation failure
**Error 502**: Agent invocation failed (logged; user sees error message in partial)

---

## Suggestions — accept or reject

### GET /api/documents/{document_id}/suggestions

List all `pending` suggestions for a document.

**Response 200**:
```json
[
  {
    "id": "uuid",
    "comment_id": "uuid",
    "original_text": "...",
    "suggested_text": "...",
    "status": "pending",
    "created_at": "2026-03-13T10:00:00Z"
  }
]
```

---

### POST /api/suggestions/{suggestion_id}/accept

Accept a suggestion. The server:
1. Retrieves the suggestion and its parent comment (and document).
2. Verifies `document.content[selection_start:selection_end] == suggestion.original_text`
   (stale check).
3. Replaces the text span in `document.content` with `suggestion.suggested_text`.
4. Sets `suggestion.status = accepted`, `comment.status = resolved`.
5. Returns the updated document content (HTMX target: `#document-content`).

**Response 200** (JSON): full `DocumentResponse`

**HTMX response**: returns `partials/document_content.html` swapped into `#document-content`;
also OOB-swaps `#suggestion-{id}` out of the DOM.

**Error 404**: suggestion not found
**Error 409**: suggestion is stale (document was edited after suggestion was created)
**Error 422**: suggestion is not in `pending` status

---

### POST /api/suggestions/{suggestion_id}/reject

Reject a suggestion. Sets `suggestion.status = rejected`, `comment.status = resolved`.

**Response 200** (JSON):
```json
{ "id": "uuid", "status": "rejected" }
```

**HTMX response**: returns empty string; suggestion panel item removed via `hx-swap="outerHTML"`.

**Error 404**: suggestion not found
**Error 422**: suggestion is not in `pending` status
