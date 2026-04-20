---

description: "Task list for semantic search over sources and snippets (Phase 2)"
---

# Tasks: Semantic Search over Sources and Snippets (Phase 2)

**Input**: Design documents from [/specs/018-semantic-search/](./)
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/search-api.md](./contracts/search-api.md)

**Tests**: TDD is MANDATORY for backend service code (business logic, data access, transformations).
Tests MUST NOT be written for frontend components or API endpoint handlers.
Tests MUST NOT call remote APIs (LLMs, external HTTP) — use mocks / tmp ChromaDB paths.
Write failing tests FIRST, confirm they fail, then implement.

**Organization**: Tasks are grouped by user story. US3 is a P1 prerequisite for the snippet half of US1 and ships before US1's acceptance can fully pass.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 as per [spec.md](./spec.md)
- File paths are absolute from repo root

## Path Conventions

- Single project: `src/writer/` with services + api + templates; shared vector primitives in `src/documentlm_core/services/`.
- Tests: `tests/unit/` (service layer).
- One-shot scripts: `scripts/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project is already initialised. No new dependencies, containers, or tooling are required for this feature.

- [ ] T001 Verify ChromaDB persistent directory exists and is writable at the path configured in [src/documentlm_core/core/config.py](../../src/documentlm_core/core/config.py); confirm `uv run alembic upgrade head` reports no pending migrations (spec 017 must be applied).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the vector store primitives and Pydantic schemas so both US1 (search) and US3 (snippet embedding) can build on a shared foundation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 [P] Add `SearchScope` (alias of existing `FilterScope`), `SourceResult`, `SnippetResult`, `SpilloverCounts`, `SearchGroupPayload`, and `SearchV2Response` Pydantic schemas to [src/writer/models/schemas.py](../../src/writer/models/schemas.py) per the shapes in [data-model.md](./data-model.md).
- [ ] T003 [P] Write failing unit tests for the new vector-store helpers in [tests/unit/test_vector_store.py](../../tests/unit/test_vector_store.py) using a tmp `chroma_path`: (a) `index_snippet` stores a vector with `entity_type="snippet"` metadata at id `snip_<uuid>`, (b) `delete_snippet_embedding` removes by deterministic id, (c) `query_document_corpus` returns both entity types scoped to `document_id`, distance-filtered ≤ 1.0, (d) existing `query_sources` / `query_sources_tiered` / `query_sources_with_metadata` no longer return `entity_type="snippet"` rows.
- [ ] T004 Implement `index_snippet(snippet_id, document_id, text, user_id, source_id, is_private)` in [src/documentlm_core/services/vector_store.py](../../src/documentlm_core/services/vector_store.py) — single-document upsert at deterministic id `snip_<uuid>` with `entity_type="snippet"` metadata. Reuse `strip_urls` from indexer.py.
- [ ] T005 Implement `delete_snippet_embedding(snippet_id, user_id)` in the same file — deletes by deterministic id.
- [ ] T006 Implement `query_document_corpus(query_text, user_id, doc_id, top_k)` in the same file — single Chroma query scoped to `document_id` with `entity_type ∈ {"source", "snippet"}`, returning (text, metadata, distance) tuples with distance ≤ 1.0 (new `MAX_DISTANCE` constant).
- [ ] T007 Add `entity_type: {"$eq": "source"}` to the existing `where` clauses in `query_sources`, `query_sources_tiered`, and `query_sources_with_metadata` in the same file so the RAG path does not accidentally pull snippets into agent context.
- [ ] T008 Re-export `index_snippet`, `delete_snippet_embedding`, `query_document_corpus` (and the existing `MAX_DISTANCE` constant) from [src/writer/services/vector_store.py](../../src/writer/services/vector_store.py).
- [ ] T009 Confirm T003's tests now pass.

**Checkpoint**: Vector store supports snippets + discriminates entity type; all existing RAG callers still return only sources.

---

## Phase 3: User Story 3 — Snippet embeddings are generated so snippets are searchable (Priority: P1)

**Goal**: Every snippet (new and existing) has an embedding in the shared vector space so it can be returned by semantic search.

**Independent Test**: Create a fresh snippet; verify a vector with id `snip_<uuid>` appears in the collection without any user action. Deploy against a populated DB, run the backfill, verify 100% of pre-existing snippets have vectors.

**Why P1 and why this precedes US1**: Spec calls US3 a prerequisite — without embeddings, the snippet half of US1 returns empty. US3 is ordered first so US1 can be acceptance-tested end-to-end.

**Note**: Re-embedding on snippet text edit is explicitly deferred (snippet text is not editable today — see spec Out of Scope). Only create + delete paths are in scope here.

### Tests for User Story 3 (backend services only — MANDATORY)

> Write tests FIRST, confirm they FAIL, then implement. Mocks for `vector_store.index_snippet` / `delete_snippet_embedding`.

- [ ] T010 [P] [US3] Write failing tests in [tests/unit/test_snippet_service.py](../../tests/unit/test_snippet_service.py) for: (a) `create_snippet` schedules an embedding call after commit, (b) `delete_snippet` calls `delete_snippet_embedding` before DB delete, (c) embedding failure logs at ERROR and does NOT raise out of `create_snippet`.

### Implementation for User Story 3

- [ ] T011 [US3] Extend `create_snippet` in [src/writer/services/snippet_service.py](../../src/writer/services/snippet_service.py) to return (or schedule) a post-commit embedding step via an internal `_embed_snippet_async(snippet, is_private)` helper that wraps `asyncio.to_thread(vector_store.index_snippet, ...)`. Catch + log exceptions at ERROR; do not propagate.
- [ ] T012 [US3] Extend `delete_snippet` in the same file to call `vector_store.delete_snippet_embedding(snippet_id, user_id)` wrapped in `asyncio.to_thread` before the `db.delete(snippet)` call; catch + log exceptions so an embedding-store failure does not block the row deletion.
- [ ] T013 [US3] Wire `BackgroundTasks` into the snippet create path in [src/writer/api/snippets.py](../../src/writer/api/snippets.py) so the service-returned embed step runs after the response is sent (FR-022 — save succeeds regardless of embedding outcome).
- [ ] T014 [US3] Create [scripts/backfill_snippet_embeddings.py](../../scripts/backfill_snippet_embeddings.py): iterate every snippet, `upsert` its vector at id `snip_<uuid>`, AND stamp `entity_type="source"` on any existing source chunks lacking the key (one-time normalisation for the discriminator rollout). Log `{n_scanned, n_embedded, n_skipped, n_failed}` at end. Exit 0 on success, 1 on any failure. Idempotent — safe to re-run.
- [ ] T015 [US3] Run the backfill against a dev DB (ask before running if it touches shared infra) and verify the reported `n_embedded + n_skipped` equals `SELECT COUNT(*) FROM snippets`.

**Checkpoint**: Every snippet in the corpus has a vector. Creates / deletes keep the vector store in sync with Postgres.

---

## Phase 4: User Story 1 — Search the current document (Priority: P1) 🎯 MVP core

**Goal**: Deliver the dual-group search: a single input returns Sources and Snippets separately, each ranked by similarity, with click-through into existing sidebar panes.

**Independent Test**: Seed a document with sources + snippets. Query a natural-language string that matches a subset. Verify the writer sees two ranked groups, each card shows the spec-required fields, and clicks on results reveal the corresponding sidebar entry.

### Tests for User Story 1 (backend services only — MANDATORY)

> Write tests FIRST, confirm they FAIL, then implement. Mock `vector_store.query_document_corpus` to return deterministic fixtures so ranking / grouping / threshold logic is testable without embedding any real text.

- [ ] T016 [P] [US1] Write failing tests in [tests/unit/test_search_service.py](../../tests/unit/test_search_service.py) for `search_document_dual`: (a) returns `sources` and `snippets` as separate groups, (b) each group sorted by score desc, (c) items with distance > 1.0 excluded, (d) source-group deduplicates by `source_id` keeping the highest-scoring chunk as the excerpt, (e) snippet-group returns one result per snippet, (f) empty-group cases (no sources in corpus, no snippets in corpus) still return explicit empty lists rather than omitting the group, (g) batched source title + snippet chapter lookups happen in single SQL queries.
- [ ] T017 [P] [US1] Write failing tests in the same file for `resolve_in_scope_ids(session, doc_id, scope)`: (a) `FilterScopeAll` returns every source/snippet id in the doc, (b) `FilterScopeDocLevel` returns only untagged items, (c) `FilterScopeChapter(chapter_id=X)` returns items tagged to X plus untagged items (per FR-012), (d) stale chapter id falls back to `all` and logs a WARN.

### Implementation for User Story 1

- [ ] T018 [US1] Implement `resolve_in_scope_ids(session, doc_id, scope)` in [src/writer/services/search_service.py](../../src/writer/services/search_service.py) returning a typed result (`InScopeIds` dataclass or TypedDict with `source_ids: set[uuid.UUID]`, `snippet_ids: set[uuid.UUID]`). Use two batched SQL queries (one per entity) joining the respective `chapter_*` table.
- [ ] T019 [US1] Implement `search_document_dual(query, user_id, doc_id, session, scope, top_k)` in the same file — orchestrates `query_document_corpus` (over-fetch `top_k * 3` chunks, capped at 60), splits by `entity_type`, groups source chunks by `source_id` keeping the top scorer per source, batch-loads source titles and snippet chapter associations, computes `in_scope` per result against the resolved in-scope sets, caps each group to `top_k`, returns a `SearchV2Response`.
- [ ] T020 [US1] Remove the now-unused `SearchResponse` / `SearchResultItem` schemas from [src/writer/models/schemas.py](../../src/writer/models/schemas.py); update any stray references.
- [ ] T021 [US1] Widen the endpoint in [src/writer/api/search.py](../../src/writer/api/search.py) to accept a `scope` query param (parsed via existing `parse_filter_scope`), default `"all"`, validate `top_k ∈ [1, 20]`. Return `SearchV2Response` as JSON when `HX-Request` is absent; render [partials/search_results.html](../../src/writer/templates/partials/search_results.html) otherwise.
- [ ] T022 [US1] Rewrite [src/writer/templates/partials/search_results.html](../../src/writer/templates/partials/search_results.html) to render two `<section>`s (Sources, Snippets) per [contracts/search-api.md](./contracts/search-api.md). Per-result fields: source cards show title + excerpt + score + existing "Add to Bank" action preserved; snippet cards show snippet text + source title attribution + chapter label (or "document-level") + "Go to snippet" anchor. Each card carries a `data-in-scope` attribute and a `data-source-id` / `data-snippet-id` attribute for click-through wiring.
- [ ] T023 [US1] Add snippet click-through behaviour: clicking a snippet result scrolls to and briefly highlights the matching `#snippet-card-<id>` element in the snippet bank. Prefer existing HTMX-friendly patterns; if a tiny JS helper is unavoidable, put it in [static/snippet-goto.js](../../static/snippet-goto.js) (new file) NOT inline (per local CLAUDE.md "never inline JS" rule). Also update `npm run build:dev` coverage if it bundles the new helper.
- [ ] T024 [US1] Confirm source click-through still works via the existing `scrollToCharOffset` handler referenced by the old template; preserved in T022 but worth explicitly verifying end-to-end.

