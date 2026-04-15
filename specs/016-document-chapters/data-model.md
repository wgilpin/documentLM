# Data Model: Chapter-Centric Documents

**Feature**: 016-document-chapters
**Date**: 2026-04-14

## New Entities

### Chapter

A structural unit within a document. Each chapter has its own title, optional brief, and content.

| Field          | Type                     | Constraints                          | Notes                                   |
|----------------|--------------------------|--------------------------------------|-----------------------------------------|
| id             | UUID                     | PK, default uuid4()                 |                                         |
| document_id    | UUID                     | FK documents.id, CASCADE, NOT NULL   | Parent document                         |
| user_id        | UUID                     | FK users.id, CASCADE, NOT NULL       | Owner (matches document owner)          |
| title          | String(255)              | NOT NULL, default "Untitled Chapter" | Chapter heading                         |
| brief          | Text                     | nullable                             | Planning description, not editor content |
| brief_visible  | Boolean                  | NOT NULL, default true               | Toggle for brief show/hide              |
| content        | Text                     | NOT NULL, default ""                 | Chapter body (markdown)                 |
| position       | Integer                  | NOT NULL                             | Display order (0-based)                 |
| created_at     | DateTime (timezone=True) | NOT NULL, server_default=now()       |                                         |
| updated_at     | DateTime (timezone=True) | NOT NULL, server_default=now(), onupdate=now() |                              |

**Indexes**:

- `chapters_document_position_idx` on (document_id, position) — ordering queries
- `chapters_document_user_idx` on (document_id, user_id) — ownership queries

**Constraints**:

- UNIQUE(document_id, position) — no two chapters share the same position within a document

### ChapterSnippet (Junction Table)

Many-to-many association between chapters and snippets.

| Field       | Type | Constraints                        | Notes            |
|-------------|------|------------------------------------|------------------|
| chapter_id  | UUID | FK chapters.id, CASCADE, NOT NULL  | Composite PK     |
| snippet_id  | UUID | FK snippets.id, CASCADE, NOT NULL  | Composite PK     |

**Indexes**:

- PK on (chapter_id, snippet_id)
- `chapter_snippets_snippet_idx` on (snippet_id) — reverse lookup: "which chapters has this snippet?"

## Modified Entities

### Document (existing)

No schema changes. The `content` field is now a cached concatenation of all chapter contents, rebuilt by chapter_service on every chapter write operation.

| Field   | Change         | Notes                                             |
|---------|----------------|---------------------------------------------------|
| content | Behaviour only | Now derived from chapters; still stored in DB      |

### Snippet (existing)

No schema changes. The `document_id` FK is retained for ownership. Chapter association is via the ChapterSnippet junction table.

| Field       | Change | Notes                                                  |
|-------------|--------|--------------------------------------------------------|
| document_id | None   | Retained for ownership; chapter link is via junction    |

## Entity Relationships

```text
Document 1──* Chapter        (document owns chapters, CASCADE delete)
Chapter  *──* Snippet         (via ChapterSnippet junction, CASCADE on both FKs)
Document 1──* Snippet         (existing relationship preserved for ownership)
Document 1──* Source          (unchanged)
Document 1──* Comment         (unchanged)
Document 1──* ChatSession     (unchanged)
```

## State Transitions

### Chapter Lifecycle

```text
[Created] → title set, content empty, position = max(existing) + 1
    │
    ├─→ [Editing] → content updated, brief added/toggled
    │
    ├─→ [Reordered] → position changed, sibling positions adjusted
    │
    └─→ [Deleted] → chapter removed, junction rows cascade-deleted,
                     sibling positions recompacted, Document.content rebuilt
```

### Document.content Rebuild Triggers

Any of these chapter operations trigger a Document.content rebuild:

- Chapter created
- Chapter content updated
- Chapter deleted
- Chapters reordered
- Chapter title changed (titles appear as headings in concatenated content)

## Migration Plan

**Migration file**: `migrations/versions/xxxx_add_chapters.py`

**Schema changes** (DDL):

1. CREATE TABLE `chapters` with all fields above
2. CREATE TABLE `chapter_snippets` with composite PK
3. Add indexes

**Data migration** (DML):

1. For each row in `documents`:
   - INSERT into `chapters`: id=new_uuid, document_id=doc.id, user_id=doc.user_id, title=doc.title, content=doc.content, position=0
2. For each row in `snippets`:
   - Find the sole chapter for that snippet's document_id
   - INSERT into `chapter_snippets`: chapter_id=chapter.id, snippet_id=snippet.id

**Rollback**: DROP `chapter_snippets`, DROP `chapters` (data migration is not reversible — rollback loses chapter structure).
