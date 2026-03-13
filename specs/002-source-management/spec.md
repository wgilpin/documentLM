# Feature Specification: Source Management

**Feature Branch**: `002-source-management`
**Created**: 2026-03-13
**Status**: Implemented
**Input**: User description: "the user should be able to see and manage the list of sources in the app"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Sources for a Document (Priority: P1)

A writer opens a document and wants to see all the reference material attached to it. They need a clear panel or section showing all sources — their titles, types (web page, PDF, note), and when they were added — so they know what content is informing the document.

**Why this priority**: Visibility is the foundation of management. Without being able to see sources, none of the other interactions are possible. This is also the most basic form of value: knowing what you've already added.

**Independent Test**: Open any document that has at least one source attached. The sources panel is visible and lists each source with its title and type. This alone delivers value by giving writers situational awareness.

**Acceptance Scenarios**:

1. **Given** a document with multiple sources, **When** the user opens that document, **Then** a sources panel is visible showing all sources with their title and type.
2. **Given** a document with no sources, **When** the user opens that document, **Then** the sources panel shows an empty state message explaining that no sources have been added yet.
3. **Given** the sources panel is visible, **When** the user looks at a source entry, **Then** the source title, type (URL / PDF / Note), and date added are clearly shown.

---

### User Story 2 - Add a New Source (Priority: P2)

A writer is working on a document and wants to add a new reference: a web page they've found, a PDF they've uploaded, or a quick note they've typed. They need a simple flow to add each type and see the new source appear in the list immediately.

**Why this priority**: Adding sources is the primary write interaction. Without it, the list can only be pre-populated; writers have no way to bring new material into their document.

**Independent Test**: From the document view, add a source of each type (URL, PDF, note) and confirm each appears in the sources list without a page reload.

**Acceptance Scenarios**:

1. **Given** the sources panel, **When** the user initiates adding a URL source, **Then** they are prompted for a title and a web address, and on submission the new source appears in the list.
2. **Given** the sources panel, **When** the user initiates adding a PDF source, **Then** they are prompted for a title and a file to upload, and on submission the new source appears in the list with content extracted from the PDF.
3. **Given** the sources panel, **When** the user initiates adding a note, **Then** they are prompted for a title and free-form text, and on submission the new note appears in the list.
4. **Given** the user submits an invalid URL (e.g., missing protocol), **When** the form is submitted, **Then** an inline error message is shown and the source is not added.
5. **Given** the user submits an empty title, **When** the form is submitted, **Then** an inline error message is shown and the source is not added.

---

### User Story 3 - Remove a Source (Priority: P3)

A writer notices a source is no longer relevant or was added by mistake. They want to remove it from the document's source list so it no longer influences the document's context.

**Why this priority**: Deletion is lower priority than visibility and creation, but necessary for completeness. Writers need to correct mistakes or curate their source list over time.

**Independent Test**: With at least one source in the list, delete it and confirm it is removed from the list without a page reload.

**Acceptance Scenarios**:

1. **Given** a source in the list, **When** the user chooses to remove it and confirms, **Then** the source is removed from the list immediately.
2. **Given** a source in the list, **When** the user initiates removal but cancels, **Then** the source remains in the list unchanged.

---

### Edge Cases

- **PDF upload fails or file is not a valid PDF** — ✅ Resolved: an inline error message is shown; the source is not saved.
- **URL is syntactically invalid** — ✅ Resolved: HTML5 `type="url"` validation prevents submission client-side; the source is not added.
- **Document has a very large number of sources (e.g., 50+)** — ⚠️ Known limitation: the sources list grows unbounded and can push the add-source forms and other sidebar sections off-screen. A fixed-height scrollable list is not yet implemented.
- **Note content is extremely long** — Not yet validated; no upper limit is enforced on note text in this phase.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST display a sources panel within the document view listing all sources associated with that document.
- **FR-002**: Each source entry MUST show its title, type (URL, PDF, or Note), and the date it was added.
- **FR-003**: The sources panel MUST show an empty state message when no sources are associated with the document.
- **FR-004**: Users MUST be able to add a URL source by providing a title and a valid web address.
- **FR-005**: Users MUST be able to add a PDF source by providing a title and uploading a PDF file; text content is extracted automatically.
- **FR-006**: Users MUST be able to add a note source by providing a title and free-form text content.
- **FR-007**: The sources list MUST update to reflect a newly added source without a full page reload.
- **FR-008**: Users MUST be able to remove any source from the document's source list.
- **FR-009**: The system MUST display an inline validation error when a URL source is submitted with an invalid or missing web address.
- **FR-010**: The system MUST display an inline validation error when any source is submitted with an empty title.
- **FR-011**: The system MUST display an error message when an uploaded file is not a valid PDF.

### Key Entities

- **Source**: A piece of reference material attached to a document. Has a title, type (URL / PDF / Note), optional web address, extracted or typed text content, and a date added. Belongs to exactly one document.
- **Document**: The primary artifact being written. Has many sources.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view all sources for a document within 2 seconds of opening it.
- **SC-002**: Users can add a URL or note source in under 30 seconds from initiating the action to seeing it in the list.
- **SC-003**: Users can remove a source in under 10 seconds.
- **SC-004**: 100% of submitted sources with invalid input (bad URL, empty title, invalid PDF) surface a clear error message without losing the user's entered data.
- **SC-005**: The sources list reflects add and remove changes immediately without requiring a page reload.

## Assumptions

- Sources are scoped per document; there is no global source library in this phase.
- The app is used by a single user with no multi-user access control in scope for this feature.
- URL sources store the web address and a user-provided title; the app does not fetch or scrape the URL content automatically.
- PDF text extraction happens at upload time; the raw file is not stored for later retrieval by the user.
- There is no enforced upper limit on the number of sources per document in this phase.
- A confirmation prompt is shown before deletion to prevent accidental removal.