**Checkpoint**: Writer can type a query and see two ranked groups; clicking results reveals items in the sidebar. Scoping is not yet applied (treats every search as `scope=all`) — that lands in US2.

---

## Phase 5: User Story 2 — Scope the search to the chapter being edited (Priority: P2)

**Goal**: Default scope to the focused chapter; surface a spillover indicator when out-of-scope matches exist; offer one-click broaden without re-querying the backend.

**Independent Test**: With tagged corpus in place, place the caret inside a chapter. Run a query whose matches span chapters. Verify default scope is the focused chapter, spillover count matches reality, broaden reveals out-of-scope hits without a new network request (DevTools), and toggling chapter context resets the default.

### Tests for User Story 2 (backend services only — MANDATORY)

> Write tests FIRST, confirm they FAIL, then implement. Same fixture approach as US1.

- [ ] T025 [P] [US2] Write failing tests in [tests/unit/test_search_service.py](../../tests/unit/test_search_service.py) for: (a) `out_of_scope_count` per group equals the count of above-threshold matches whose id is not in the in-scope set, (b) `scope=all` yields `out_of_scope_count=0` for both groups, (c) stale chapter id in scope triggers fallback to `all` and the returned `SearchV2Response.scope` reflects the degraded value (FR-021), (d) document with zero chapters + `scope=chapter:<uuid>` also degrades to `all`, (e) doc-level items are included in a chapter scope (FR-012) — specifically, an untagged snippet with a matching query appears in the `chapter:<uuid>` scope's in-scope results.

