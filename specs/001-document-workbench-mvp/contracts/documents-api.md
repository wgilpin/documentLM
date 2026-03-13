# Contract: Documents API

Base path: `/api/documents`

All request/response bodies are JSON. All timestamps are ISO 8601 UTC strings.

---

## GET /api/documents

List all documents (newest first).

**Response 200**:
```json
[
  {
    "id": "uuid",
    "title": "My Research Doc",
    "created_at": "2026-03-13T10:00:00Z",
    "updated_at": "2026-03-13T11:30:00Z"
  }
]
```

---

## POST /api/documents

Create a new document.

**Request body**:
```json
{ "title": "My Research Doc", "content": "" }
```

**Validation**:
- `title`: non-empty string, max 255 chars
- `content`: optional, default `""`

**Response 201**:
```json
{
  "id": "uuid",
  "title": "My Research Doc",
  "content": "",
  "created_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:00:00Z"
}
```

**Error 422**: validation failure (title empty / too long)

---

## GET /api/documents/{document_id}

Fetch a single document with full content.

**Response 200**: Same shape as POST 201 response.

**Error 404**: document not found

---

## PUT /api/documents/{document_id}

Update a document's title and/or content (auto-save on edit).

**Request body** (all fields optional):
```json
{ "title": "Updated Title", "content": "# Heading\n\nBody text" }
```

**Response 200**: Full document response (same shape as GET single)

**Error 404**: document not found
**Error 422**: validation failure

---

## DELETE /api/documents/{document_id}

Delete a document and all associated sources, comments, and suggestions.

**Response 204**: No content

**Error 404**: document not found

---

## UI Routes (HTMX, returns HTML)

| Method | Path | Returns |
|---|---|---|
| GET | `/` | `index.html` — document list |
| GET | `/documents/new` | `document.html` — blank editor |
| GET | `/documents/{id}` | `document.html` — editor populated |
