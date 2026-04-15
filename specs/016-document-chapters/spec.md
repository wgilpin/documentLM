# Feature Specification: Chapter-Centric Documents

**Feature Branch**: `016-document-chapters`  
**Created**: 2026-04-14  
**Status**: Draft  
**Input**: User description: "Documents need to be chapter centric. A single chapter looks like a standard doc, but as we add chapters the display shows 1) The TOC 2) Chapter 1 3) Chapter N... 4) An Add Chapter button. Snippets can be attached to a chapter, for reference (not part of the chapter in the editor). Chapters can be empty, apart from a title and a Chapter Brief / Description, which can be hidden. This allows a user to create some chapters, add snippets, then start writing."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Create and Manage Chapters (Priority: P1)

A user opens a document and wants to organise it into chapters. They click "Add Chapter", give it a title, and optionally write a brief/description for the chapter. The chapter appears in the document view below any existing chapters, with an editor area ready for writing. They can add more chapters, reorder them, rename them, or delete them. A table of contents at the top of the document automatically reflects the current chapter structure.

**Why this priority**: This is the foundational capability — without chapter creation and management, no other chapter-related feature works. It transforms the document from a flat text block into a structured, navigable artefact.

**Independent Test**: Can be fully tested by creating a new document, adding 3+ chapters with titles, reordering them, and confirming the TOC updates. Delivers value immediately as a structured writing environment.

**Acceptance Scenarios**:

1. **Given** a document with no chapters, **When** the user clicks "Add Chapter", **Then** a new chapter is created with a title input field, an optional brief/description area, and an empty editor area.
2. **Given** a document with one chapter, **When** the user clicks "Add Chapter", **Then** a second chapter appears below the first, and a table of contents appears at the top showing both chapter titles.
3. **Given** a document with multiple chapters, **When** the user reorders chapters (e.g., moves Chapter 3 to position 1), **Then** the document view and TOC both update to reflect the new order.
4. **Given** a document with multiple chapters, **When** the user deletes a chapter, **Then** the chapter and its content are removed, the remaining chapters renumber in the TOC, and the user is asked to confirm before deletion.
5. **Given** a document with a single chapter, **When** the user views the document, **Then** the display looks like a standard document (no TOC, just the chapter content with its title as the document heading).
6. **Given** a document with multiple chapters, **When** the user clicks on a chapter that is not currently active, **Then** that chapter's rendered content is replaced with a live editor, and the previously active chapter's editor is replaced with its rendered content.

---

### User Story 2 — Chapter Brief / Description (Priority: P2)

A user wants to plan their document structure before writing. They create several chapters, each with a title and a brief that describes what the chapter will cover. The brief serves as a planning aid — it is visible to the author but can be toggled hidden when the author wants to focus on writing. The brief is not part of the chapter's main content in the editor.

**Why this priority**: The brief/description is a key planning tool that enables the "outline first, write later" workflow described in the feature request. It is essential for the intended use case but the system works without it.

**Independent Test**: Can be tested by creating a chapter, writing a brief, toggling its visibility, and confirming the brief does not appear in the editor's main content area.

**Acceptance Scenarios**:

1. **Given** a chapter with no brief, **When** the user clicks to add a brief, **Then** a text input area appears below the chapter title and above the editor area.
2. **Given** a chapter with a brief, **When** the user toggles "hide brief", **Then** the brief is collapsed/hidden from view but its content is preserved.
3. **Given** a chapter with a hidden brief, **When** the user toggles "show brief", **Then** the brief reappears with its original content intact.
4. **Given** a chapter with a brief, **When** the user edits the chapter content in the editor, **Then** the brief text is not included in or affected by the editor content.

---

### User Story 3 — Attach Snippets to Chapters (Priority: P2)

A user is researching and collecting snippets from sources. Instead of snippets floating at the document level, the user attaches each snippet to a specific chapter so that when they're writing that chapter, they can see the relevant reference material. Snippets appear as reference items alongside the chapter — visible for context but not inserted into the chapter's editor content.

**Why this priority**: Snippet-to-chapter association is the core research workflow improvement. It lets users gather material and assign it to chapters before writing, completing the "plan → research → write" pipeline.

