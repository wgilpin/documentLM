# Contract: Search API

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md)
**Date**: 2026-04-20

This spec **extends in place** the existing endpoint at [src/writer/api/search.py](../../../src/writer/api/search.py). No new routes are introduced. The old response shape (`SearchResponse` with a flat `results` list) is removed; the single existing consumer (the `partials/search_results.html` partial) is rewritten in lockstep.

---

## `GET /api/documents/{doc_id}/search`

### Request

| Param | In | Type | Default | Notes |
|---|---|---|---|---|
| `doc_id` | path | `uuid` | — | Must belong to the authenticated user. |
| `q` | query | `str` | — | Required. Trimmed server-side; empty / whitespace-only → 400. |
| `scope` | query | `str` | `"all"` | One of `"all"`, `"doc-level"`, or `"chapter:<uuid>"`. Parsed via existing `parse_filter_scope`. Unknown values → 400. |
| `top_k` | query | `int` | 10 | Per-group cap. Bounded `[1, 20]`. |

### Authentication

Same as existing: `Depends(get_current_user)`. A user may only search documents they own.

### Response — `Accept: text/html` or `HX-Request: true`

Rendered [partials/search_results.html](../../../src/writer/templates/partials/search_results.html). Structure:

```html
<div class="search-results" data-scope="{{ scope.kind }}">
  <section class="search-results-group" data-group="sources">
    <header>Sources <span class="count">{{ sources.in_scope | length }}</span></header>
    <!-- cards for in_scope sources -->
    {% if sources.out_of_scope_count > 0 %}
    <p class="search-spillover">
      {{ sources.in_scope | length }} in this chapter, {{ sources.out_of_scope_count }} in others
      <a hx-get="{{ broaden_url }}" hx-target="#search-results" hx-swap="outerHTML">
        Show all
      </a>
    </p>
    {% endif %}
  </section>
  <section class="search-results-group" data-group="snippets">
    <!-- symmetric structure -->
  </section>
</div>
```

Each card:

- **Source card**: title, excerpt (best-matching chunk), score, a "Go to source" action (re-uses the existing `scrollToCharOffset` helper wired to the sources pane), and the existing "Add to Bank" control preserved from today's search UI.
- **Snippet card**: snippet text, source attribution (title + link), chapter label ("document-level" when `chapter_ids` is empty), score, a "Go to snippet" action that scrolls/flashes the matching card in `#snippet-list`.

The broaden `<a>` re-fetches the endpoint with `scope=all` (Research §7 chose client-side CSS toggling for the non-HTMX path; for the HTMX path the simplest implementation is a tiny follow-up request that re-renders with the broader scope — still one click, no typed re-query). The JSON contract below intentionally permits both interaction patterns.

### Response — `Accept: application/json` (no `HX-Request` header)

```json
{
  "query": "diminishing returns in team size",
  "scope": {
    "kind": "chapter",
    "chapter_id": "c7a9b0e2-…"
  },
  "sources": {
    "in_scope": [
      {
        "source_id": "8f3c…",
        "title": "Mythical Man-Month (Brooks, 1975)",
        "excerpt": "Adding manpower to a late software project makes it later…",
        "score": 0.87,
        "in_scope": true
      }
    ],
    "out_of_scope_count": 4
  },
  "snippets": {
    "in_scope": [
      {
        "snippet_id": "41aa…",
        "text": "The bearing of a child takes nine months, no matter how many women are assigned.",
        "source_id": "8f3c…",
        "source_title": "Mythical Man-Month (Brooks, 1975)",
        "chapter_ids": ["c7a9b0e2-…"],
        "score": 0.82,
        "in_scope": true
      }
    ],
    "out_of_scope_count": 2
  }
}
```

### Response codes

| Code | Reason |
|---|---|
| `200` | Successful search (including zero results — both groups return empty `in_scope` arrays and `out_of_scope_count: 0`). |
| `400` | Empty query, or unparseable `scope`, or `top_k` out of range. |
| `401` | Missing/invalid auth. |
| `404` | `doc_id` does not exist or does not belong to the authenticated user. |

### Side effects

**None.** The endpoint is read-only (FR-011). Embedding generation happens on snippet write paths, not here.

### Performance contract

- Single ChromaDB query per request. No N+1 SQL.
- Source titles are batch-loaded (`SELECT id, title FROM sources WHERE id IN (...)`).
- Snippet chapter associations are batch-loaded (`SELECT * FROM chapter_snippets WHERE snippet_id IN (...)`).
- Target: p95 < 1 s for a corpus of a few hundred sources + snippets within a single document (SC-001).

### Scope-fallback behaviour (FR-021)

If the requested `chapter:<uuid>` refers to a chapter that no longer exists in the target document (stale tab, chapter deleted mid-session), the service degrades to `scope=all` silently and logs a WARN. The echoed `scope` in the response reflects the degraded value so the client can update its scope selector.

### Entity-type discriminator (internal)

Not visible in the contract but important for internal correctness: the backend emits a ChromaDB `where` clause that always scopes by `document_id` and filters by `entity_type ∈ {"source", "snippet"}`. The agent-side RAG retrieval paths MUST be audited during implementation to add `entity_type: "source"` to their own `where` clauses — otherwise they will start pulling snippets into agent context, which is out of scope for this spec.

---

## Snippet write-path side effect (background embedding)

Not a new endpoint, but documenting the embedding contract the existing snippet endpoints now honour:

- `POST /api/documents/{doc_id}/snippets` — schedules a background task to embed + upsert the snippet vector after the row is committed. Response shape unchanged.
- `PUT /api/snippets/{snippet_id}` — if the update modifies `text`, schedules a background re-embed. If only `note` or `tag` changed, no embedding work.
- `DELETE /api/snippets/{snippet_id}` — synchronously deletes the snippet's vector by deterministic ID before deleting the row (or after — order doesn't matter as long as both happen; pick whichever simplifies error handling).

Failure of the background embedding logs at ERROR and does not reach the client. The snippet stays saved; it's simply invisible in search until the backfill script re-runs or an equivalent re-embed path is triggered.

---

## Backfill script

Not a network contract but part of the feature surface:

```bash
uv run python scripts/backfill_snippet_embeddings.py [--user-id UUID] [--dry-run]
```

- Iterates every snippet (optionally scoped to one user for testing).
- For each snippet: checks whether a vector with ID `snip_<snippet_uuid>` exists in the owning user's collection; if not, embeds + upserts it.
- Idempotent by design (upsert). Safe to run any number of times.
- Logs `{n_scanned, n_embedded, n_skipped, n_failed}` at end. Exit code `0` on success, `1` if any snippet failed.
- Also stamps `entity_type: "source"` on any existing source chunks that lack the key (one-time normalisation for the discriminator rollout).
