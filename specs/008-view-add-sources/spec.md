# Feature Specification: Document Sources Pane – View and Add Sources

**Feature Branch**: `008-view-add-sources`
**Created**: 2026-03-17
**Status**: Draft
**Input**: User description: "in the document sources pane I need two extra features: 1) view a source - open it in a new tab 2) add a new source manually - paste url - paste text - upload pdf"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View an Existing Source (Priority: P1)

A user working on a document wants to review the full content of one of the sources listed in the sources pane. They click a "View" action on that source and the source content opens in a new browser tab, allowing them to read it without losing their place in the document editor.

**Why this priority**: Existing sources are already in the system — exposing them for review is the simpler of the two features and immediately valuable for verifying source accuracy.

**Independent Test**: Can be fully tested by clicking "View" on any existing source and confirming it opens in a new tab with the correct content.

**Acceptance Scenarios**:

1. **Given** a document with at least one source in the sources pane, **When** the user clicks "View" on a source, **Then** that source's content opens in a new browser tab.
2. **Given** a source that is a URL, **When** the user clicks "View", **Then** the external URL opens in a new tab.
3. **Given** a source that is stored text or an uploaded PDF, **When** the user clicks "View", **Then** the stored content is displayed in a new tab (rendered as plain text or PDF).

---

### User Story 2 - Add a Source by URL (Priority: P2)

A user finds a relevant web page and wants to add it as a source for their document. They click "Add Source", choose URL input, paste the URL, and submit. The source is fetched and added to the document's sources pane.

**Why this priority**: URL is the most common way to reference external content; delivering this first provides the highest value for manual source addition.

**Independent Test**: Can be fully tested by adding a well-formed URL as a source and confirming it appears in the pane.

**Acceptance Scenarios**:

1. **Given** the user is on a document, **When** they open "Add Source", choose URL, paste a valid URL, and submit, **Then** the source appears in the sources pane immediately.
2. **Given** the user submits a malformed or empty URL, **Then** an error message is shown and no source is added.
3. **Given** a URL that is unreachable, **When** the user submits it, **Then** the system displays a clear error indicating the URL could not be accessed.

---

### User Story 3 - Add a Source by Pasting Text (Priority: P3)

A user has a passage of text (copied from any source) they want to add directly as a source. They open "Add Source", choose text input, paste the text, and submit. The text is stored as a source and appears in the pane.

**Why this priority**: Text paste is a flexible fallback for content not available as a URL or PDF, and requires no file handling.

**Independent Test**: Can be fully tested by pasting text and confirming it is saved as a source in the pane.

**Acceptance Scenarios**:

1. **Given** the user chooses text input, **When** they paste non-empty text and submit, **Then** a new source appears in the pane containing that text.
2. **Given** the user submits an empty text field, **Then** an error is shown and no source is added.

---

### User Story 4 - Add a Source by Uploading a PDF (Priority: P4)

A user has a PDF document (research paper, report, etc.) they want to add as a source. They open "Add Source", choose PDF upload, select a PDF file, and submit. The PDF is stored and appears as a source in the pane.

**Why this priority**: PDF upload handles physical documents and gated content not reachable by URL; slightly more complex than text paste.

**Independent Test**: Can be fully tested by uploading a PDF file and confirming it appears as a source in the pane.

**Acceptance Scenarios**:

1. **Given** the user chooses PDF upload, **When** they select a valid PDF file and submit, **Then** the file appears as a source in the pane.
2. **Given** the user selects a non-PDF file, **Then** an error is shown and the file is rejected.
3. **Given** the user uploads a PDF that exceeds the maximum allowed size, **Then** a clear error message is shown and the upload is rejected.

---

### Edge Cases

- What happens when a URL is syntactically valid but the target page is unreachable or returns an error?
- How does the system handle a PDF that contains only scanned images with no extractable text?
- What if the user tries to add a URL that already exists as a source for the same document?
- What if the user pastes an extremely large block of text?
- What if the PDF file is corrupt or password-protected?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each source listed in the sources pane MUST display a "View" action that the user can activate.
- **FR-002**: Activating "View" on any source MUST open that source's content in a new browser tab without navigating away from the current document.
- **FR-003**: The sources pane MUST provide an "Add Source" control that initiates the source-addition workflow.
- **FR-004**: The add-source workflow MUST present three input methods: URL, plain text, and PDF upload.
- **FR-005**: Users MUST be able to submit a URL as a new source; the system MUST validate the URL is well-formed before accepting it.
- **FR-006**: Users MUST be able to paste plain text as a new source; empty submissions MUST be rejected with an error message.
- **FR-007**: Users MUST be able to upload a PDF file as a new source; only files in PDF format MUST be accepted.
- **FR-008**: Successfully added sources MUST appear in the sources pane immediately without requiring a full page reload.
- **FR-009**: The system MUST display a clear, user-friendly error message when any submission fails validation (malformed URL, empty text, invalid file type, file too large).
- **FR-010**: The system MUST enforce a maximum file size for PDF uploads and communicate the limit to users.

### Key Entities

- **Source**: A reference item associated with a document. Has a type (URL, text, PDF), content or reference data, and a display name shown in the sources pane.
- **Document**: The parent entity that owns one or more sources.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can open any existing source for viewing in 1 click after locating it in the sources pane.
- **SC-002**: Users can successfully add a new source via any of the three input methods (URL, text, PDF) in under 60 seconds from clicking "Add Source".
- **SC-003**: 100% of successfully added sources appear in the sources pane without a full page reload.
- **SC-004**: Invalid inputs (malformed URL, empty text, non-PDF file) are rejected with an error message before any data is stored — 0% false acceptances.
- **SC-005**: Users who attempt to add a source for the first time can complete the action without consulting documentation, as measured by task completion on first attempt.

## Assumptions

- All three "Add Source" input methods (URL, text, PDF) are available within the same workflow, selectable via tabs or a similar selector — not as separate entry points.
- "View" for URL sources opens the original external URL directly; for text/PDF sources, the stored content is rendered in a new tab.
- For URL sources, the page title or URL itself is used as the display name; for text sources, the user provides a brief title at submission time; for PDF sources, the filename is used as the display name.
- The maximum PDF upload size is 10 MB unless otherwise configured.
- Duplicate URL detection is a nice-to-have; the system may warn but will not hard-block duplicate URLs in this iteration.
- This feature applies to all documents and all logged-in users — no special permissions are required beyond document access.
