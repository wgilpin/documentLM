# Research: Vector RAG for Document Sources

**Branch**: `005-vector-rag-sources` | **Date**: 2026-03-15

---

## Decision 1: Vector Store — ChromaDB

**Decision**: Use ChromaDB with its default embedding function (`all-MiniLM-L6-v2` via `chromadb`'s built-in `DefaultEmbeddingFunction`).

**Rationale**: Specified in the feature spec. ChromaDB is a lightweight, file-backed vector store that requires no external service, matches the project's Docker/local-first philosophy, and its default embedding model runs locally with no API key. Persistence to a local directory (`./data/chroma`) is a one-line config option.

**Alternatives considered**:
- pgvector (PostgreSQL extension): Would keep everything in one DB, but requires Docker image change, a separate extension install, and more complex similarity query syntax. Overhead unjustified for a demo prototype.
- Pinecone / Weaviate: Cloud-hosted, incompatible with the "no remote API calls" constraint in tests.
- FAISS: Lower-level, no built-in persistence or metadata filtering; more code to maintain.

---

## Decision 2: Chunker — `nlp_utils.chunk_sentences`

**Decision**: Use `chunk_sentences(text, chunk_size=1000, chunk_overlap=100)` from the local `nlp-utils` package.

**Rationale**: Already a project dependency. The function is a recursive sentence/paragraph chunker (paragraph → sentence → word → character fallback). `chunk_size=1000` characters fits well within typical LLM context window limits for injected chunks, and `chunk_overlap=100` gives continuity across chunk boundaries. Chunk IDs will be deterministic: `f"{source_id}_{index}"`.

**Alternatives considered**:
- `chunk_overlap=0`: Simpler but risks losing context at boundaries.
- `chunk_size=500`: More granular retrieval but increases ChromaDB collection size and embedding count.

---

## Decision 3: Background Indexing — FastAPI `BackgroundTasks`

**Decision**: Use FastAPI's built-in `BackgroundTasks` to trigger the indexing pipeline after the upload response is sent.

**Rationale**: Zero additional infrastructure. The pipeline (extract → chunk → embed → store) is I/O-bound and runs in the same process. Fits the YAGNI principle — no Celery, Redis, or separate worker process needed for a demo prototype.

**Alternatives considered**:
- `asyncio.create_task`: Works but is less visible in FastAPI context; `BackgroundTasks` is the idiomatic FastAPI approach and hooks into the request lifecycle.
- Celery + Redis: Far more infrastructure than needed for a prototype; rejected.

**Status-update pattern**: The background task wraps the pipeline in a try/except, updating `indexing_status` to `processing` at start and `completed` or `failed` at end. The `error_message` field captures the exception string on failure.

---

## Decision 4: ChromaDB Collection Strategy — One Collection per Application

**Decision**: Use a single ChromaDB collection named `"sources"` for all source chunks, keyed by `source_id` metadata for filtering and deletion.

**Rationale**: Simplest possible design. Filtering by `where={"source_id": str(source_id)}` is efficient in ChromaDB. A per-document or per-source collection would create collection management overhead.

**Chunk ID format**: `"{source_id}_{chunk_index}"` (e.g., `"abc123_0"`, `"abc123_1"`) — deterministic, unique, and traceable.

---

## Decision 5: Retrieval — Top-5 Semantic Search

**Decision**: Use `collection.query(query_texts=[query], n_results=5)` at agent invocation time.

**Rationale**: Specified in the feature spec (`top_k=5`). The query text is the user's prompt / instruction text. Retrieved chunks are joined with newline separators and injected into the agent context in place of full source text.

**Sources with non-"completed" status**: Silently excluded from retrieval. ChromaDB only contains chunks for successfully indexed sources, so this is automatic — no filtering needed.

---

## Decision 6: Async/Sync ChromaDB Client

**Decision**: Use ChromaDB's synchronous `chromadb.PersistentClient` wrapped in `asyncio.to_thread()` for calls from async FastAPI handlers.

**Rationale**: ChromaDB's async client is in alpha and has known stability issues as of early 2026. The synchronous client is stable. Wrapping individual ChromaDB calls in `asyncio.to_thread()` is idiomatic for calling blocking I/O from async code in Python 3.13+.

---

## Decision 7: Persistence Directory — Settings-Configured

**Decision**: Add `chroma_path: str = "./data/chroma"` to `Settings` (pydantic-settings). The value is read from the `CHROMA_PATH` environment variable and defaults to `./data/chroma` relative to the working directory.

**Rationale**: Consistent with the project's existing config pattern (all settings via pydantic-settings from `.env`). The `./data/` directory is gitignored.

---

## Decision 8: Vector Store Module Location

**Decision**: New module `src/writer/services/vector_store.py` exposes three functions:
- `index_source(source_id, chunks)` — add chunks to ChromaDB
- `query_sources(query_text, top_k=5)` — semantic search
- `delete_source(source_id)` — remove all chunks for a source

**Rationale**: Keeps the ChromaDB interface boundary isolated in one file. Service functions remain thin orchestrators. Easy to mock in unit tests.
