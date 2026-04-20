# Contract: Snippet ↔ Chapter API

The single-association endpoints already exist from spec-016 and remain unchanged. This feature adds tag-on-create, retroactive replace, and a richer filter mode to the list endpoint.

## Tagging on save

`POST /api/documents/{doc_id}/snippets` — **extended** (existing endpoint)

The request schema (`SnippetCreate`) gains a `chapter_ids` field.

**Request (JSON)**:

```json
{
  "source_id": "<uuid|null>",
  "text": "...",
  "char_offset": 0,
  "note": null,
  "tag": null,
  "chapter_ids": ["<uuid>", "<uuid>"]
}
```

`chapter_ids` is optional; default `[]` = document-level.

**Response**:

- 201 Created — `SnippetResponse` JSON, or rendered `partials/snippet_card.html` when `HX-Request: true`. Response includes `chapter_ids: list[UUID]`.
- 404 — document not found.
- 422 — one or more chapter UUIDs do not belong to `doc_id`.

## Retroactive replace

`PUT /api/documents/{doc_id}/snippets/{snippet_id}/chapters` — **NEW**

Replaces the full set of chapter associations for one snippet.

**Request (JSON)**:

```json
{ "chapter_ids": ["<uuid>", "<uuid>"] }
```

`chapter_ids` may be empty (= demote to document-level).

**Response**:

- 200 OK — `SnippetResponse` JSON, or rendered `partials/snippet_card.html` when `HX-Request: true`.
- 404 — snippet not found or not owned by current user.
- 422 — one or more chapter UUIDs do not belong to the snippet's document.

## Filter on list

`GET /api/documents/{doc_id}/snippets` — **extended** (existing endpoint)

Replaces the existing `chapter_id` query parameter with the broader `scope` parameter.

**Query parameters**:

| Param  | Values                                                                | Default |
|--------|-----------------------------------------------------------------------|---------|
| scope  | `all` \| `doc-level` \| `chapter:<uuid>`                              | `all`   |

**Backward-compatibility**: The existing `chapter_id=<uuid>` parameter is treated as an alias for `scope=chapter:<uuid>` for one release. Removed when no internal callers remain.

**Response**:

- 200 OK — `list[SnippetResponse]` JSON, or rendered `partials/snippet_bank.html` when `HX-Request: true`. Each response includes `chapter_ids`.
- Stale `scope=chapter:<uuid>` silently degrades to `scope=all`; logged at WARNING.

## Single-association endpoints (UNCHANGED — exist from spec-016)

`POST /api/documents/{doc_id}/chapters/{chapter_id}/snippets/{snippet_id}` — exists, unchanged.
`DELETE /api/documents/{doc_id}/chapters/{chapter_id}/snippets/{snippet_id}` — exists, unchanged.

These remain available; the Phase 1 UI uses the new bulk replace endpoint instead.
