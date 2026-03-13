# Contract: Sources API

Base path: `/api/documents/{document_id}/sources`

Sources are scoped to a document for MVP. All timestamps are ISO 8601 UTC strings.

---

## GET /api/documents/{document_id}/sources

List all sources for a document.

**Response 200**:
```json
[
  {
    "id": "uuid",
    "document_id": "uuid",
    "source_type": "note",
    "title": "My Research Notes",
    "content": "Key finding: ...",
    "url": null,
    "created_at": "2026-03-13T10:00:00Z"
  }
]
```

---

## POST /api/documents/{document_id}/sources

Add a source to the Core Bucket.

**Content-Type**: `application/json` for `url` and `note`; `multipart/form-data` for `pdf`.

### note or url type (JSON):
```json
{
  "source_type": "note",
  "title": "My Notes",
  "content": "The key point is...",
  "url": null
}
```

```json
{
  "source_type": "url",
  "title": "Wikipedia: Markdown",
  "content": "Optional summary by user",
  "url": "https://en.wikipedia.org/wiki/Markdown"
}
```

### pdf type (multipart/form-data):
```
source_type=pdf
title=My Paper
file=<binary PDF>
```

Text is extracted server-side via `pypdf`; the extracted text is stored in `content`.

**Validation**:
- `source_type` MUST be one of `url | pdf | note`
- `title`: non-empty, max 255 chars
- `source_type=url`: `url` MUST be a valid HTTP/HTTPS URL
- `source_type=pdf`: `file` MUST be present and be a valid PDF
- `source_type=note`: `content` MUST be non-empty

**Response 201**:
```json
{
  "id": "uuid",
  "document_id": "uuid",
  "source_type": "note",
  "title": "My Notes",
  "content": "The key point is...",
  "url": null,
  "created_at": "2026-03-13T10:00:00Z"
}
```

**Error 404**: document not found
**Error 422**: validation failure

---

## DELETE /api/documents/{document_id}/sources/{source_id}

Remove a source from the Core Bucket.

**Response 204**: No content

**Error 404**: source or document not found

---

## HTMX partial

| Method | Path | Returns |
|---|---|---|
| POST | `/api/documents/{id}/sources` | `partials/sources.html` — updated source list item (swapped into `#source-list`) |
