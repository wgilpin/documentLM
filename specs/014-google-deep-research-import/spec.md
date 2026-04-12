# Feature Specification: Import Google Deep Research

**Feature Branch**: `014-google-deep-research-import`  
**Created**: 2026-04-12  
**Status**: Draft  
**Input**: User description: "we should be able to read the contents and references from a google deep research..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload and Ingest Deep Research Document (Priority: P1)

A user has completed a Google Deep Research session and wants to bring both the research report and all its cited sources into their document workspace. They follow the export instructions, select the downloaded Markdown file, and the system automatically adds the report and all referenced URLs as sources and ingests them.

**Why this priority**: This is the entire value of the feature — without it, there is nothing else to build. All other stories depend on this core flow working end-to-end.

**Independent Test**: Can be fully tested by clicking "Import Google Deep Research", following the export instructions, selecting a Markdown file containing references, and verifying that the document and each referenced URL appear as ingested sources in the workspace.

**Acceptance Scenarios**:

1. **Given** a user is on the sources page of a document, **When** they click "Import Google Deep Research", **Then** a modal appears displaying step-by-step export instructions (export to Google Docs → open the Doc → File > Download > Markdown).

2. **Given** the instructions modal is open, **When** the user selects a Markdown file from their filesystem (defaulting to ~/Downloads), **Then** the system parses the file, adds the document content as a source, extracts all hyperlinks/references, and queues them all for ingestion.

3. **Given** the import has been triggered, **When** ingestion completes, **Then** the user sees the research document and each referenced source listed and marked as ingested in the sources panel.

---

### User Story 2 - Partial Reference Ingestion (Priority: P2)

Some references in the research document may be inaccessible (paywalled, dead links, or non-web sources like academic citations). The system should continue ingesting what it can and clearly report which sources could not be retrieved.

**Why this priority**: Real-world research documents frequently contain references that cannot be fetched. Without graceful handling, the entire import would feel broken even if 90% succeeded.

**Independent Test**: Can be fully tested by importing a Markdown file that contains a mix of valid URLs, dead links, and non-URL references, and verifying that accessible sources are ingested while failures are clearly reported without blocking the overall import.

**Acceptance Scenarios**:

1. **Given** a research document contains a reference with an inaccessible URL, **When** ingestion runs, **Then** that source is marked as failed with a human-readable reason, while all other sources complete normally.

2. **Given** a research document contains plain-text citations (no URL), **When** the system parses references, **Then** those non-URL references are skipped and not shown as failed sources (only URL-based references are attempted).

---

### Edge Cases

- If the uploaded file is not a valid Markdown file or contains no parseable content, the modal displays an inline error message and remains open so the user can select a different file.
- What happens when the research document contains duplicate URLs across references?
- What happens when the file is very large (100+ references)?
- What happens if the user cancels the file picker without selecting a file?
- What happens when a reference URL redirects multiple times or returns non-HTML content (PDF, image)?

## Clarifications

### Session 2026-04-12

- Q: What happens when the selected file is invalid or not a recognisable Deep Research Markdown export? → A: Show an inline error in the modal; keep the modal open so the user can re-select a different file.
- Q: What happens when an extracted URL already exists as a source in the current workspace? → A: Skip silently — the existing source is reused and no error or warning is shown.
- Q: Is "Import Session" a persistent data entity or a UX-only grouping? → A: UX-only — the grouping exists only during the import flow; sources become independent after import completes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The sources panel MUST display an "Import Google Deep Research" button or action.
- **FR-002**: Clicking the import action MUST show a modal with step-by-step instructions for exporting a Google Deep Research report to Markdown format (export to Google Docs → open Doc → File > Download > Markdown).
- **FR-003**: The modal MUST provide a way for the user to select a local Markdown file, defaulting the file picker to the ~/Downloads directory where possible.
- **FR-003a**: If the selected file cannot be parsed as Markdown or yields no content, the modal MUST display an inline error and remain open so the user can select a different file.
- **FR-004**: The system MUST parse the selected Markdown file and add the full document content as one source.
- **FR-005**: The system MUST extract all hyperlinks (URLs) embedded in the Markdown file and treat each distinct URL as a separate source to be ingested.
- **FR-006**: The system MUST deduplicate extracted URLs — the same URL appearing multiple times in the file MUST result in only one source being created.
- **FR-006a**: If an extracted URL already exists as a source in the current workspace, it MUST be silently skipped — no duplicate is created and no warning is shown.
- **FR-007**: The document content source and all URL-based reference sources MUST be queued and ingested using the existing ingestion pipeline.
- **FR-008**: The user MUST be shown ingestion progress for the document and each reference source.
- **FR-009**: Sources that fail to ingest (unreachable URL, unsupported content type) MUST be marked with a failure status and a reason, without blocking ingestion of other sources.
- **FR-010**: Non-URL citations (plain text references with no hyperlink) MUST be silently skipped — they MUST NOT appear as failed sources.

### Key Entities

- **Research Document Source**: The full text content of the imported Markdown file, treated as a single source in the workspace.
- **Reference Source**: A URL extracted from the Markdown file, representing one cited external resource to fetch and ingest.
- **Import Session**: A transient UX grouping used only during the import flow to display progress for the document and all its reference sources together. Once ingestion completes, sources are independent and require no persistent batch record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full import flow (click button → read instructions → select file → confirm) in under 2 minutes.
- **SC-002**: All valid, accessible URLs extracted from the research document are successfully ingested as sources with no manual intervention required.
- **SC-003**: At least 90% of test Markdown exports from actual Google Deep Research sessions are parsed correctly with no errors.
- **SC-004**: Failed reference sources are identified and reported to the user within the same ingestion status view, with no ambiguity about which sources failed and why.
- **SC-005**: Importing a research document with 20+ references completes without UI degradation or timeout errors visible to the user.

## Assumptions

- The Google Deep Research Markdown export format consistently embeds references as standard Markdown hyperlinks (`[text](url)`). If Google changes this format, the parser may require updates.
- The existing source ingestion pipeline (used for URLs and document text) is already capable of handling the volume and variety of content this feature will feed it.
- Users have access to Google Deep Research and understand how to use it; this feature only handles the import step, not the research creation.
- The file system default open path (~/Downloads) is a UX hint only — the actual file picker behavior depends on the user's browser and OS.
- Plain-text academic citations (e.g., "Smith, J. (2024). Title. Journal.") without URLs are out of scope for ingestion.
