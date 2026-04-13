# Feature Specification: Bounded Generation & Curation Workflow

**Feature Branch**: `015-bounded-generation`
**Created**: 2026-04-13
**Status**: Draft
**Input**: User description: "Bounded Generation and Curation Workflow"

## Overview

Writers and researchers frequently rely on AI tools that generate text with minimal human oversight, leading to outputs disconnected from their actual source material. This feature replaces that pattern with a deliberate, evidence-first workflow: users must first gather and curate evidence from their sources before any text can be generated. The AI produces only what the user explicitly authorises, bounded by snippets they have selected and an intent they have written themselves.

The core loop is: **Search → Select → Synthesize**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest and Browse a Source Document (Priority: P1)

A researcher has a PDF or URL they want to use as a source. They add it to their workspace, and the system converts it into a readable, browsable format inside the tool. They can then open the document in the side panel to read it.

**Why this priority**: This is the foundation of the entire workflow — without ingested, readable sources, no other functionality is possible. It must work reliably before anything else.

**Independent Test**: A user uploads a PDF or pastes a URL. The system processes it and displays the parsed text in the Document View panel. No other features need to be present for this to deliver value as a basic document reader.

**Acceptance Scenarios**:

1. **Given** a user has a PDF file, **When** they add it as a source, **Then** the document's text content is readable in the Document View within the side panel.
2. **Given** a user adds a URL, **When** the system processes it, **Then** the extracted text is displayed in the Document View in a clean, readable format.
3. **Given** a source has been ingested, **When** the user opens the Document View, **Then** headings and paragraph structure from the original document are preserved.
4. **Given** a source fails to process, **When** the user tries to open it, **Then** a clear error message explains what went wrong.

---

### User Story 2 - Save Text Snippets to the Scratchpad (Priority: P1)

While reading a source document in the Document View, the user highlights a passage they find relevant. A prompt appears allowing them to save that selection as a snippet in their Snippet Bank. The snippet retains a link back to its source location.

**Why this priority**: Snippet curation is the central human-in-the-loop mechanic. Without it, the bounded generation step cannot function. This story directly enables the core differentiator of the feature.

**Independent Test**: A user opens a document in Document View, selects text, saves it as a snippet. The Snippet Bank tab shows the saved snippet with its source attribution. This is independently valuable as a manual note-taking / evidence-gathering tool.

**Acceptance Scenarios**:

1. **Given** a document is open in Document View, **When** the user highlights text, **Then** a "Save to Scratchpad" prompt appears near the selection.
2. **Given** the user confirms saving a selection, **When** the snippet is saved, **Then** it appears as a card in the Snippet Bank with the source document name and the selected text.
3. **Given** a snippet is saved, **When** the user clicks its source reference, **Then** the Document View navigates back to the originating passage in the source document.
4. **Given** a snippet exists in the Snippet Bank, **When** the user adds an optional note or tag, **Then** the note is saved and displayed on the snippet card.
5. **Given** a snippet exists in the Snippet Bank, **When** the user deletes it, **Then** it is removed from the bank and is no longer available for bundling.

---

### User Story 3 - Search the Source Corpus Semantically (Priority: P2)

The user wants to find relevant passages across all their ingested sources without re-reading every document. They type a conceptual query into the search bar at the top of the Snippet Bank. The system returns ranked result cards from across the corpus. The user can check the ones they want, instantly adding them to their active Snippet Bank.

**Why this priority**: This dramatically accelerates evidence gathering for large or numerous sources. It is valuable after the core snippet workflow exists but is not a prerequisite for generation.

**Independent Test**: With at least two ingested sources, the user enters a search query and receives results from across both documents. Checking a result card adds it to the Snippet Bank. Generation does not need to be present.

**Acceptance Scenarios**:

1. **Given** the user enters a query in the search bar, **When** results return, **Then** each result shows the matching passage and which source document it came from.
2. **Given** search results are displayed, **When** the user checks a result card, **Then** that passage is immediately added to the Snippet Bank as a snippet.
3. **Given** a query returns no strong matches, **When** results are shown, **Then** the user is informed that no strong matches were found rather than being shown irrelevant content.
4. **Given** a snippet from search has been added to the Snippet Bank, **When** the user views the bank, **Then** the snippet is indistinguishable in format from manually saved snippets.