### Implementation for User Story 2

- [ ] T026 [US2] Ensure `search_document_dual` (from T019) populates `out_of_scope_count` by counting results with `in_scope=False` per group BEFORE applying the `top_k` cap; also degrade scope to `all` when the requested chapter no longer exists in the target document (mirrors `list_snippets_by_scope` behaviour in [snippet_service.py:357](../../src/writer/services/snippet_service.py)).
- [ ] T027 [US2] Create [src/writer/templates/partials/search_scope.html](../../src/writer/templates/partials/search_scope.html): a `<select>` with options "Entire document" and (conditionally) "This chapter — [title]". Hidden when the document has zero chapters (FR-017). Uses HTMX `hx-get` on change with a `scope=…` param targeting `#search-results`.
- [ ] T028 [US2] Wire the scope selector's default value in the document template to reflect the current caret-owning chapter (reuse the data attribute or event already emitted by spec 017's sidebar filter; avoid adding new JS). Integrate `partials/search_scope.html` into the search UI container in [src/writer/templates/document.html](../../src/writer/templates/document.html).
- [ ] T029 [US2] Extend [src/writer/templates/partials/search_results.html](../../src/writer/templates/partials/search_results.html) (written in T022): add a per-section spillover indicator that renders `"{in_count} in this chapter, {out_count} in other chapters"` when the active scope is chapter-bound AND `out_of_scope_count > 0`. Include a "Show all" link that flips the wrapping `<div class="search-results">`'s `data-scope` attribute from `chapter` to `all` — CSS hides / reveals cards via `[data-scope="chapter"] [data-in-scope="false"] { display: none; }`. No new backend request (satisfies SC-005).
- [ ] T030 [US2] Ensure the "Show all" link also updates the `<select>` state for visual consistency; again avoid a fresh JS file if HTMX `hx-on::click` plus a target attribute can set both the class and the select value. If unavoidable, add the helper to [static/search-scope.js](../../static/search-scope.js) (new file) per CLAUDE.md JS rules.
- [ ] T031 [US2] Verify FR-018 by manual test: broaden to "Entire document", move the caret into a different chapter, open the search UI — scope must default to the new chapter (per-search override is NOT sticky across chapter context changes).

