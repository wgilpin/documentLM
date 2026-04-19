# Contract: Source ↔ Chapter API

All endpoints require an authenticated session (cookie-based, per existing project pattern). All return both JSON (default) and HTML partials when `HX-Request: true` is set.

## Tagging on add

`POST /api/documents/{doc_id}/sources` — **extended** (existing endpoint)

Adds optional multi-value form field `chapter_ids`. Form encoding sends one `chapter_ids=<uuid>` pair per selected chapter; absence = empty list = document-level.

**Request (form, multipart for PDF / urlencoded for note + url)**:

| Field        | Type                       | Required | Notes                              |
|--------------|----------------------------|----------|------------------------------------|
| source_type  | `note` \| `url` \| `pdf`   | yes      | unchanged                          |
| title        | string                     | yes      | unchanged                          |
| content      | string                     | no       | unchanged                          |
| url          | string                     | no       | unchanged                          |
| file         | file                       | when pdf | unchanged                          |
| `chapter_ids`| `uuid` (zero or more)      | no       | **NEW** — multi-select chapter set |

**Response**:

- 201 Created — `SourceResponse` JSON, or `partials/sources.html` HTML row when `HX-Request: true`. Response now includes `chapter_ids: list[UUID]`.
- 422 — invalid form input (e.g. unknown chapter UUID), with HTMX-friendly error retarget unchanged.

**Validation**:

- Each `chapter_ids` UUID MUST belong to a chapter in `doc_id`. Mismatch returns 422 with detail naming the offending UUID(s); no partial creation.

## Retroactive replace

`PUT /api/documents/{doc_id}/sources/{source_id}/chapters` — **NEW**

Replaces the full set of chapter associations for one source.

**Request (JSON)**:

```json
{ "chapter_ids": ["<uuid>", "<uuid>"] }
```

`chapter_ids` may be empty (= demote to document-level).

**Response**:

- 200 OK — `SourceResponse` JSON, or rendered `partials/sources.html` row when `HX-Request: true` (so the chapter chips on the row update in place).
- 404 — source not found or not owned by current user.
- 422 — one or more chapter UUIDs do not belong to `doc_id`.

## Filter on list

`GET /api/documents/{doc_id}/sources` — **extended** (existing endpoint)

Adds optional `scope` query parameter.

**Query parameters**:

| Param  | Values                                                                | Default |
|--------|-----------------------------------------------------------------------|---------|
| scope  | `all` \| `doc-level` \| `chapter:<uuid>`                              | `all`   |

**Response**:

- 200 OK — `list[SourceResponse]` JSON, or rendered HTML rows when `HX-Request: true`. Response includes `chapter_ids` per source.
- Stale `scope=chapter:<uuid>` (chapter no longer exists for `doc_id`) silently degrades to `scope=all`; logged at WARNING.

## Single-association endpoints (mirror existing snippet endpoints from spec-016)

These are provided for symmetry with the existing snippet API — used for atomic single-toggle updates if needed by future UI.

`POST /api/documents/{doc_id}/chapters/{chapter_id}/sources/{source_id}` — **NEW**

Creates one association. 201 on success, idempotent (409 NOT thrown on duplicate; uses `db.merge`).

`DELETE /api/documents/{doc_id}/chapters/{chapter_id}/sources/{source_id}` — **NEW**

Removes one association. 204 on success or no-op.

These are not required by the Phase 1 UI (which uses the bulk replace endpoint), but provide parity with the existing snippet-side endpoints from spec-016 and may be used by future tooling.
