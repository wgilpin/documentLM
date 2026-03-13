# Data Model: Document Workbench MVP

## Entities

### Document

The primary artifact the user creates and edits.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Generated on creation |
| `title` | str | User-provided; non-empty |
| `content` | str | Markdown source text |
| `created_at` | datetime | UTC, set on insert |
| `updated_at` | datetime | UTC, updated on every content change |

**Validation rules**:
- `title` MUST be non-empty, max 255 chars
- `content` may be empty string (blank new document)

**State transitions**: None (content is mutable; no formal draft/published states in MVP)

---

### Source

A source material in the Core Bucket (trusted) added by the user.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Generated on creation |
| `document_id` | UUID (FK → Document) | Scoped to a single document for MVP |
| `source_type` | enum: `url \| pdf \| note` | How the source was added |
| `title` | str | User-provided label |
| `content` | str | Extracted/typed text; used as grounding context |
| `url` | str \| None | For `url` type; otherwise null |
| `created_at` | datetime | UTC |

**Validation rules**:
- `source_type=url`: `url` MUST be a valid HTTP/HTTPS URL; `content` is the user-provided
  summary or empty (full scraping is out of scope for MVP)
- `source_type=pdf`: `content` holds pypdf-extracted text; `url` is null
- `source_type=note`: `content` holds user-typed text; `url` is null
- `title` MUST be non-empty, max 255 chars

**Note**: For MVP, sources are scoped per-document. Post-MVP this becomes workspace-scoped.

---

### Comment

A margin comment created by the user on a text selection in a Document.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Generated on creation |
| `document_id` | UUID (FK → Document) | The annotated document |
| `selection_start` | int | Character offset (inclusive) into document.content |
| `selection_end` | int | Character offset (exclusive) into document.content |
| `selected_text` | str | Snapshot of the selected text at time of comment |
| `body` | str | The user's instruction to the AI |
| `status` | enum: `open \| resolved` | `resolved` when a suggestion is accepted/rejected |
| `created_at` | datetime | UTC |

**Validation rules**:
- `selection_start` >= 0; `selection_end` > `selection_start`
- `selected_text` MUST match `document.content[selection_start:selection_end]` at
  creation time (validated in service layer)
- `body` MUST be non-empty

---

### Suggestion

An AI-generated text replacement produced in response to a Comment.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Generated on creation |
| `comment_id` | UUID (FK → Comment) | The comment that triggered this |
| `original_text` | str | Snapshot of text being replaced (same as comment.selected_text) |
| `suggested_text` | str | AI-generated replacement text |
| `status` | enum: `pending \| accepted \| rejected \| stale` | Lifecycle state |
| `created_at` | datetime | UTC |

**State transitions**:

```
pending → accepted   (user clicks Accept; document.content updated)
pending → rejected   (user clicks Reject; comment.status → resolved)
pending → stale      (document edited after suggestion created; offset mismatch detected)
```

**Validation rules**:
- Only one Suggestion per Comment may be in `pending` state at a time
- On acceptance: substitute `document.content[selection_start:selection_end]` with
  `suggested_text`; set `comment.status = resolved`

---

## Entity Relationship Diagram

```
Document 1──────────* Source
Document 1──────────* Comment
Comment  1──────────1 Suggestion
```

---

## SQLAlchemy ORM Notes

- All tables use `uuid_generate_v4()` (PostgreSQL extension) for primary keys
- All datetime fields are `timezone=True` (UTC stored)
- Relationships use `lazy="selectin"` for async compatibility
- No `relationship()` back-populates required for MVP — queries are explicit joins

---

## Pydantic Schemas (API layer)

```
DocumentCreate    → title: str, content: str = ""
DocumentUpdate    → title: str | None, content: str | None
DocumentResponse  → id, title, content, created_at, updated_at

SourceCreate      → document_id, source_type, title, content, url
SourceResponse    → id, document_id, source_type, title, content, url, created_at

CommentCreate     → document_id, selection_start, selection_end, selected_text, body
CommentResponse   → id, document_id, selection_start, selection_end, body, status, created_at

SuggestionResponse → id, comment_id, original_text, suggested_text, status, created_at
```

All TypedDict-style intermediate data structures MUST use `TypedDict` (not plain `dict`).