**Independent Test**: Can be tested by creating two chapters, attaching different snippets to each, then navigating between chapters and confirming each shows only its own snippets.

**Acceptance Scenarios**:

1. **Given** a document with chapters, **When** the user creates a snippet from a source, **Then** the snippet is created unassigned (document-level) in the snippet bank.
2. **Given** an unassigned snippet in the snippet bank, **When** the user assigns it to one or more chapters, **Then** the snippet appears in each assigned chapter's snippet view.
3. **Given** a chapter with attached snippets, **When** the user is viewing/editing that chapter, **Then** the snippets panel shows the snippets associated with that chapter.
4. **Given** a snippet attached to Chapters 2 and 3, **When** the user is viewing Chapter 1, **Then** that snippet does not appear in the snippets panel (unless the user explicitly views all snippets).
5. **Given** a chapter with associated snippets, **When** the chapter is deleted, **Then** the snippet-to-chapter association is removed but the snippet itself is preserved (it may still be associated with other chapters, or becomes unassigned).

---

### User Story 4 — Empty Chapters as Outline Placeholders (Priority: P3)

A user wants to plan the structure of a long document. They create several chapters with just titles and briefs, leaving the content empty. The document displays this outline clearly, making it easy to see the planned structure. The user can later return to fill in content chapter by chapter.

**Why this priority**: This supports the planning-first workflow. It's a natural consequence of P1 (chapter creation) but deserves explicit testing to ensure the UI handles empty chapters gracefully.

**Independent Test**: Can be tested by creating a document with 5 empty chapters (title + brief only), confirming the TOC and document view render cleanly, then returning later to add content to one chapter.

**Acceptance Scenarios**:

1. **Given** a new document, **When** the user creates multiple chapters with only titles and briefs, **Then** the document displays a clean outline with the TOC and chapter headers — no "empty content" warnings or broken layouts.
2. **Given** a document with a mix of empty and content-filled chapters, **When** the user views the document, **Then** empty chapters show their title and brief (if visible) without visual clutter, and content-filled chapters display normally.
3. **Given** an empty chapter, **When** the user clicks on it or navigates to it, **Then** the editor is ready for writing with cursor focus in the content area.

---

### User Story 5 — Table of Contents Navigation (Priority: P3)

A user has a long document with many chapters. The table of contents at the top provides a clickable list of chapters. Clicking a chapter title in the TOC scrolls the document view to that chapter.

**Why this priority**: Navigation becomes important as documents grow, but the feature functions without it (users can scroll manually).

**Independent Test**: Can be tested by creating a document with 5+ chapters with content, then clicking TOC entries and confirming smooth scroll to the correct chapter.

**Acceptance Scenarios**:

1. **Given** a document with 3+ chapters, **When** the user views the document, **Then** a table of contents is displayed at the top listing all chapter titles in order.
2. **Given** a TOC is visible, **When** the user clicks a chapter title in the TOC, **Then** the view scrolls to that chapter's position in the document.
3. **Given** a document with a single chapter, **When** the user views the document, **Then** no TOC is displayed (the document looks like a standard single-page document).

---

### Edge Cases

