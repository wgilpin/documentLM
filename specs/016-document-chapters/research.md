# Research: Chapter-Centric Documents

**Feature**: 016-document-chapters
**Date**: 2026-04-14

## R1: Chapter Content Storage Strategy

**Decision**: Chapters stored as separate database rows; Document.content maintained as cached concatenation.

**Rationale**: Chapters need independent identity for snippet association (many-to-many), ordering, briefs, and per-chapter editing. Storing as separate rows enables direct CRUD operations per chapter. The cached concatenation in Document.content preserves backward compatibility with agent_service (invoke_drafter, invoke_bounded_drafter, invoke_planner), vector store indexing, and comment/suggestion offset tracking — all of which read Document.content as a single string.

**Alternatives considered**:

- *Single TipTap document with H1 delimiters*: Chapters would be virtual (defined by H1 headings). Rejected because: empty chapters with just titles wouldn't work, briefs have no natural representation in markdown, and snippet-to-chapter association requires addressable chapter IDs.
- *JSON array in Document.content*: Store chapters as structured JSON. Rejected because: breaks all existing code that treats content as markdown text, requires migration of every consumer.
- *Remove Document.content entirely*: Always compute on the fly. Rejected because: requires changes to agent_service, vector_store, and suggestion/comment flows — too much churn for a prototype.

## R2: Editor Instance Management

**Decision**: Single TipTap editor instance, dynamically mounted on the active chapter.

**Rationale**: The spec requires all chapters visible in a scrollable page but only the active chapter has a live editor. A single TipTap instance avoids memory overhead and ProseMirror conflict issues from multiple editors. When the user clicks a non-active chapter: (1) save current chapter, (2) destroy current TipTap instance, (3) render previous chapter as HTML, (4) create new TipTap instance on clicked chapter.

**Alternatives considered**:

- *Multiple simultaneous TipTap instances*: One per chapter, all live. Rejected because: heavy memory use with 10+ chapters, complex state management, and the spec explicitly says only the active chapter shows a live editor.
- *Single global editor with chapter switching*: Only show one chapter at a time (tab-based). Rejected because: the spec requires all chapters visible in a scrollable page.

## R3: Snippet-Chapter Association Model

**Decision**: Junction table `chapter_snippets` (chapter_id, snippet_id) for many-to-many. Snippets retain document_id for ownership. Unassigned snippets have no rows in the junction table.

**Rationale**: The clarified spec states snippets can belong to multiple chapters. A junction table is the standard relational approach for many-to-many. Keeping document_id on snippets preserves ownership semantics and allows "all snippets for this document" queries. Unassigned snippets (no junction rows) appear in the "all snippets" view.

**Alternatives considered**:

- *Array column on Snippet*: Store chapter_ids as a PostgreSQL array. Rejected because: no referential integrity, harder to query "snippets for chapter X".
- *Replace document_id with chapter_id (one-to-many)*: Rejected because: spec requires many-to-many, and snippets need to exist before chapter assignment.

## R4: Content Cache Rebuild Strategy

**Decision**: Rebuild Document.content on every chapter write operation (create, update, delete, reorder) by querying all chapters ordered by position and concatenating with markdown headings.

**Rationale**: The rebuild is a single SELECT + string concatenation. With ≤50 chapters of typical document size, this takes <10ms. Triggered inside chapter_service functions so it's atomic with the chapter change.

**Format**: Each chapter is concatenated as:

```
## {chapter.title}

{chapter.content}
```

Chapters are separated by double newlines. Document.content starts with the first chapter (no document-level preamble).

**Alternatives considered**:

- *Rebuild on read*: Compute Document.content when agents/suggestions request it. Rejected because: requires changing every consumer to call a new function.
- *Event-driven async rebuild*: Use a background task. Rejected because: adds complexity; synchronous rebuild is fast enough.

## R5: Data Migration Approach

**Decision**: Alembic migration with data migration step. Each existing document gets one chapter. Each existing snippet gets a junction row.

**Rationale**: Preserves all existing content and snippet associations. The migration is idempotent (can check for existing chapters). After migration, existing documents look identical — single chapter, no TOC shown.

**Migration steps**:

1. Create `chapters` table
2. Create `chapter_snippets` table
3. For each document: INSERT one chapter with title=document.title, content=document.content, position=0
4. For each snippet: INSERT one chapter_snippets row linking to the document's sole chapter

## R6: Comment/Suggestion Offset Compatibility

**Decision**: Comments and suggestions continue to use offsets relative to Document.content (the full concatenated markdown). No changes to the comment/suggestion models or services.

**Rationale**: Since Document.content is rebuilt to match the concatenated chapters, existing offset-based logic continues to work. When the user creates a comment while editing a chapter, the frontend computes the global offset by adding the chapter's start position in the full document. This is a pragmatic approach for a prototype — full chapter-scoped comments would require model changes across comment, suggestion, and agent flows.

**Risk**: If chapters are reordered, existing comment offsets may point to wrong positions. Acceptable for a prototype where comments are transient.
