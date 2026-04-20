# Implementation Plan: Semantic Search over Sources and Snippets (Phase 2)

**Branch**: `018-semantic-search` | **Date**: 2026-04-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-semantic-search/spec.md`

## Summary

Turn the existing source-only chunk search into a dual-entity semantic search over the current document's sources **and** snippets, grouped by entity type, ranked by cosine similarity, and filterable by chapter scope.

Technical approach: extend the existing per-user ChromaDB collection with a new `entity_type` discriminator (`"source"` vs `"snippet"`), embed snippets at create/update time (and via a one-shot backfill), and add a chapter-aware filter pipeline that resolves an in-scope set of source_ids and snippet_ids from the `chapter_sources` / `chapter_snippets` join tables (shipped in 017). The search runs one unbounded query per user interaction against the whole document corpus, then buckets results client-side into `{sources, snippets}` × `{in_scope, out_of_scope}` — this gives us free spillover counts and a zero-roundtrip broaden action. The existing `/documents/{id}/search` endpoint is widened; the current source-chunk-only search UI is replaced with a two-group results partial that wires click-through into the existing sidebar panes (no new detail view).

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, ChromaDB (existing, per-user persistent client), `nlp-utils` (existing, for snippet chunk parity), Jinja2, Alembic (no schema migration this phase — backfill only)
**Storage**: PostgreSQL (Docker container) — **no new tables** (reuses `chapter_sources` + `chapter_snippets` from 017). ChromaDB local persistent directory gains snippet documents inside the existing per-user collection, distinguished by a new `entity_type` metadata key.
**Testing**: pytest (service layer only — TDD; no tests for API endpoints or UI per Constitution II). ChromaDB and embedding calls mocked in service tests; integration tests exercise the real ChromaDB persistent client with a tmp `chroma_path`.
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL); ChromaDB embedded in-process inside the app container
**Project Type**: Web service (single FastAPI app, HTMX frontend)
**Performance Goals**: Sub-second search for a corpus of a few hundred sources + snippets in a single document (SC-001). One ChromaDB query per user interaction (the broaden action is client-side filtering of cached results).
**Constraints**: No remote API calls in tests; no plain dicts; no `Any`; ruff must pass; minimise JS (scope toggle and broaden action are HTMX `hx-get` on a `<select>` / `<a>`, no new `.js` files)
**Scale/Scope**: A single document: hundreds of sources, maybe low thousands of snippets, up to tens of chapters. ChromaDB's default `hnsw` index handles this trivially — latency is bounded by the DB round trip for chapter-scope resolution, not the vector search.

## Constitution Check

- [x] **I. Python + uv**: All new code is Python; uv used for deps. No new package manager or language.
- [x] **II. TDD scope**: Tests planned for `search_service` (dual-group ranking, scope resolution, spillover count accuracy), `snippet_service` (embed-on-create, delete-removes-embedding), and `vector_store` wrappers for snippet indexing. No tests for API endpoints or templates.
- [x] **III. No remote APIs in tests**: ChromaDB runs locally; embedding model is local (sentence-transformers via nlp-utils). Service-layer tests mock `vector_store` calls directly to avoid touching the persistent client.
- [x] **IV. Simplicity**: Scope confirmed against spec; no extras (no "summarise this source", no discover, no query history, no saved searches — all explicitly out of scope in the spec). Reuses existing collection + existing search endpoint path rather than introducing a new subsystem.
- [x] **V. Strong typing**: New Pydantic schemas for request/response (`SearchV2Request`, `SearchV2Response`, `SourceResult`, `SnippetResult`, `SpilloverCounts`, `SearchScope`). `ChunkResult` already a TypedDict in core; snippet path gets a parallel `SnippetChunkResult` TypedDict. No `Any`.
- [x] **VI. Functional style**: All new code is module-level async functions parallel to existing `search_service` / `snippet_service` idioms. No new classes beyond ORM additions (none needed) and Pydantic schemas.
- [x] **VII. Ruff**: Run `ruff check --fix && ruff format` on all touched files before save.
- [x] **VIII. Containers**: No infra changes; reuses existing PostgreSQL container and ChromaDB persistent directory.
- [x] **IX. Logging**: Every new service function logs start + success/failure at INFO/ERROR. Embedding failures on snippet create are logged at ERROR and do not raise out of `create_snippet` (snippet save must still succeed per FR-023).
- [x] **ADK architecture**: No agent changes — feature is pure RAG retrieval, no LLM invocation anywhere in the search path.

No violations to record in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/018-semantic-search/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── search-api.md    # Extended /documents/{id}/search contract
├── checklists/
│   └── requirements.md  # spec quality checklist (already passes)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

Single-project layout (`src/writer/`) — no new top-level directories.

```text
src/writer/
├── api/
│   └── search.py            # extend: accept `scope` query param; return dual-group partial
├── models/
│   └── schemas.py           # add: SearchV2Request, SearchV2Response, SourceResult,
│                            #      SnippetResult, SpilloverCounts, SearchScope (reuses FilterScope shape)
├── services/
│   ├── search_service.py    # extend: new search_document_dual(query, doc_id, scope)
│   │                        #         returning dual groups + spillover counts
│   ├── snippet_service.py   # extend: create_snippet embeds on save (FR-019);
│   │                        #         delete_snippet removes embedding (FR-020)
│   │                        # note: snippet text is not editable today, so no
│   │                        #       re-embed hook is required (see spec Assumptions)
│   └── vector_store.py      # extend: re-export new snippet-aware helpers from core
├── templates/
│   └── partials/
│       ├── search_results.html # REPLACE contents: two <section>s (Sources, Snippets),
│       │                        #                  spillover indicator + broaden link
│       └── search_scope.html    # NEW: scope selector <select> (hidden when doc has no chapters)
└── core/                    # no changes