---

### User Story 4 - Bundle Snippets and Generate Bounded Text (Priority: P2)

The user is writing in the main editor and wants to draft a section. They select a heading or empty block, which triggers a bundling panel. From their Snippet Bank, they may then optionally choose which snippets should serve as the evidence base. They then type an explicit analytical intent. The system generates a draft paragraph or section and inserts it into the document in a highlighted "Suggested" state awaiting their approval.

**Why this priority**: This is the culminating step of the workflow, but it requires Phases 1 and 2 to be complete. It is the AI-assisted generation step, constrained entirely by the user's curated evidence and stated intent.

**Independent Test**: With snippets in the Snippet Bank and an empty block in the editor, the user selects snippets, writes an intent, and triggers generation. A suggested text block appears in the editor. The user accepts or rejects it. All prior stories must be in place.

**Acceptance Scenarios**:

1. **Given** the user places their cursor on a heading or empty block, **When** they invoke the bundling UI, **Then** a panel appears listing all current Snippet Bank cards with checkboxes.
2. **Given** the bundling panel is open, **When** the user selects at least one snippet, **Then** an intent input field becomes active and required.
3. **Given** snippets are selected and intent is entered, **When** the user confirms generation, **Then** a suggested text block appears inline in the editor marked as a suggestion.
4. **Given** a suggested block is present, **When** the user accepts it, **Then** the text is committed to the document in normal (non-suggested) state.
5. **Given** a suggested block is present, **When** the user rejects it, **Then** the suggestion is discarded and the editor returns to the pre-generation state.
6. **Given** the user has not selected any snippets, **When** they attempt to trigger generation, **Then** the system prevents generation and prompts them to select evidence first.
7. **Given** the user has not entered an intent, **When** they attempt to trigger generation, **Then** the system prevents generation and prompts them to state their intent.

---

### Edge Cases

- What happens when a source document is very large (hundreds of pages)? Users should still be able to search and browse without excessive wait times.
- What happens when the user's Snippet Bank is empty and they try to invoke generation? The bundling UI must block generation and clearly explain why.
- What happens when a source document is deleted after snippets were saved from it? Existing snippets retain their saved text but display a "source unavailable" notice rather than breaking.
- What happens when a search query returns hundreds of results? Results should be limited to the most semantically relevant matches to avoid overwhelming the user.
- What happens if the generated suggestion is very long? The editor must accommodate variable-length suggestions without breaking layout.

## Requirements *(mandatory)*

### Functional Requirements

#### Source Ingestion

- **FR-001**: System MUST accept PDF files and URLs as source inputs for a workspace.
- **FR-002**: System MUST extract and preserve the textual content and structural hierarchy (headings, paragraphs) from all ingested sources.
- **FR-003**: System MUST index each ingested source's content into the workspace corpus to support semantic search.
- **FR-004**: System MUST display the parsed content of any source document in a browsable Document View within the side panel.
- **FR-005**: System MUST provide clear feedback when a source fails to process, without blocking the rest of the workspace.

#### Snippet Curation

- **FR-006**: System MUST allow users to select any span of text within the Document View and save it as a snippet.
- **FR-007**: Each snippet MUST record the source document it came from and the location within that document.
- **FR-008**: System MUST allow users to add an optional free-text note or tag to any snippet.
- **FR-009**: System MUST allow users to delete individual snippets from the Snippet Bank.
- **FR-010**: System MUST navigate the Document View to the originating passage when a user clicks a snippet's source reference.
- **FR-011**: Snippets MUST persist across user sessions for the duration of the workspace.

#### Semantic Search

- **FR-012**: System MUST provide a search input within the Snippet Bank panel that queries the full workspace corpus.
- **FR-013**: Search MUST return results ranked by conceptual relevance, not keyword frequency alone.
- **FR-014**: Each search result MUST display the matching passage text and its source document.
- **FR-015**: System MUST allow users to add any search result directly to the Snippet Bank via a single interaction.

