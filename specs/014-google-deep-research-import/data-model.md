# Data Model: Import Google Deep Research

**Feature**: 014-google-deep-research-import  
**Date**: 2026-04-12

---

## Schema Changes

**None.** This feature reuses the existing `Source` table and ingestion pipeline. No migrations required.

---

## Existing `Source` Table (relevant fields)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `document_id` | UUID | FK → Document |
| `user_id` | UUID | FK → User |
| `source_type` | enum | `url` \| `pdf` \| `note` |
| `title` | str | Display name in sources panel |
| `content` | str | Text content (used for note/pdf types) |
| `url` | str \| None | URL (used for url type) |
| `indexing_status` | enum | `pending` → `processing` → `completed` \| `failed` |
| `error_message` | str \| None | Populated on indexing failure |

**Document body source**: inserted with `source_type=note`, `content=<full markdown text>`, `url=None`  
**Each reference URL**: inserted with `source_type=url`, `url=<extracted url>`, `title=<link text>`, `content=""`

---

## New Internal Types (service layer only, no DB)

### `ExtractedReference`

```python
class ExtractedReference(TypedDict):
    title: str   # link display text, or domain name as fallback
    url: str     # absolute https:// URL
```

### `DeepResearchParseResult`

```python
class DeepResearchParseResult(TypedDict):
    title: str                          # first H1/H2 heading, or filename fallback
    body: str                           # full markdown content
    references: list[ExtractedReference]  # deduplicated list of extracted URLs
```

---

## Deduplication Logic

URL deduplication occurs at two levels:

1. **Within the import** (`deep_research_service.extract_urls`): Python `dict` keyed by URL strips duplicates before any DB writes.
2. **Within the workspace** (`source_service.add_source`): existing check on `(document_id, url, user_id)` silently returns the existing source if the URL already exists — no new source row is created.
