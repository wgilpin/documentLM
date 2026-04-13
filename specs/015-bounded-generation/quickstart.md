# Developer Quickstart: Bounded Generation & Curation Workflow

**Feature**: 015-bounded-generation
**Date**: 2026-04-13

---

## Prerequisites

- Docker + docker-compose running (`docker-compose up -d postgres`)
- `uv` installed
- Node.js + npm (for editor bundle rebuild)

---

## Step 1: Install new dependency

```bash
cd /Users/will/projects/document-projects/documentLM
uv add pymupdf4llm
```

> `pymupdf4llm` pulls in `pymupdf` (fitz). `pypdf` can remain — it is used nowhere else after this feature lands.

---

## Step 2: Run the migration

```bash
uv run alembic revision --autogenerate -m "add_snippets_table"
# Review the generated migration, then:
uv run alembic upgrade head
```

---

## Step 3: Run tests (TDD loop)

Run the unit tests before touching implementation code:

```bash
cd /Users/will/projects/document-projects/documentLM
uv run pytest tests/unit/
```

All new service logic goes in `src/writer/services/` and gets tested in `tests/unit/`.

---

## Step 4: Lint and type-check after each file

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

---

## Step 5: Rebuild the JS bundle after any `editor.js` change

```bash
npm run build:dev
```

> **Always run this after any change to `static/editor.js`** — `editor.bundle.js` is what the browser loads.

---

## New files this feature adds

```text
src/writer/
├── api/snippets.py            # Snippet CRUD endpoints
├── api/search.py              # Semantic search endpoint
├── api/generation.py          # Bounded generate endpoint
└── services/snippet_service.py # Snippet business logic

migrations/versions/
└── xxxx_add_snippets_table.py

tests/unit/
└── test_snippet_service.py    # TDD tests for snippet service

static/
└── editor.js                  # Updated — add bundle UI + insertBoundedSuggestion()

templates/partials/
├── snippet_card.html          # Single snippet card
├── snippet_bank.html          # Full snippet bank list
├── search_results.html        # Search result cards
└── bounded_suggestion.html    # Generation result partial
```

---

## Key service functions to implement (TDD)

| Service | Function | Tests |
| --- | --- | --- |
| `snippet_service` | `create_snippet` | create happy path, wrong doc 404 |
| `snippet_service` | `list_snippets` | empty, multiple, ordering |
| `snippet_service` | `delete_snippet` | happy path, not found, wrong user |
| `snippet_service` | `update_snippet` | note/tag update, not found |
| `snippet_service` | `get_snippet_with_source_title` | joins source.title |
| `agent_service` | `invoke_bounded_drafter` | mock run_agent_text; verify prompt contains document content, snippets, and intent |
| `search_service` | `search_document_corpus` | mock vector_store, verify result mapping |

Mock `vector_store.query_sources_with_metadata` in all search tests.
Mock `run_agent_text` in all generation tests.
Never call a real LLM in tests.
