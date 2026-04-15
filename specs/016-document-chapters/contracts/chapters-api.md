# API Contract: Chapter Endpoints

**Feature**: 016-document-chapters
**Base path**: `/api/documents/{doc_id}/chapters`

## Endpoints

### POST /api/documents/{doc_id}/chapters

Create a new chapter at the end of the document.

**Request** (JSON):

```json
{
  "title": "Chapter Title",
  "brief": "Optional planning description"
}
```

- `title`: string, optional (defaults to "Untitled Chapter")
- `brief`: string, optional (defaults to null)

**Response** (201 Created):

- HTMX request (`HX-Request` header): Returns HTML partial of the new chapter card + updated TOC
- JSON request: Returns ChapterResponse

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "title": "Chapter Title",
  "brief": "Optional planning description",
  "brief_visible": true,
  "content": "",
  "position": 2,
  "created_at": "2026-04-14T...",
  "updated_at": "2026-04-14T..."
}
```

**Side effects**: Rebuilds Document.content cache.

---

### GET /api/documents/{doc_id}/chapters

List all chapters for a document, ordered by position.

**Response** (200 OK):

- HTMX request: Returns HTML — full chapter list with TOC
- JSON request: Returns `ChapterResponse[]`

---

### GET /api/documents/{doc_id}/chapters/{chapter_id}

Get a single chapter.

**Response** (200 OK):

- HTMX request: Returns HTML partial of the chapter card (rendered content, title, brief)
- JSON request: Returns ChapterResponse

---

### PUT /api/documents/{doc_id}/chapters/{chapter_id}

Update chapter content, title, or brief.

**Request** (JSON):

```json
{
  "title": "Updated Title",
  "content": "Updated markdown content",
  "brief": "Updated brief"
}
```

All fields optional — only provided fields are updated.

**Response** (200 OK): ChapterResponse (JSON) or HTML partial (HTMX)

**Side effects**: Rebuilds Document.content cache when title or content changes.

---

### DELETE /api/documents/{doc_id}/chapters/{chapter_id}

Delete a chapter and recompact sibling positions.

**Response** (200 OK):

- HTMX request: Returns updated chapter list HTML + TOC (or empty state if no chapters remain)
- JSON request: Returns 204 No Content

**Side effects**: CASCADE deletes chapter_snippets rows. Rebuilds Document.content cache. Recompacts remaining chapter positions.

---

### PATCH /api/documents/{doc_id}/chapters/{chapter_id}/position

Reorder a chapter.

**Request** (JSON):

```json
{
  "position": 0
}
```

- `position`: integer, the new 0-based position

**Response** (200 OK):

- HTMX request: Returns updated full chapter list HTML + TOC (OOB swap)
- JSON request: Returns ChapterResponse[]

**Side effects**: Adjusts positions of affected siblings. Rebuilds Document.content cache.

---

### PATCH /api/documents/{doc_id}/chapters/{chapter_id}/brief-visibility

Toggle brief visibility.

**Request** (JSON):

```json
{
  "brief_visible": false
}
```

**Response** (200 OK): ChapterResponse (JSON) or chapter card HTML (HTMX)

---

## Snippet-Chapter Association Endpoints

### POST /api/documents/{doc_id}/chapters/{chapter_id}/snippets/{snippet_id}

Associate a snippet with a chapter.

**Response** (201 Created): Empty body

**Side effects**: Creates chapter_snippets row. Idempotent — no error if association already exists.

---

### DELETE /api/documents/{doc_id}/chapters/{chapter_id}/snippets/{snippet_id}

Remove a snippet's association with a chapter.

**Response** (204 No Content): Empty body

**Side effects**: Deletes chapter_snippets row. The snippet itself is not deleted.

---

### GET /api/documents/{doc_id}/snippets?chapter_id={chapter_id}

List snippets filtered by chapter (modified existing endpoint).

**Query params**:

- `chapter_id` (optional UUID): Filter to snippets associated with this chapter
- If omitted: Returns all snippets for the document (existing behaviour)

**Response** (200 OK): Existing SnippetResponse[] or snippet_bank.html (HTMX)

## Pydantic Schemas

### ChapterCreate

```
title: str = "Untitled Chapter"
brief: str | None = None
```

### ChapterUpdate

```
title: str | None = None
content: str | None = None
brief: str | None = None
```

### ChapterResponse

```
id: UUID
document_id: UUID
title: str
brief: str | None
brief_visible: bool
content: str
position: int
created_at: datetime
updated_at: datetime
```

### ChapterPositionUpdate

```
position: int
```

### ChapterBriefVisibilityUpdate

```
brief_visible: bool
```
