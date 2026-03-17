# API Contracts: Document Sources Pane – View and Add Sources

**Branch**: `008-view-add-sources` | **Date**: 2026-03-17

## New Endpoint

### View Source Content

```
GET /api/documents/{doc_id}/sources/{source_id}/view
```

**Purpose**: Display the stored content of a `note` or `pdf` source in a new browser tab.

**Path Parameters**:
- `doc_id` (UUID) — the owning document
- `source_id` (UUID) — the source to view

**Response**:
- `200 OK` — `text/html` — a standalone HTML page rendering the source title and content
- `404 Not Found` — source does not exist or does not belong to `doc_id`

**Notes**:
- This endpoint is intended to be opened via `<a target="_blank">` — not via HTMX.
- URL-type sources do NOT use this endpoint; they link directly to `source.url`.

---

## Existing Endpoints (no change)

These remain unchanged; listed for completeness:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/documents/{doc_id}/sources` | List all sources (HTML or JSON) |
| POST | `/api/documents/{doc_id}/sources` | Add a source (note / url / pdf) |
| DELETE | `/api/documents/{doc_id}/sources/{source_id}` | Remove a source |
