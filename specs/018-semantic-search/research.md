# Research: Semantic Search over Sources and Snippets (Phase 2)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-04-20

Each item below resolves a `NEEDS CLARIFICATION`-equivalent from the plan's Technical Context / Phase 0 open items. Format: Decision → Rationale → Alternatives rejected.

---

## 1. ChromaDB entity-type discrimination

**Decision**: Single shared per-user collection, with a new metadata key `entity_type` ∈ `{"source", "snippet"}` on every document. Both retrieval paths (RAG for agents, user-facing search) filter on this key.

**Rationale**:

- Spec requires source and snippet similarity scores to be directly comparable in the same vector space (FR-019, Assumptions). Same collection + same embedding model guarantees this.
- A single Chroma query can return both types in one round trip, sorted by global similarity. This gives us the dual-group view (with per-group ranking) at the cost of one query, not two, and lets us compute spillover counts from a single result list.
- Existing RAG callers (`query_sources`, `query_sources_tiered`, `query_sources_with_metadata` in [src/documentlm_core/services/vector_store.py](../../src/documentlm_core/services/vector_store.py)) are narrow; adding `"entity_type": {"$eq": "source"}` to their `where` clause is a one-line change per call site.
- Backfill naturally normalises existing source-chunk metadata to carry `entity_type: "source"` so filtering is unambiguous. Rows without the key (from before the backfill runs) are treated as `"source"` by default in the retrieval helpers, so there's no race window.

**Alternatives rejected**:

- **Separate snippet collection** (e.g. `snippets_user_<hex>`). Forces two Chroma queries per search and two different score distributions that we can't trivially reconcile. Adds a second collection to manage lifecycle for (privacy updates, user-deletion cascades) for no retrieval-quality benefit.
- **ID-prefix convention** (`src_*` vs `snip_*`, no metadata change). Chroma's `where` filters don't meaningfully operate on ID prefixes; we'd have to filter post-query, negating the "use Chroma's top_k" optimisation. Also cosmetically brittle — an ID prefix typo becomes a silent retrieval bug.

---

## 2. Snippet chunking policy

**Decision**: One embedding per snippet, whole text, no chunking. URL stripping via the existing `strip_urls` helper in [indexer.py](../../src/documentlm_core/services/indexer.py) is reused.

**Rationale**:

- Snippets are short — a highlighted paragraph or a couple of sentences, typically under 1,000 chars. `chunk_sentences` with the existing `chunk_size=1000` would emit a single chunk anyway for the majority of snippets.
- Fragmenting a snippet would produce duplicate hits for the same logical snippet, requiring post-hoc grouping (same problem as sources — see §4). Not worth it for a prototype.
- Keeps the vector ID deterministic (`snip_<snippet_uuid>`), which is essential for idempotent backfill and for `delete` by ID.

**Alternatives rejected**:

- **Reuse source chunking (`chunk_sentences` with chunk_size=1000, overlap=100)**. Identical result for most snippets, unnecessary complexity + ID bookkeeping for the long-snippet minority.

---

## 3. Embedding-on-save behaviour on failure (FR-023)

**Decision**: Synchronous embed-on-create via FastAPI `BackgroundTasks`, scheduled after the snippet row is committed. Failures are logged at ERROR and do not raise out of the create/update path. The snippet is marked searchable implicitly — i.e. its presence in the vector store IS the searchable flag; no separate DB column. A snippet whose background embedding failed is invisible in search until an operator re-runs the backfill script.

**Rationale**:

