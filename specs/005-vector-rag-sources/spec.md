# Feature Specification: Vector RAG for Document Sources

**Feature Branch**: `005-vector-rag-sources`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: Vector RAG implementation using ChromaDB and nlp-utils for document sources to prevent context window overflow during agent calls

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Source Upload Triggers Automatic Indexing (Priority: P1)

When a user uploads a document source, the system automatically extracts, chunks, embeds, and indexes its content in the background without blocking the upload confirmation. The user sees an "indexing" status and later sees "ready" once indexing completes.

**Why this priority**: This is the foundation of the RAG system — without indexed content, retrieval cannot work. All other stories depend on this pipeline being operational.

**Independent Test**: Can be tested by uploading a document and observing that (1) the upload succeeds immediately, (2) the source transitions through "pending" → "processing" → "completed" status, and (3) the vector store contains chunks linked to that source.

**Acceptance Scenarios**:

1. **Given** a user uploads a PDF or text document, **When** the upload completes, **Then** the system returns success immediately and sets the source status to "pending" or "processing"
2. **Given** a source is being indexed, **When** the background process finishes, **Then** the source status transitions to "completed" and the content is queryable
3. **Given** the indexing process encounters an error, **When** the failure occurs, **Then** the source status is set to "failed" and the error message is recorded and visible

---

### User Story 2 - Agent Answers Use Relevant Document Chunks (Priority: P2)

When a user asks the chat agent a question, the agent retrieves only the most relevant text excerpts from indexed sources rather than loading entire documents. The answers remain accurate and the conversation does not fail due to document size.

**Why this priority**: This is the core user-facing benefit of RAG — reliable, accurate answers regardless of how large or numerous the source documents are.

**Independent Test**: Can be tested by uploading a large document and asking a specific question; verify the agent returns a relevant answer and only the top relevant chunks (not the full document) were injected into the agent context.

**Acceptance Scenarios**:

1. **Given** a user has indexed document sources, **When** they ask the agent a question, **Then** the agent receives only the top 5 most semantically relevant chunks from those sources
2. **Given** multiple sources are indexed, **When** a query is issued, **Then** chunks from the most relevant sources are returned regardless of which document they come from
3. **Given** a source is in "failed" or "pending" status, **When** a query is issued, **Then** only content from "completed" sources is included in retrieval

---

### User Story 3 - Source Deletion Removes Indexed Content (Priority: P3)

When a user deletes a source, all corresponding vector index entries are also removed automatically. Subsequent agent queries do not surface content from the deleted source.

**Why this priority**: Data lifecycle consistency — users expect that deleting a source fully removes it from the system, including from AI answers.

**Independent Test**: Can be tested by indexing a source with distinctive content, deleting it, then asking a question that would previously have matched that content and confirming it no longer appears in the answer.

**Acceptance Scenarios**:

1. **Given** a source has been indexed and a user deletes it, **When** the deletion completes, **Then** all vector index entries associated with that source are also deleted
2. **Given** a deleted source's content was previously returned in queries, **When** the same query is issued after deletion, **Then** no content from the deleted source appears in results

---

### Edge Cases

- What happens when a source file is empty or contains no extractable text?
- How does the system handle indexing of a very large document (hundreds of pages)?
- What if the vector store is unavailable when a source deletion is requested — is the relational record still deleted?
- What if the same source is submitted for indexing while already in "processing" status?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST transition a newly uploaded source to an indexing queue without blocking the upload response
- **FR-002**: System MUST extract text from source files, segment it into chunks, embed the chunks, and persist them to the vector store asynchronously
- **FR-003**: System MUST record `indexing_status` (pending, processing, completed, failed) on each source and update it as the pipeline progresses
- **FR-004**: System MUST record an `error_message` on the source when indexing fails
- **FR-005**: System MUST store a `source_id` reference on every vector store chunk to maintain the mapping back to the relational record
- **FR-006**: System MUST query the vector store at query time and retrieve the top 5 most semantically relevant chunks for the given input
- **FR-007**: System MUST inject only the retrieved chunks — not full document text — into the agent context window
- **FR-008**: System MUST delete all vector store entries associated with a source when that source is deleted from the relational database
- **FR-009**: System MUST use the project-standard text chunker for all text segmentation
- **FR-010**: System MUST persist the vector store to a local directory so indexed content survives application restarts

### Key Entities

- **Source**: A user-uploaded document tracked in the relational database; carries `indexing_status` and `error_message` fields in addition to existing attributes
- **Vector Chunk**: A text segment stored in the vector store, representing a portion of a source document; references its parent source via a `source_id` metadata field
- **Indexing Pipeline**: The asynchronous process that transforms a raw source into queryable vector chunks (extract → chunk → embed → store)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Source upload completes and returns a response to the user within the same time as before this feature was introduced — indexing must not block the upload response
- **SC-002**: 100% of deleted sources have their corresponding vector store entries removed — no orphaned chunks remain after deletion
- **SC-003**: Agent answers for document-related questions remain accurate after this change with no regression compared to full-document injection
- **SC-004**: Sources larger than 50 pages are successfully indexed without errors or timeouts
- **SC-005**: Indexing status is always accurate — a source never stays in "processing" state after the pipeline has finished or failed
- **SC-006**: All unit and integration tests pass, including tests for chunking, retrieval, and deletion synchronization

## Assumptions

- The existing source upload endpoint already extracts and stores file content; this feature adds downstream processing after that point
- The default local embedding model is sufficient for acceptable retrieval quality; no external embedding API is required
- "Top 5 chunks" (`top_k=5`) is an acceptable starting retrieval depth and can be tuned in a future iteration
- Sources with a non-"completed" indexing status are silently skipped during retrieval (no error surfaced to the user)
- If a source is submitted for re-indexing while its status is already `processing` or `completed`, the new indexing request is silently ignored to prevent duplicate chunks accumulating in the vector store
- The vector store persistence directory will be configurable via application settings, defaulting to a standard location within the project data directory
