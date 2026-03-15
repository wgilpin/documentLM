# Tasks: Vector RAG for Document Sources

**Input**: Design documents from `/specs/005-vector-rag-sources/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: TDD is MANDATORY for backend service code (business logic, data access, transformations).
Tests MUST NOT be written for frontend components or API endpoint handlers.
Tests MUST NOT call remote APIs (LLMs, external HTTP) — use mocks.
Write failing tests FIRST, confirm they fail, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add ChromaDB dependency and configure persistence directory

- [X] T001 Add `chromadb` dependency: run `uv add chromadb` and verify `pyproject.toml` is updated
- [X] T002 Add `./data/chroma` to `.gitignore` (ensure vector store data is never committed)
- [X] T003 Add a `./data/chroma` bind-mount volume to the app service in `docker-compose.yml` so ChromaDB data persists across container rebuilds (e.g., `- ./data/chroma:/app/data/chroma`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core model changes and config that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Add `IndexingStatus` enum (`pending`, `processing`, `completed`, `failed`) to `src/writer/models/enums.py`
- [X] T005 Add `indexing_status: Mapped[IndexingStatus]` (default `pending`) and `error_message: Mapped[str | None]` columns to the `Source` ORM model in `src/writer/models/db.py`
- [X] T006 Add `indexing_status: IndexingStatus` and `error_message: str | None` fields to `SourceResponse` Pydantic schema in `src/writer/models/schemas.py`
- [X] T007 Generate Alembic migration for the two new `sources` columns: run `uv run alembic revision --autogenerate -m "add_source_indexing_fields"` and verify the generated file under `migrations/versions/`
- [X] T008 Add `chroma_path: str = "./data/chroma"` to `Settings` in `src/writer/core/config.py`

**Checkpoint**: Foundation ready — all user story implementation can now begin

---

## Phase 3: User Story 1 — Source Upload Triggers Automatic Indexing (Priority: P1) 🎯 MVP

**Goal**: When a source is uploaded, its text is chunked and indexed into ChromaDB asynchronously without blocking the upload response. The `indexing_status` field tracks progress from `pending` → `processing` → `completed` (or `failed`).

**Independent Test**: Upload any source, confirm the response returns immediately with `indexing_status: "pending"`. Wait, then list sources and confirm status is `"completed"`. Check that ChromaDB contains chunks with the matching `source_id` metadata.

### Tests for User Story 1

> **Write tests FIRST and confirm they FAIL before any implementation.**
> Tests go in `tests/unit/` (service logic) or `tests/integration/` (DB/service integration).
> Do NOT write tests for API endpoints or frontend components.
> Do NOT call remote APIs in tests — mock all external dependencies.

- [X] T009 [P] [US1] Write failing unit tests for `index_source` in `tests/unit/test_vector_store.py`: verify chunk IDs follow `"{source_id}_{i}"` format, metadata contains `source_id`, and the collection `add` method is called with correct arguments (mock `chromadb.Collection`)
- [X] T010 [P] [US1] Write failing unit tests for `run_indexing` in `tests/unit/test_indexer.py`: verify `indexing_status` transitions (`pending` → `processing` → `completed`), that `chunk_sentences` is called on the source `content`, that on exception the status is set to `failed` with `error_message` populated, and that calling `run_indexing` when status is already `processing` or `completed` is a no-op (mock DB session and `vector_store.index_source`)

### Implementation for User Story 1

- [X] T011 [US1] Create `src/writer/services/vector_store.py` with `get_collection() -> chromadb.Collection` (lazy-initialised singleton using `settings.chroma_path`) and `index_source(source_id: uuid.UUID, chunks: list[str]) -> None` — wrap ChromaDB client creation in `asyncio.to_thread()` at call sites; log at INFO on success
- [X] T012 [US1] Create `src/writer/services/indexer.py` with `async def run_indexing(source_id: uuid.UUID, db: AsyncSession) -> None`: at the start, re-fetch the source and return early (no-op) if `indexing_status` is already `processing` or `completed` (idempotency guard against duplicate background tasks); otherwise log at INFO when status → `processing`; call `chunk_sentences(source.content, chunk_size=1000, chunk_overlap=100)` from `nlp_utils`; call `vector_store.index_source`; log at INFO when status → `completed`; on any exception set status → `failed`, write `error_message`, log at ERROR level
- [X] T013 [US1] Modify `src/writer/api/sources.py`: inject `BackgroundTasks` into both `POST /` and `POST /pdf` upload handlers; after the source is created, enqueue `run_indexing(source_id=source.id, db=db)` as a background task

**Checkpoint**: User Story 1 is fully functional — upload returns immediately, indexing completes in background, status is queryable via list endpoint

---

## Phase 4: User Story 2 — Agent Answers Use Relevant Document Chunks (Priority: P2)

**Goal**: The drafter, planner, and chat agents retrieve the top 5 semantically relevant chunks from ChromaDB instead of receiving full document/source text. Agent answers remain accurate; no context-window overflow for large documents.

**Independent Test**: Index a large source (50+ pages). Invoke the drafter agent with a specific question. Confirm the agent returns a relevant answer. Inspect the injected context and verify it contains only retrieved chunks (not the full document text).

### Tests for User Story 2

> Write tests FIRST, confirm they FAIL, then implement. No remote API calls. No endpoint tests.

- [X] T014 [P] [US2] Write failing unit tests for `query_sources` in `tests/unit/test_vector_store.py`: verify the function calls `collection.query` with correct `query_texts` and `n_results=5`, and returns the `documents` list flattened to `list[str]` (mock `chromadb.Collection`)
- [X] T015 [P] [US2] Write failing unit tests for the updated `invoke_drafter` and `invoke_planner` in `tests/unit/test_agent_service.py`: verify neither function concatenates raw `source.content` into the context, and that `vector_store.query_sources` is called with the appropriate query text (mock `vector_store.query_sources` to return a fixed list of strings)

### Implementation for User Story 2

- [X] T016 [US2] Add `query_sources(query_text: str, top_k: int = 5) -> list[str]` to `src/writer/services/vector_store.py`: call `collection.query(query_texts=[query_text], n_results=top_k)`, return the flattened documents list; log query text and result count at DEBUG level
- [X] T017 [US2] Modify `invoke_drafter` in `src/writer/services/agent_service.py`: replace the `source_index` dict and `list_sources`/`get_source` closures with a single `query_sources(comment.body + " " + comment.selected_text)` call; inject the returned chunks as a `--- RELEVANT SOURCE CHUNKS ---` block in the message
- [X] T018 [US2] Modify `invoke_planner` in `src/writer/services/agent_service.py`: replace full `research_sources` concatenation with `query_sources(overview, top_k=5)` call; set `session_state["research_sources"]` to the joined chunks
- [X] T019 [US2] Modify `invoke_chat_agent` in `src/writer/services/chat_service.py`: add a `query_sources` call using the last user message text; append retrieved chunks as a `--- RELEVANT SOURCES ---` block to the prompt (keep the existing current-document injection unchanged — that is the document being edited, not source references)

**Checkpoint**: User Stories 1 and 2 both work — agents use vector retrieval, no context overflow on large documents

---

## Phase 5: User Story 3 — Source Deletion Removes Indexed Content (Priority: P3)

**Goal**: When a source is deleted from the relational database, all corresponding ChromaDB chunks are removed. No orphaned vector entries remain after deletion.

**Independent Test**: Index a source with distinctive text. Delete it. Query ChromaDB with text from that source and confirm zero results are returned.

### Tests for User Story 3

> Write tests FIRST, confirm they FAIL, then implement. No remote API calls. No endpoint tests.

- [X] T020 [P] [US3] Write failing unit tests for `delete_source_chunks` in `tests/unit/test_vector_store.py`: verify `collection.delete(where={"source_id": str(source_id)})` is called with the correct filter (mock `chromadb.Collection`)
- [X] T021 [P] [US3] Write failing integration test in `tests/integration/test_rag_pipeline.py` using `chromadb.EphemeralClient()`: index a source → delete it via `delete_source_chunks` → query → assert empty result; also add a round-trip test: index → query → assert chunks returned
- [X] T022 [P] [US3] Write failing unit tests for the modified `delete_source` in `tests/unit/test_source_service.py`: verify `vector_store.delete_source_chunks` is called with the correct `source_id` before the DB deletion, and that if `delete_source_chunks` raises, the exception propagates and the relational record is NOT deleted (mock `vector_store.delete_source_chunks` and the DB session)

### Implementation for User Story 3

- [X] T023 [US3] Add `delete_source_chunks(source_id: uuid.UUID) -> None` to `src/writer/services/vector_store.py`: call `collection.delete(where={"source_id": str(source_id)})`; log the deletion at INFO level
- [X] T024 [US3] Modify `delete_source` in `src/writer/services/source_service.py`: call `await asyncio.to_thread(vector_store.delete_source_chunks, source_id)` before deleting the relational record; log at INFO level; if ChromaDB deletion raises, log at ERROR and re-raise (do not silently swallow)

**Checkpoint**: All three user stories are independently functional. Deleting a source fully removes it from both the relational DB and the vector store.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, type checking, and final cleanup

- [X] T025 [P] Run `uv run ruff check --fix src/ tests/` and `uv run ruff format src/ tests/` — fix any lint or formatting issues introduced by this feature
- [X] T026 [P] Run `uv run mypy src/` — resolve all type errors in the new and modified files
- [X] T027 Run `uv run pytest` — confirm all existing tests pass alongside the new tests
- [X] T028 Run the quickstart.md validation steps manually: upload a PDF, observe status transitions, ask the chat agent a question, delete the source, confirm no chunks remain

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **User Stories (Phases 3–5)**: All depend on Foundational completion
  - US2 depends on US1 being complete (needs indexed chunks to query)
  - US3 can proceed in parallel with US1 after Phase 2 (deletion cascade has no dependency on indexing)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Only depends on Phase 2 — no story dependencies
- **US2 (P2)**: Depends on US1 being complete (needs indexed chunks to query)
- **US3 (P3)**: Only depends on Phase 2 — can be developed in parallel with US1

### Within Each User Story

- Tests MUST be written and confirmed FAILING before implementation (TDD — mandatory)
- Tests MUST NOT be written for API endpoints or frontend components
- Models before services
- Services before endpoint wiring
- Story complete before moving to next priority

### Parallel Opportunities

- T009 and T010 can run in parallel (different test files)
- T014 and T015 can run in parallel (different test files)
- T020, T021, and T022 can run in parallel (different test files)
- T025 and T026 can run in parallel (ruff and mypy are independent)
- Once Phase 2 is complete, US1 and US3 can start in parallel
- Once US1 is complete, US2 can begin

---

## Parallel Example: User Story 1

```bash
# Run in parallel — different files, no dependencies between them:
Task T009: "Write failing unit tests for index_source in tests/unit/test_vector_store.py"
Task T010: "Write failing unit tests for run_indexing in tests/unit/test_indexer.py"