src/documentlm_core/services/
├── vector_store.py          # extend: index_snippet(), delete_snippet_embedding(),
│                            #         query_document_corpus() returning sources + snippets
│                            #         with entity_type metadata
└── indexer.py               # extend: helper `embed_snippet_text()` reusing existing
                             #         chunk/strip-URL pipeline but emitting a single doc
                             #         (snippets are short — no chunking)

scripts/
└── backfill_snippet_embeddings.py  # NEW: one-shot script iterating all snippets,
                                    #      embedding those without a vector record (FR-022)

tests/unit/
├── test_search_service.py          # NEW: dual-group ranking, scope resolution,
│                                    #      spillover count accuracy, empty-group handling
├── test_snippet_service.py         # extend: embed-on-create, delete-removes-embedding,
│                                    #         failure path (embedding raises →
│                                    #         snippet still saved, logged)
└── test_vector_store.py            # NEW: snippet index/query/delete with entity_type filter;
                                    #      uses a tmp chroma_path (not a mock) to prove metadata
```

**Structure Decision**: Single project (`src/writer/`), with the shared vector store primitives lifted into `documentlm_core`'s existing `vector_store.py` module (where source indexing already lives). The work splits cleanly along the existing service modules:

- `search_service.py` grows one new function (`search_document_dual`) that orchestrates scope resolution + vector query + bucketing; the old `search_document_corpus` can either be retired or kept as a thin pass-through. Decision deferred to Phase 0.
- `snippet_service.py` grows two small embedding hooks (create + delete) around existing CRUD.
- `documentlm_core.vector_store` grows two symmetric helpers (`index_snippet`, `delete_snippet_embedding`) and one unified query (`query_document_corpus`) that returns both entity types in a single Chroma round-trip.
- UI delta is two template partials (`search_results.html` rewrite + `search_scope.html` new) wired into the existing sidebar; no new JS.
- A one-shot Python script under `scripts/` handles the initial backfill. This stays out of Alembic because it's not a schema change — embeddings live in ChromaDB, not Postgres.

## Phase 0 — Research

Driven by the unknowns surfaced while drafting this plan. Output goes to `research.md`.

Open items requiring a decision:

1. **ChromaDB entity-type discrimination.** Current Chroma metadata is `{source_id, document_id, is_private}`. Adding a snippet path needs a mechanism to keep source-chunk retrieval (used by agents for RAG) from accidentally pulling snippets.
   - Option A: new `entity_type` metadata key; both paths filter by it explicitly.
   - Option B: separate per-user collection for snippets (e.g. `snippets_user_<hex>`).
   - Option C: ID prefix convention (`src_<uuid>_<i>` vs `snip_<uuid>`) with no metadata change — brittle, filters by ID prefix are awkward in Chroma.
   - **Leaning**: A. Single collection keeps vectors directly comparable in the same space (spec requires this) and lets a single Chroma query return both types sorted by global similarity. Existing RAG callers (`query_sources`, `query_sources_tiered`, `query_sources_with_metadata`) must be audited to add an explicit `entity_type: "source"` filter so they don't regress.

2. **Snippet chunking policy.** Snippets are short (typically a highlighted paragraph or two). Splitting them into multiple chunks would fragment results and inflate index size for zero quality gain.
   - **Leaning**: one embedding per snippet, whole text, no chunking. URL stripping from `indexer.strip_urls` is reused for parity.

3. **Embedding-on-save behaviour when embedding fails (FR-022).** The spec requires the snippet to save regardless, with a background retry.
   - Option A: synchronous embed during `create_snippet`; on failure, log and swallow; no retry queue, rely on backfill script + admin action.
   - Option B: background task via FastAPI `BackgroundTasks` that runs embedding after the response is sent; failure logged but not user-visible.
   - Option C: full retry queue with persisted state.
   - **Leaning**: B for creates/updates (fast happy path, no user-visible latency) + A fallback pattern for the backfill script (it's already an offline batch). C is over-engineered for a prototype.

4. **Best-matching-excerpt per source in results (FR-007).** Chroma returns chunks, not sources. If a source has 20 chunks and 3 of them match, we need to: (a) keep only the highest-similarity chunk per source for display, (b) dedupe source IDs in the source-results list, (c) decide whether similarity score shown is the top chunk's score (what the spec implies).
   - **Leaning**: over-fetch (`top_k` × a small fudge factor, e.g. 30), group by `source_id`, keep the top-scoring chunk per source; truncate result list to the configured per-group cap. Snippets are already one-per-entity so no grouping needed.

5. **Similarity threshold (noise floor — FR-005).** ChromaDB returns squared-L2 distances, not cosine similarity directly. Existing `query_sources_tiered` uses `max_distance=1.0`. We need a distance cutoff that behaves sensibly across source chunks (longer, ~1000 chars) and snippet text (shorter, highly variable).
   - **Leaning**: start with the same `max_distance=1.0` as the existing tiered function and tune from dogfooding. Threshold must be a single constant (not per-entity-type) since the spec requires comparable scoring across types.

6. **Chapter scope resolution query shape.** Given (document_id, scope), we need two sets: {in_scope_source_ids}, {in_scope_snippet_ids}. The naive path: two SQL queries. With `FilterScopeAll`, we just need all source/snippet IDs for the doc (for bucketing spillover). With `FilterScopeChapter`, we need tagged-to-chapter OR untagged.
   - **Leaning**: two small SQL queries per search (one per entity type), computed once and passed as ID lists into Chroma's `where_document` / metadata filter. Chroma supports `$in` on metadata.

7. **Broaden action implementation (FR-016).** Spec requires "one-click broaden must change the filter, not re-issue the query."
   - Option A: server stores the full (entire-document) result set in session, broaden re-renders from memory. Requires session state.
   - Option B: server returns the full result set plus in-scope flags on every search; broaden is pure client-side CSS (hide/show). No session state needed.
   - Option C: broaden re-queries the backend with scope=all; same query string, different scope param. Technically a re-query but cached by Chroma.
   - **Leaning**: B. Matches SC-005 exactly ("single query request per typed query, regardless of scope changes"), avoids any session state, and HTMX can swap visibility via a class toggle.

8. **Backwards compatibility with the existing search endpoint.** The current `/documents/{id}/search` returns a single flat result list of source chunks — consumed by existing JS on the page (`hx-post` to add snippet from a result chunk).
   - Option A: keep the old endpoint, add a new one at `/documents/{id}/search-v2`.
   - Option B: extend the existing endpoint to return the new dual-group shape; rewrite the existing consumer template (`partials/search_results.html`) to the new shape.
   - **Leaning**: B. The existing endpoint has one template consumer and zero external API clients. A parallel endpoint would double the surface for no benefit. The current "add chunk as snippet" flow from search results is preserved inside the new source-group result card.

9. **Backfill script trigger and idempotency.** Running the backfill twice must not create duplicate vectors. ChromaDB's `add` with a duplicate ID raises; the script must check-then-upsert or use `add_or_update`.
   - **Leaning**: deterministic snippet vector ID = `snip_<snippet_uuid>` (single chunk, single id), and the script uses `add` inside a try/except for `IDAlreadyExists` (or `upsert` if the ChromaDB client exposes it — check version in research).

Output: `research.md` consolidating each decision + rationale + alternatives rejected.

## Phase 1 — Design & Contracts

Prerequisite: `research.md` complete.

### `data-model.md`

Entities added (vector store) and touched (relational DB):

- **Snippet Embedding** (new, ChromaDB):
  - Collection: existing per-user collection `user_<user_hex>`.
  - Vector ID: `snip_<snippet_uuid>` (single vector per snippet, no chunking).
  - Document: the snippet's `text` with URLs stripped.
  - Metadata: `{entity_type: "snippet", snippet_id: "<uuid>", source_id: "<uuid or 'none'>", document_id: "<uuid>", is_private: <bool>}`.
  - Lifecycle: created on snippet insert, replaced on snippet text edit, deleted on snippet delete or on document/source cascade.
- **Source Chunk** (existing, unchanged payload but **metadata extended**):
  - Metadata now also carries `entity_type: "source"`. Existing rows without this key are treated as `"source"` via a server-side default in the retrieval helpers — so no data migration required, but the backfill script SHOULD also stamp the missing key to normalise the store.
- **Relational tables**: none changed. `chapter_sources` and `chapter_snippets` from 017 are read-only in this feature.

### `contracts/search-api.md`

Extended endpoint:

- `GET /api/documents/{doc_id}/search?q=<query>&scope=<scope>&top_k=<n>`
  - `q`: non-empty query string (trim whitespace).
  - `scope`: `"all"` | `"doc-level"` | `"chapter:<uuid>"` (reuses `parse_filter_scope` from existing `filter_scope.py`). Default: `"all"` if omitted.
  - `top_k`: per-group cap, default 10, max 20 (matches existing contract).
  - Response shape (JSON when hit without `HX-Request`):

    ```json
    {
      "query": "…",
      "scope": {"kind": "chapter", "chapter_id": "…"},
      "sources": {
        "in_scope": [{"source_id": "…", "title": "…", "excerpt": "…", "score": 0.87}],
        "out_of_scope_count": 4
      },
      "snippets": {
        "in_scope": [{"snippet_id": "…", "text": "…", "source_id": "…", "source_title": "…", "chapter_ids": ["…"], "score": 0.82}],
        "out_of_scope_count": 2
      }
    }
    ```

  - Response when `HX-Request: true`: rendered `partials/search_results.html` with two `<section>`s and the spillover indicator.
  - Read-only (FR-011); MUST NOT mutate any row.

### `quickstart.md`

1. `docker-compose up -d postgres`
2. `uv run alembic upgrade head` (no-op for this spec; verifies 017 is present)
3. `uv run python scripts/backfill_snippet_embeddings.py` — backfills pre-existing snippets. Idempotent.
4. `uv run uvicorn writer.main:app --reload`
5. Open a document with chapters; place caret inside a chapter; open the search UI; type a query; verify:
   - Two groups render (Sources, Snippets).
   - Scope selector defaults to the focused chapter.
   - Spillover indicator shows counts when other-chapter matches exist.
   - Broaden link reveals out-of-scope hits without a new network request (verify via DevTools network tab).
   - Clicking a source jumps to the sources pane; clicking a snippet jumps to the snippet bank.

### Agent context update

Run `.specify/scripts/bash/update-agent-context.sh claude` after plan is finalised to append ChromaDB + `entity_type` discriminator note to `CLAUDE.md`'s Active Technologies section.

## Complexity Tracking

> No violations to track.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| _none_    | —          | —                                    |
