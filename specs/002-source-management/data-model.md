# Data Model: Source Management

**Branch**: `002-source-management` | **Date**: 2026-03-13

## Status: No Schema Changes Required

The `sources` table and all associated Pydantic schemas are **already implemented** and require no modifications for this feature. This document records the existing model as the authoritative reference for implementation.

## Entity: Source

**Table**: `sources`
**File**: `src/writer/models/db.py:43-58`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, default=uuid4 | |
| `document_id` | UUID | FK → documents.id, CASCADE DELETE, NOT NULL | Scopes source to one document |
| `source_type` | Enum(url, pdf, note) | NOT NULL | Determines which fields are meaningful |
| `title` | String(255) | NOT NULL | User-provided label |
| `content` | Text | NOT NULL, default="" | Extracted PDF text, typed note, or optional URL summary |
| `url` | String(2048) | NULL | Only populated for `source_type=url` |
| `created_at` | DateTime (tz-aware) | NOT NULL, server_default=now() | |

## Validation Rules (from service layer)

| Rule | Enforcement point |
|------|------------------|
| `title` must be non-empty | HTML5 `required` on form; Pydantic `str` type (non-empty) |
| `url` must be a valid HTTP/HTTPS URL | HTML5 `type="url"` on form input |
| PDF upload must be a parseable PDF | `pypdf.PdfReader` in `source_service._extract_pdf_text` — currently swallows parse errors silently (sets content="") |
| `source_type=pdf` requires a file upload | API checks `file is not None` |

## Schemas

**File**: `src/writer/models/schemas.py`

```
SourceCreate:
  document_id: UUID
  source_type: SourceType
  title: str
  content: str = ""
  url: str | None = None

SourceResponse:
  id: UUID
  document_id: UUID
  source_type: SourceType
  title: str
  content: str
  url: str | None
  created_at: datetime
```

## Relationships

```
Document (1) ──── (*) Source
```

One document has zero-or-many sources. Deleting a document cascades to delete all its sources.

## Note on PDF error handling

`add_source_pdf` currently catches all exceptions during PDF extraction, logs them, and stores `content=""` silently. For this feature, the API should surface parse failures to the user as an error response (see contracts).
