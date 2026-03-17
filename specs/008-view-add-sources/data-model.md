# Data Model: Document Sources Pane – View and Add Sources

**Branch**: `008-view-add-sources` | **Date**: 2026-03-17

## No Schema Changes Required

All data needed by this feature is already present in the `sources` table.

## Existing Source Entity (reference)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID (PK) | |
| `document_id` | UUID (FK → documents) | |
| `source_type` | `SourceType` enum | `url`, `pdf`, `note` |
| `title` | str (255) | Display name in the pane |
| `content` | str (text) | Stored text; for PDFs, pypdf-extracted text |
| `url` | str \| None (2048) | Only set for `url` type sources |
| `indexing_status` | `IndexingStatus` enum | `pending`, `processing`, `completed`, `failed` |
| `error_message` | str \| None | Set on indexing failure |
| `created_at` | datetime | |

## View Feature — Data Access Pattern

```
GET /{doc_id}/sources/{source_id}/view
  → service: get_source(db, source_id) → SourceResponse
  → template: renders source.content (for note/pdf)
              OR redirects to source.url (for url type — handled in template link, not here)
```

**Note**: The view endpoint is only called for `note` and `pdf` source types. URL sources open their stored `url` directly via an `<a target="_blank">` link — no endpoint involved.

## Existing Pydantic Schemas (no changes needed)

- **`SourceCreate`**: `document_id`, `source_type`, `title`, `content`, `url`
- **`SourceResponse`**: all Source fields + `created_at`

Both schemas already cover the data needed for the view feature.