#### Bounded Generation

- **FR-016**: Generation MAY proceed with zero snippets selected; snippet selection is optional.
- **FR-017**: When the user invokes AI generation, an intent statement is required. The user may always dismiss the bundling UI and type directly instead.
- **FR-018**: System MUST provide a snippet-selection UI triggered from a heading or empty paragraph block in the main editor.
- **FR-019**: System MUST send the selected snippets (if any), the user's intent string, and the current document content as context for text generation. For chapter-structured documents, the full current chapter plus brief summaries of other chapters MUST be included so the AI does not repeat content or lose focus.
- **FR-020**: All generated text MUST be inserted into the editor in a visually distinct "Suggested" state before the user takes any action on it.
- **FR-021**: System MUST allow users to accept a suggestion, committing it to the document as normal editable text.
- **FR-022**: System MUST allow users to reject a suggestion, removing it from the editor entirely.

### Key Entities

- **Source**: A document (PDF or URL) added to a workspace. Has ingestible content, processing status, and a human-readable title.
- **Corpus Chunk**: A discrete, searchable passage extracted from a source during ingestion. Belongs to one source; has text content and a positional reference within that source.
- **Snippet**: A user-curated evidence card. Contains the saved text, a reference to its source (and position within it), an optional user note/tag, and belongs to a specific workspace.
- **Snippet Bank**: The collection of all active snippets curated by the user for a workspace. Acts as the evidence pool available for generation.
- **Generation Bundle**: The ephemeral set of snippets and intent string selected by the user for a single generation request. Not persisted after use.
- **Suggestion**: A block of AI-generated text in a pending state, awaiting user acceptance or rejection. Belongs to a specific position in the editor document.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can ingest a new source (PDF or URL) and begin browsing its content within 30 seconds of submission for documents under 50 pages.
- **SC-002**: Users can save a snippet from a highlighted passage in two interactions or fewer (highlight → save prompt → confirm).
- **SC-003**: Semantic search returns relevant results in under 3 seconds for a corpus of up to 20 ingested sources.
- **SC-004**: 100% of AI generation interactions require a non-empty intent statement — zero-intent AI generation is impossible by design. Snippet selection is optional. Users may always dismiss the bundling UI and write directly in the editor without invoking AI.
- **SC-005**: Generated suggestions are inserted into the editor within 15 seconds of the user confirming a bundle.
- **SC-006**: Users can complete the full Search → Select → Synthesize loop (find evidence, save snippets, generate a paragraph) within 5 minutes of first use, without instruction.
- **SC-007**: Snippet Bank state persists correctly across page reloads and re-logins with no data loss.

## Assumptions

- All users are authenticated workspace members; snippet banks are per-workspace and shared if the workspace is shared (multi-user sharing behaviour is out of scope for this feature).
- Source ingestion handles native text extraction for PDFs; scanned image-only PDFs that require OCR are out of scope and should surface a clear "unsupported format" error.
- The side panel (scratchpad) is always accessible alongside the main editor; no full-screen / collapsed panel mode is required in this iteration.
- Snippet ordering in the Snippet Bank defaults to chronological (most recently saved first); manual reordering is out of scope.
- There is no enforced limit on the number of snippets per workspace in this iteration.
- The intent field has a practical character limit (500 characters) to prevent abuse; the exact limit can be tuned during implementation.
- "Suggested" state for generated text is visually distinct (e.g., highlighted or differentiated styling) but does not require a separate tracked-changes system — accept/reject is the complete workflow.
- Re-generation (generating a new suggestion for the same location after rejecting one) is permitted and follows the same bundling flow.

## Out of Scope

- OCR or layout-aware parsing for scanned or image-heavy PDFs.
- Generating entire document outlines or multi-section drafts in a single action.
- Any generation trigger that does not require user-selected snippets and an explicit intent string.
- Inline editing of a suggestion before accepting it (editing is available after acceptance).
- Sharing or exporting the Snippet Bank independently of the workspace.
- Version history of snippets or suggestions.
