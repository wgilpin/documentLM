# Quickstart: Semantic Search over Sources and Snippets

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-04-20

## Prerequisites

- spec 017 (`source_chapters` + `snippet_chapters` join tables) deployed.
- Existing ChromaDB persistent directory (`./data/chroma`) present — this feature reuses it.
- `uv` environment set up and `docker-compose` bringing up PostgreSQL.

## One-time setup

Ask before running `docker` commands (per `CLAUDE.md`).

```bash
# 1. Bring up Postgres
docker-compose up -d postgres

# 2. Confirm schema is current (this spec adds no migrations of its own; it just
#    verifies spec 017's join tables are present).
cd /Users/will/projects/document-projects/documentLM && uv run alembic upgrade head

# 3. Backfill snippet embeddings for any pre-existing snippets.
#    Idempotent — safe to re-run.
cd /Users/will/projects/document-projects/documentLM && uv run python scripts/backfill_snippet_embeddings.py

# 4. Start the dev server.
cd /Users/will/projects/document-projects/documentLM && uv run uvicorn writer.main:app --reload
```

Expected backfill output (example):

```text
backfill_snippet_embeddings: scanned=42 embedded=40 skipped=2 failed=0
```

`skipped` counts snippets whose vectors already existed (benign). `failed > 0` means the embedding model was unavailable — inspect the log and re-run.

## Smoke test (manual UI)

1. Open a document that has ≥ 2 chapters, ≥ 5 sources with mixed chapter tags, and ≥ 10 snippets with mixed chapter tags.
2. Place the caret inside a specific chapter — watch the sidebar filter control (from spec 017) pick up the chapter, same signal the search scope uses.
3. Click the search control, type `"diminishing returns"` (or any substantive query). Observe:
   - Two result groups render: **Sources** and **Snippets**, each ordered by similarity.
   - Source cards show the source title + the best-matching excerpt.
   - Snippet cards show the snippet text + source attribution + chapter label (or "document-level").
   - The scope selector defaults to the focused chapter.
4. If there are matches in other chapters, a spillover indicator appears — e.g. "3 in this chapter, 5 in others". Click **Show all**. Expected:
   - All matches now visible (both groups).
   - No new request to `/search` in DevTools Network tab — the broaden swaps visibility on already-rendered cards (research §7).
5. Click a source result → the sources pane scrolls to / highlights that source.
6. Click a snippet result → the snippet bank scrolls to / highlights that snippet card.
7. Switch the scope selector back to "This chapter" → out-of-scope cards hide again.
8. Switch the caret to a different chapter → next search defaults to the new chapter. Previous "Show all" override does not persist (FR-018).
9. Place the caret outside any chapter (e.g. document preamble) → scope defaults to "Entire document"; no spillover indicator appears.

## Smoke test (API, unauthenticated example)

```bash
# Authenticated requests: use the session cookie from a logged-in browser.
# Example with httpie + cookie jar:
http -b --session=./s.json GET \
  "localhost:8000/api/documents/<doc_uuid>/search" \
  q=="diminishing returns" \
  scope==chapter:<chapter_uuid>
```

Expected: JSON matching the shape in [contracts/search-api.md](./contracts/search-api.md). `sources.in_scope` is ordered by descending score; `snippets.in_scope` likewise.

## Unit-test commands

```bash
# Service-layer tests (TDD targets):
cd /Users/will/projects/document-projects/documentLM && uv run pytest tests/unit/test_search_service.py -v
cd /Users/will/projects/document-projects/documentLM && uv run pytest tests/unit/test_snippet_service.py::test_create_snippet_schedules_embedding -v
cd /Users/will/projects/document-projects/documentLM && uv run pytest tests/unit/test_vector_store.py -v

# Full test suite (quality gate before commit):
cd /Users/will/projects/document-projects/documentLM && uv run pytest
```

## Validation against spec success criteria

| SC | How to verify |
|---|---|
| SC-001 (< 1 s p95) | Time five successive searches against a real doc with ≥ 100 sources + snippets; all < 1 s. |
| SC-002 (relevance) | Seed a query with a known match; assert at least one of the top 3 in each group matches intent. |
| SC-003 (scope default) | Smoke test step 3. |
| SC-004 (spillover accuracy) | Inspect JSON response: `out_of_scope_count` equals (broader-scope in_scope list length) − (narrower-scope in_scope list length) for the same query. |
| SC-005 (no re-query on broaden) | DevTools Network tab during smoke test step 4. |
| SC-006 (backfill coverage) | Post-backfill: `SELECT COUNT(*) FROM snippets` equals the count of snippet vectors in the collection (inspect via Chroma REPL or a small `scripts/audit_snippet_coverage.py`). |
| SC-007 (read-only) | Take an `md5(SELECT *)` hash of `snippets` and `sources` tables before and after 20 searches; hashes must match. |
| SC-008 (no-chapters behaviour) | Open a document with zero chapters; scope selector is hidden; no spillover indicator ever appears. |

## Troubleshooting

- **"Snippets group always empty"** → check the backfill ran (step 3). Also check `entity_type` filter on the search path is `{"$in": ["source", "snippet"]}`, not `"source"` only.
- **"Agent RAG started returning snippet text as sources"** → audit the agent-side RAG call sites (`query_sources`, `query_sources_tiered`, `query_sources_with_metadata`); they must filter on `entity_type: "source"`.
- **"Broaden re-issues the query on every click"** → regressed against research §7. Check `search_results.html` uses CSS visibility toggles, not `hx-get` back to the endpoint, for the broaden control.
- **"Stale chapter still selected after delete"** → FR-021 fallback: check the service's scope-validation branch logs a WARN and degrades to `scope=all` when the chapter no longer exists.