- What happens when a user deletes all chapters from a document? The document returns to an empty state with an "Add Chapter" prompt.
- What happens when a chapter title is left blank? The system assigns a default title (e.g., "Untitled Chapter") and allows the user to rename it later.
- What happens when a user reorders chapters that have attached snippets? The snippet associations are unchanged regardless of chapter position changes.
- How does the existing AI chat interact with chapters? The AI chat remains document-level and can reference content across all chapters.
- What happens to existing documents (created before this feature) when the feature is deployed? Existing documents are migrated to a single-chapter structure, preserving all existing content and snippets.
- What is the maximum number of chapters allowed? No hard limit, but the UI should remain usable with up to 50 chapters.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to add chapters to a document, each with a required title.
- **FR-002**: System MUST display a table of contents when a document has two or more chapters, listing all chapter titles in order.
- **FR-003**: System MUST hide the table of contents when a document has only one chapter, so a single-chapter document looks like a standard document.
- **FR-004**: System MUST display chapters in sequence (TOC, then Chapter 1, Chapter 2, etc., then "Add Chapter" button) within the document view. All chapters are visible in a scrollable page, but only the active (clicked) chapter shows a live editor — other chapters display their rendered content.
- **FR-005**: System MUST allow each chapter to have an optional brief/description field that is separate from the chapter's main editor content.
- **FR-006**: System MUST allow users to toggle the visibility of a chapter's brief/description (show/hide).
- **FR-007**: System MUST allow chapters to exist with only a title (and optionally a brief), with no content — supporting the outline-first workflow.
- **FR-008**: System MUST allow users to reorder chapters within a document.
- **FR-009**: System MUST allow users to rename chapter titles inline.
- **FR-010**: System MUST allow users to delete chapters, with a confirmation prompt that warns if the chapter contains content or attached snippets.
- **FR-011**: System MUST allow snippets to be associated with one or more chapters (many-to-many). Snippets are created unassigned (document-level) and assigned to chapters as a separate action from the snippet bank.
- **FR-012**: System MUST display chapter-specific snippets in the snippets panel when the user is viewing or editing a chapter. A snippet associated with multiple chapters appears in each of those chapters' snippet views.
- **FR-013**: System MUST provide clickable TOC entries that navigate the user to the corresponding chapter in the document view.
- **FR-014**: System MUST persist chapter order, titles, briefs, and content independently so that editing one chapter does not affect others.
- **FR-015**: System MUST migrate existing single-content documents into a single-chapter structure to maintain backward compatibility.
- **FR-016**: System MUST assign a default title ("Untitled Chapter") when a chapter is created without a user-supplied title.

### Key Entities

- **Chapter**: A structural unit within a document. Has a title (required), a brief/description (optional, can be hidden), content (optional — may be empty), a display order within the document, and zero or more associated snippets.
- **Document**: Now serves as a container for one or more chapters. Retains its title, sources, AI chat sessions, comments, and suggestions. The document-level title serves as the overall document name.
- **Snippet**: An extracted text reference from a source. Can be unassigned (document-level) or associated with one or more chapters (many-to-many) to provide chapter-specific research context.

## Clarifications

### Session 2026-04-14

- Q: When a document has multiple chapters, how does the user interact with chapter content? → A: All chapters are visible in a scrollable page, but only the active/clicked chapter shows its live editor — other chapters display rendered content.
- Q: When does a snippet get assigned to a chapter? → A: Snippets are created unassigned (document-level), then assigned to chapters from the snippet bank as a separate action. A single snippet can be associated with multiple chapters (many-to-many).

## Assumptions

- The "Add Chapter" button appears at the bottom of the chapter list, below the last chapter.
- Chapter reordering uses up/down controls (drag-and-drop is a potential future enhancement).
- Sources remain at the document level (not chapter-level) — all chapters share the same source pool.
- AI chat, comments, and suggestions remain at the document level and are not scoped to individual chapters.
- The brief/description is plain text, not rich text — it is a planning note, not a content section.
- Only the active chapter displays a live editor; other chapters show rendered (read-only) content. Clicking a chapter activates its editor and deactivates the previous one.
- Snippet search within the snippets panel filters within the currently viewed chapter's snippets by default.
- The user can switch to a "show all snippets" mode to see all snippets (assigned and unassigned) across the document.
- Unassigned snippets are visible in the "all snippets" view and can be assigned to chapters from there.
- Auto-save behaviour applies per chapter (each chapter's content is saved independently).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create a 5-chapter document outline (titles and briefs only) in under 2 minutes.
- **SC-002**: Users can attach a snippet to a specific chapter in 2 clicks or fewer from the snippet creation flow.
- **SC-003**: Navigating between chapters via the TOC takes under 1 second (perceived response time).
- **SC-004**: A document with a single chapter is visually indistinguishable from the current standard document view.
- **SC-005**: 100% of existing documents are automatically migrated to the chapter structure with zero content loss.
- **SC-006**: Users can reorder chapters and see the updated TOC reflect the change immediately (within 1 second).
- **SC-007**: The chapter brief can be toggled between visible and hidden in a single click.