**Checkpoint**: All user stories are independently functional. A writer editing inside a chapter gets chapter-scoped results by default, sees the spillover count, and can broaden with a single click.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Run `uv run ruff check --fix src/ tests/ scripts/` and `uv run ruff format src/ tests/ scripts/`; resolve any remaining violations.
- [ ] T033 [P] Run `uv run mypy src/` and resolve any new type errors introduced by T002-T030.
- [ ] T034 Run `uv run pytest` and ensure the full suite passes (per CLAUDE.md "Fix all failing tests" rule — existing failures must be addressed, not ignored).
- [ ] T035 Execute the manual smoke test described in [quickstart.md](./quickstart.md) steps 1-9 against a seeded document; confirm sub-second latency (SC-001) on a corpus of ≥ 200 items.
- [ ] T036 Run `npm run build:dev` if any changes were made to static JS bundles per T023/T030, per local CLAUDE.md.
- [ ] T037 Audit agent-side RAG callers one more time to confirm the `entity_type: "source"` filter is in place: search for references to `query_sources`, `query_sources_tiered`, `query_sources_with_metadata` across `src/writer/services/` and `src/writer/agents/`; none should return snippets.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: T001 only. No real code changes.
- **Phase 2 (Foundational)**: Depends on Setup. BLOCKS all user stories.
- **Phase 3 (US3)**: Depends on Phase 2. Required for US1's snippet half to pass acceptance. Start before or alongside Phase 4.
- **Phase 4 (US1)**: Depends on Phase 2. Can start in parallel with Phase 3, but its acceptance scenarios for snippets require Phase 3 embeddings to be in place.
- **Phase 5 (US2)**: Depends on Phase 4 (UI foundations from US1). Extends search_service + search template.
- **Phase 6 (Polish)**: Depends on all prior phases.