# Then run in parallel — different service files:
Task T011: "Create src/writer/services/vector_store.py"
Task T012: "Create src/writer/services/indexer.py"

# Then, after T011 and T012:
Task T013: "Modify src/writer/api/sources.py to wire BackgroundTasks"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`uv add chromadb`, gitignore, docker-compose volume)
2. Complete Phase 2: Foundational (model fields, migration, config)
3. Complete Phase 3: User Story 1 (indexing pipeline)
4. **STOP and VALIDATE**: upload a source, confirm `indexing_status` transitions, inspect ChromaDB chunks
5. Demo/deploy if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → non-blocking indexing with status tracking (MVP!)
3. US2 → agent answers use retrieved chunks instead of full text
4. US3 → cascading delete keeps vector store clean
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers (after Phase 2 complete):

- Developer A: US1 (indexing pipeline)
- Developer B: US3 (deletion cascade) — independent after Phase 2
- Developer C: Prepares US2 test stubs while waiting for US1 to complete

---

## Notes

- `[P]` tasks = different files, no shared dependencies
- `[Story]` label maps each task to a specific user story for traceability
- Each user story is independently completable and testable
- Verify tests FAIL before implementing (TDD mandate)
- Commit after each task or logical group
- Stop at each **Checkpoint** to validate the story independently
- ChromaDB uses `asyncio.to_thread()` at all call sites — never block the event loop with synchronous client calls
- Integration tests use `chromadb.EphemeralClient()` — no filesystem side effects, no cleanup needed
