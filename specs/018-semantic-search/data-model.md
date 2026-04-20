# Data Model: Semantic Search over Sources and Snippets (Phase 2)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-04-20

## Scope

This feature adds **no relational tables** and changes **no existing table columns**. The only persisted-state delta is in the ChromaDB vector store: snippet vectors are added, and source chunk metadata is extended with an `entity_type` discriminator.

Relational entities reused from prior specs:

- `snippets` (from spec 010)
- `sources` (from spec 001)
- `chapters` (from spec 016)
- `chapter_sources`, `chapter_snippets` (from spec 017)

See [src/writer/models/db.py](../../src/writer/models/db.py) for the authoritative ORM definitions.

## ChromaDB — extended entity schema

The existing per-user collection `user_<user_hex>` now holds two kinds of documents, distinguished by `entity_type`.

### Source Chunk (existing shape, metadata extended)

| Field | Source | Notes |
|---|---|---|
| `id` (Chroma ID) | `{source_uuid}_{chunk_index}` | Unchanged from spec 005. |
| `document` | text of one chunk | Produced by `chunk_sentences(strip_urls(source.content))`. Unchanged. |
| `metadata.source_id` | `str(source.id)` | Unchanged. |
| `metadata.document_id` | `str(source.document_id)` | Unchanged. |
| `metadata.is_private` | `bool` | Unchanged. |
| `metadata.entity_type` | **`"source"`** | **NEW.** Normalised by the backfill script for existing rows. Retrieval helpers default missing values to `"source"` during the migration window. |

### Snippet Embedding (new)

| Field | Source | Notes |
|---|---|---|
| `id` (Chroma ID) | `snip_{snippet_uuid}` | Deterministic; enables idempotent upsert + delete-by-ID. |
| `document` | `strip_urls(snippet.text)` | Single embedding per snippet — no chunking (see research §2). |
| `metadata.entity_type` | `"snippet"` | Discriminator for retrieval filtering. |
| `metadata.snippet_id` | `str(snippet.id)` | Primary lookup key for deletion and post-query hydration. |
| `metadata.source_id` | `str(snippet.source_id)` or `"none"` | Sentinel `"none"` when the snippet has no parent source (Chroma metadata values must be scalars). |
| `metadata.document_id` | `str(snippet.document_id)` | Enables per-document corpus filtering. |
| `metadata.is_private` | `bool` | Mirrors the owning document's privacy state at the time of embedding; kept in sync via `vector_store.update_privacy` (existing helper needs to be extended to also cover snippets — see implementation notes). |

### Lifecycle

- **Create snippet** → background task embeds + upserts one vector using the deterministic ID.
- **Edit snippet metadata only (note, tag, chapter associations)** → no embedding work. Snippet tag associations are NOT mirrored into Chroma metadata (see research §6). Snippet **text** is not editable through any current UI or API path, so no re-embed hook is required (see spec Assumptions; adding snippet text editing later is a future concern that must ship its own re-embed call).
- **Delete snippet** → `collection.delete(ids=["snip_<uuid>"])` in the snippet service's delete path.
- **Delete source** → existing `delete_source_chunks` handles source chunks. Snippets that reference a deleted source have `snippet.source_id` set to NULL via the existing `ondelete="SET NULL"` FK, but their embedding is unaffected (still searchable, with `source_id="none"` in metadata after the next re-embed if any). No cascade of snippet embeddings is required.
- **Delete document / user** → cascades already handled by existing delete paths (relational cascade deletes snippet rows; vector-store cleanup piggybacks on existing document/user teardown).
- **Document privacy toggle** → existing `update_privacy(user_id, doc_id, is_private)` already updates all chunks by `document_id`. No change needed; snippets have the same `document_id` metadata field, so the existing function covers them too.

## In-memory entities (server-side, not persisted)

These live as Pydantic schemas in [src/writer/models/schemas.py](../../src/writer/models/schemas.py); they are request/response shapes only.

### `SearchScope` (alias of existing `FilterScope`)

Reuses [services/filter_scope.py](../../src/writer/services/filter_scope.py)'s `parse_filter_scope`. The values are:

| kind | Fields | Meaning |
|---|---|---|
| `all` | — | Entire document. |
| `doc-level` | — | Items with zero chapter associations only. Unused by the search UI in this spec (the two user-facing modes are `all` and `chapter:<uuid>`) but kept for symmetry with the sidebar filter from spec 017. |
| `chapter` | `chapter_id: uuid` | Items tagged to the chapter OR with zero associations (per FR-012). |