### Intra-Story Order

- Service-layer tests (T010, T016, T017, T025) MUST be written and FAIL before the corresponding implementation.
- Schemas (T002) before services.
- Vector store primitives (T004-T007) before service-layer callers (T011, T012, T019).
- `resolve_in_scope_ids` (T018) before `search_document_dual` (T019) — the latter calls it.
- Template work (T022, T027, T029) depends on the endpoint contract being stable (T021, T026).

### Parallel Opportunities

- T002 and T003 can run in parallel (schemas vs. vector-store tests).
- T016 and T017 can run in parallel (different test scenarios, same test file — ensure non-overlapping test function names).
- T010, T016, T017, T025 can all be authored in parallel (different test scenarios across two files).
- T027 (new partial) can be drafted in parallel with T026 (service spillover logic).
- T032 and T033 can run in parallel.

---

## Parallel Example: Phase 2 kick-off

```bash
# Run schema additions and vector-store tests in parallel:
Task: "Add SearchScope + SearchV2Response + SourceResult + SnippetResult + SpilloverCounts to src/writer/models/schemas.py"  # T002
Task: "Write failing tests in tests/unit/test_vector_store.py for index_snippet, delete_snippet_embedding, query_document_corpus, and existing query_sources entity-type filter"  # T003
```

## Parallel Example: US1 test authoring

```bash
# All service tests for US1 can be drafted in parallel (same file, different test functions):
Task: "Write test_search_document_dual_* cases in tests/unit/test_search_service.py"  # T016
Task: "Write test_resolve_in_scope_ids_* cases in tests/unit/test_search_service.py"  # T017
```

---

## Implementation Strategy

### MVP First (US3 + US1)

1. Phase 1: Setup (T001).
2. Phase 2: Foundational (T002–T009).
3. Phase 3: US3 — snippet embeddings are live (T010–T015). **Run backfill.**
4. Phase 4: US1 — dual-group search is live (T016–T024).
5. **STOP and VALIDATE**: search works end-to-end for sources + snippets without any chapter scoping.
6. Deploy / demo.

### Incremental Delivery

1. MVP as above (Phases 1–4): ships findability over the whole document.
2. Phase 5 (US2): adds chapter scoping, spillover, broaden — upgrades findability to "focused by default."
3. Phase 6 (Polish): lint, types, tests, smoke test.

### Parallel Team Strategy

- One developer on Phase 2 vector store + backfill script (T002–T009, T014).
- Second developer on Phase 3 snippet service hooks (T010–T013) once T004–T008 are merged.
- Third developer on Phase 4 search service + template (T016–T024) once T006 + T008 are merged.
- Phase 5 best done by whoever owns Phase 4 (same files).

---

## Notes

- Every service-layer change must have a failing test first (Constitution II).
- No remote API calls in tests — ChromaDB uses a tmp `chroma_path` fixture; embedding model calls are mocked (Constitution III).
- No `except: pass` — every exception logs at ERROR or higher (Constitution IX).
- No new agent types introduced (Constitution ADK architecture).
- No inline JS in templates; two optional new JS files ([static/snippet-goto.js](../../static/snippet-goto.js), [static/search-scope.js](../../static/search-scope.js)) only if HTMX alone can't achieve the interaction.
- Commit after each task or at every checkpoint.
