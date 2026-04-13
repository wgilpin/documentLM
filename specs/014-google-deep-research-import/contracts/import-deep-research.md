# API Contract: Import Google Deep Research

**Endpoint**: `POST /api/documents/{doc_id}/sources/import-deep-research`  
**Auth**: Required (current user session)

---

## Request

| Part | Field | Type | Required | Notes |
|---|---|---|---|---|
| Path | `doc_id` | UUID | Yes | Target document |
| Form | `file` | UploadFile | Yes | `.md` file from Google Deep Research export |

Content-Type: `multipart/form-data`

---

## Success Response — HTMX (`HX-Request: true`)

**Status**: `200 OK`  
**Content-Type**: `text/html`  
**Body**: Concatenated `partials/sources.html` fragments, one per created source (document body + each reference URL). Suitable for `hx-swap="beforeend"` on `#source-list`.

If a URL already exists as a source in the workspace, it is silently skipped — no fragment is emitted for it.

---

## Error Responses — HTMX

| Scenario | Status | HX-Retarget | Body |
|---|---|---|---|
| File is empty or unreadable | `422` | `#import-deep-research-error` | Inline error HTML |
| File contains no parseable content | `422` | `#import-deep-research-error` | Inline error HTML |
| Document not found / not owned by user | `404` | — | Standard HTTP error |

The modal remains open on `422` errors so the user can select a different file.

---

## Success Response — Non-HTMX

**Status**: `200 OK`  
**Content-Type**: `application/json`  
**Body**:

```json
{
  "created": [
    {
      "id": "uuid",
      "source_type": "note",
      "title": "AI Product Management in Rapid Development",
      "indexing_status": "pending"
    },
    {
      "id": "uuid",
      "source_type": "url",
      "title": "Vibe Coding Explained: Tools and Guides - Google Cloud",
      "url": "https://cloud.google.com/discover/what-is-vibe-coding",
      "indexing_status": "pending"
    }
  ],
  "skipped_count": 2
}
```

---

## Notes

- Ingestion (`run_indexing`) is triggered as a FastAPI `BackgroundTask` for each created source — the response returns immediately with `indexing_status: pending`.
- `skipped_count` reflects URLs that already existed in the workspace and were silently deduped.