- Request latency is preserved — the POST returns as soon as the snippet row is persisted; embedding happens after.
- Matches spec FR-023 verbatim: "the snippet itself is still saved successfully and the embedding is retried in the background". The backfill script acts as the "retry" mechanism for any permanent failure (it idempotently embeds any snippet whose ID isn't already in the collection).
- Avoids a new DB column / background worker. Keeps prototype surface small.

**Alternatives rejected**:

- **Blocking embed during `create_snippet`**. Adds a few hundred ms to the user-visible save latency. Only advantage is immediate searchability, which isn't a hard spec requirement.
- **Celery / RQ job queue**. Gigantic overkill for a prototype. Would require a new container, a broker, and lifecycle plumbing.
- **DB-persisted `needs_embedding` flag + cron retry**. Solves the same problem as the backfill script but with more moving parts.

---

## 4. Best-matching-excerpt per source (FR-007)

**Decision**: Over-fetch from Chroma (`top_k * 3`, capped at 60), then group source-type results by `source_id`, keeping only the highest-scoring chunk per source. Display that chunk's text as the excerpt. Truncate to the configured per-group cap (default 10). Snippet-type results are already one-per-entity so no grouping.

**Rationale**:

- Chroma returns chunks, not sources. Without grouping, a single well-matched source would eat most of the `top_k` slots with its own chunks.
- Over-fetch factor of 3× is a pragmatic ceiling — in practice a single source rarely contributes more than 3 chunks to the top-10, so 30 chunks usually yield 10 distinct sources.
- Grouping happens in the service layer, not the store, keeping `vector_store` primitives type-agnostic.

**Alternatives rejected**:

- **Query twice (once for sources with a source-id distinctness hack, once for snippets)**. Doubles Chroma round trips, still doesn't natively support "distinct by metadata field" — would need client-side grouping anyway.
- **Store one embedding per source (centroid / title-only)**. Huge quality regression; the whole point of chunk-level indexing is retrieval precision.
- **Fetch `top_k` and accept duplicates**. Fails FR-007 ("each source hit shows the best-matching excerpt" implies one excerpt per source).

---

## 5. Similarity threshold / noise floor (FR-005)

**Decision**: Single global distance cutoff `max_distance = 1.0`, applied to both entity types. Exposed as a constant in `search_service.py` (not user-configurable). Matches the existing `query_sources_tiered` default.

**Rationale**:

- A single threshold across types is required for spec correctness — spillover counts and ranking orderings must be comparable.
- `1.0` is the value already in production use for the RAG path (§tiered retrieval). Re-using it avoids introducing two tuning knobs.
- Exposing it as a module-level constant keeps it easy to change later without schema churn.

**Alternatives rejected**:

- **Per-type thresholds**. Tempting because snippet texts are shorter and produce different distance distributions than source chunks. Rejected because it breaks cross-type comparability and adds tuning complexity without validated need. Revisit if dogfooding shows snippet matches are systematically over- or under-filtered.
- **Percentile cutoff (e.g. drop bottom 30% by score)**. Adaptive but unpredictable — the same query returns different result counts depending on the distribution of other hits. Debug nightmare.

---

## 6. Chapter scope resolution

**Decision**: Two small SQL queries at search time (one for source IDs, one for snippet IDs), returning the in-scope UUID sets. Passed into Chroma's `where` clause as `{"<entity>_id": {"$in": [...]}}` metadata filters when scope ≠ `all`. For `FilterScopeAll`, no ID filter is added (Chroma returns everything within the `document_id` filter).

**Rationale**:

- Scope resolution is a pure relational operation — join `sources` / `snippets` against `chapter_sources` / `chapter_snippets`. Two indexed queries, sub-ms on a corpus of a few hundred items.
- Chroma's `$in` operator accepts arbitrarily large lists (no practical ceiling at this scale).
- For `FilterScopeChapter`, the in-scope set = `{items tagged to that chapter} ∪ {items with no chapter tags}` (per FR-012). This is expressible as one query with an `OUTER JOIN` + `(chapter_id = X OR chapter_id IS NULL)` filter per entity.
- For the spillover count, we also need the OUT-OF-SCOPE set. Cheapest path: run the broad Chroma query (no ID filter) and bucket results client-side using the in-scope set as a lookup. No second Chroma query required.

**Alternatives rejected**:

- **Denormalise chapter IDs into Chroma metadata** (per-chunk `chapter_ids: [...]`). Would let us filter inside Chroma. Rejected: chapter tags change (add/remove) frequently; keeping Chroma metadata in sync with relational state adds a write-path hazard for every tag edit. Current approach keeps tags as relational-only truth.
- **Cache the in-scope set on the document model**. Premature optimisation; DB queries are already fast enough at this scale.

---

## 7. Broaden action implementation (FR-016, SC-005)

**Decision**: The backend always returns the FULL result set (entire document, both in-scope and out-of-scope) with an explicit `in_scope: bool` flag per result. The HTMX partial renders both subsets into the DOM but hides out-of-scope results behind a CSS class controlled by the active scope state. The broaden action is a single HTMX `hx-get` that swaps the scope selector's value and toggles the wrapper class — no network request to `/search`.

**Rationale**:

- Exactly satisfies SC-005 ("single query request per typed query, regardless of scope changes").
- Avoids any session state, which would otherwise be needed to cache "the last full result set" on the server.
- Works correctly for the `scope=all` case too: `in_scope=true` for every result, `out_of_scope_count=0`, broaden control hidden.
- Spillover count is computed server-side from the same result list (`sum(not r.in_scope)`) so the indicator is consistent with what the DOM has.

**Alternatives rejected**:

- **Server-side session cache**. Introduces session state we don't otherwise need; implicated in multi-tab behaviour if the user has two docs open.
- **Re-query on broaden with `scope=all`**. Simpler server code but adds a second round trip per broaden action, failing SC-005's spirit even if letter-compliant (query text unchanged).

---

## 8. Backwards compatibility with the existing search endpoint

**Decision**: Extend the existing `GET /api/documents/{doc_id}/search` endpoint in place to return the new dual-group shape. Rewrite [partials/search_results.html](../../src/writer/templates/partials/search_results.html) to the new two-section layout, preserving the "Add to Bank" affordance (which today lets users promote a search-result chunk to a snippet) inside each source result card. No `-v2` endpoint.

**Rationale**:

- The existing endpoint has a single consumer (the search UI partial) and zero external API clients. Splitting to `-v2` would double the maintained surface for no benefit.
- The response shape does change — callers currently receive `{"results": [...], "query": "..."}`. The only caller expecting that shape is the template, which we're rewriting anyway. `SearchResponse` / `SearchResultItem` schemas (in [schemas.py](../../src/writer/models/schemas.py)) can be retired or kept as `@deprecated` and replaced with the new `SearchV2Response` family.
- Keeping one route preserves the existing URL in the HTMX form and avoids browser history / cache oddities during deploy.

**Alternatives rejected**:

- **Parallel `/search-v2` endpoint, leave old path untouched**. Extra surface, no user-visible benefit.
- **Keep the old response shape, layer the dual-group data alongside**. Union response shapes get ugly fast; "sources is a list, results is also a list, don't use both" is a footgun.

---

## 9. Backfill script idempotency

**Decision**: Deterministic vector ID `snip_<snippet_uuid>`. Backfill script uses ChromaDB's `collection.upsert()` (available in `chromadb>=0.4.15`, already pinned in the project) so running it twice is a no-op. Script queries Postgres for `(snippet.id, snippet.text, snippet.document_id, snippet.source_id, document.is_private)` tuples and upserts each one. Logs `n_embedded`, `n_skipped` (already-present IDs), `n_failed` at end.

**Rationale**:

- `upsert` is idempotent by contract and faster than `get→add` when most rows are already indexed.
- Single deterministic ID per snippet keeps delete-by-ID trivial (matches the entity-type discriminator pattern — one vector per snippet, one delete per snippet).
- Logging per-batch counts is enough visibility for a prototype; no separate telemetry.
- The same `upsert` call pattern is used by the create/update path in `snippet_service`, so there's exactly one code path for snippet vectorisation.

**Alternatives rejected**:

- **`add` + try/except on duplicate-ID errors**. Chroma's exception hierarchy on duplicate IDs is version-sensitive; `upsert` is the documented-stable API.
- **Truncate and re-embed all snippets on every run**. Unnecessarily expensive (embedding is the slow part) and breaks any caller currently mid-query.

---

## Summary — state after Phase 0

All `NEEDS CLARIFICATION` equivalents resolved. No technology additions beyond the existing ChromaDB + nlp-utils stack. No new services, no new containers, no new runtime dependencies. Proceed to Phase 1 (data-model, contracts, quickstart).