### `SourceResult`

| Field | Type | Source |
|---|---|---|
| `source_id` | `uuid.UUID` | Chroma metadata. |
| `title` | `str` | Resolved from `sources.title` (one SQL query per search, batched). |
| `excerpt` | `str` | Text of the highest-scoring chunk for this source (see plan §4). |
| `score` | `float` | ChromaDB distance, surfaced as `1 - distance` or similar normalisation; exact formula an implementation detail. |
| `in_scope` | `bool` | True iff `source_id` is in the resolved in-scope set for the current `scope`. |

### `SnippetResult`

| Field | Type | Source |
|---|---|---|
| `snippet_id` | `uuid.UUID` | Chroma metadata. |
| `text` | `str` | Full snippet text (one embedding == full text, so Chroma's `document` field is the text). |
| `source_id` | `uuid.UUID \| None` | Parsed from metadata (`"none"` sentinel → `None`). |
| `source_title` | `str \| None` | Resolved from `sources.title` via the same batched lookup as sources results. `None` when `source_id` is `None`. |
| `chapter_ids` | `list[uuid.UUID]` | Loaded from `chapter_snippets` in one batched query per search. |
| `score` | `float` | As above. |
| `in_scope` | `bool` | As above. |

### `SpilloverCounts`

| Field | Type | Meaning |
|---|---|---|
| `out_of_scope_count` | `int` | Count of out-of-scope matches above the similarity threshold, per group. Shown only when `scope` is a chapter scope AND the count is > 0 (FR-015). |

### `SearchV2Response`

| Field | Type | Meaning |
|---|---|---|
| `query` | `str` | Echo of the trimmed query. |
| `scope` | `SearchScope` | Echo of the resolved scope (may differ from input if the requested chapter was deleted — fallback to `all` per FR-021). |
| `sources` | `{"in_scope": list[SourceResult], "out_of_scope_count": int}` | Source group. |
| `snippets` | `{"in_scope": list[SnippetResult], "out_of_scope_count": int}` | Snippet group. |

Note: the response carries only in-scope items in the `in_scope` list but also exposes `out_of_scope_count` for the spillover indicator. Per research §7, the client-side render path receives the FULL list (both in- and out-of-scope items) with the `in_scope` flag per item; the response schema above reflects the JSON view. The HTMX partial view receives the same data but renders all items with a `data-in-scope` attribute for CSS-driven visibility.

## State transitions

- **Snippet vector presence**:
  - `absent` → `present` : on create (background task), on edit (background task), on backfill.
  - `present` → `absent` : on snippet delete.
  - `present` → `present (replaced)` : on edit (upsert replaces in place).
  - Failed transitions log at ERROR and leave the snippet row intact; the vector stays `absent` until the next create/edit/backfill that targets it.

- **Source chunk metadata**:
  - Missing `entity_type` → `entity_type: "source"` : via backfill script one-shot. Retrieval helpers treat missing as `"source"` during the migration window, so there's no observable behaviour change.

## Validation rules

- **Snippet embedding**: snippet text MUST be non-empty (already enforced by `Snippet.text` NOT NULL + `SnippetCreate.text` min_length). Empty text → skip embedding (log at INFO), snippet still saved.
- **Search query**: must be non-whitespace after `.strip()` (FR-001). Existing endpoint already rejects empty; extended endpoint keeps that behaviour.
- **Scope validation**: `chapter:<uuid>` must refer to a chapter in the target document. On mismatch, service falls back to `all` and logs WARN. This parallels the behaviour in `list_snippets_by_scope` today.
- **Similarity threshold**: distances > 1.0 are dropped before grouping/ranking (research §5). Constant lives in `search_service.py`.

## Indexes

No new relational indexes required. The scope-resolution queries use:

- `chapter_sources` PK `(chapter_id, source_id)` — already in place from 017.
- `chapter_sources_source_idx` — already in place from 017.
- `chapter_snippets` PK `(chapter_id, snippet_id)` — already in place from 017.
- `chapter_snippets_snippet_idx` — already in place from 017.
- `snippets.document_id` FK index — already in place.
- `sources.document_id` FK index — already in place.

ChromaDB's HNSW index is applied automatically on collection creation; no explicit index maintenance needed.
