# Feature Specification: UX Improvements

**Feature Branch**: `003-ux-improvements`
**Created**: 2026-03-13
**Status**: Draft
**Input**: UX review (docs/002-UX-review.md) — implement all 6 recommended actions

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Global Command Modal (Priority: P1)

A writer wants to issue a global AI command (e.g., "summarize this document" or "suggest a title") without occupying a permanent sidebar form. They trigger an on-demand modal via a keyboard shortcut or a floating action button, type their command, and submit it. The modal disappears when done.

**Why this priority**: The persistent "ASK AI" sidebar form consumes significant vertical space and distracts from the document. Replacing it with an on-demand modal is the highest-impact friction reduction.

**Independent Test**: Can be fully tested by opening the modal, submitting a command, and confirming the modal closes and the response appears — without touching any other UI element.

**Acceptance Scenarios**:

1. **Given** a document is open, **When** the user presses the keyboard shortcut or activates the floating button, **Then** a modal dialog appears with a text input for an AI command.
2. **Given** the modal is open, **When** the user submits a command, **Then** the modal closes and the AI response is surfaced in the document area.
3. **Given** the modal is open, **When** the user presses Escape or clicks outside the modal, **Then** the modal closes without submitting anything.
4. **Given** no document is open, **When** the user triggers the modal, **Then** the modal indicates that a document must be open first.

---

### User Story 2 - Contextual AI Triggers (Priority: P2)

A writer highlights a passage in the document and wants to ask the AI a question specifically about that text without navigating away. A floating context menu appears near the selection, offering an "Add AI Instruction" option. The writer clicks it, types an annotation or instruction, and it is captured as an inline margin comment linked to that passage.

**Why this priority**: Inline annotation tied to selected text is a PRD requirement and eliminates the context-switching caused by the current sidebar workflow.

**Independent Test**: Can be fully tested by selecting text, triggering the context menu, submitting an instruction, and confirming the margin comment appears alongside the correct passage.

**Acceptance Scenarios**:

1. **Given** text is selected in the editor, **When** the selection is made, **Then** a small floating menu appears near the selection.
2. **Given** the floating menu is visible, **When** the user clicks "Add AI Instruction", **Then** an input appears for the user to type their annotation.
3. **Given** an instruction is submitted, **When** the system processes it, **Then** the instruction is saved as an inline margin comment associated with the selected passage.
4. **Given** text is deselected, **When** no selection exists, **Then** the floating menu is hidden.

---

### User Story 3 - Inline Track Changes for AI Suggestions (Priority: P3)

A writer receives an AI-generated suggestion and wants to review it without leaving the document flow. Instead of a separate sidebar panel, AI suggestions appear directly within the document text, styled distinctly, with inline accept and reject controls.

**Why this priority**: The empty "AI SUGGESTIONS" sidebar box fails to deliver the MS Word-style track-changes experience required by the PRD. Inline rendering keeps the writer in context.

**Independent Test**: Can be fully tested by requesting a document edit, confirming the suggestion appears inline with accept/reject controls, and verifying both accept (incorporates text) and reject (removes suggestion) work correctly.

**Acceptance Scenarios**:

1. **Given** the AI generates a text suggestion, **When** the suggestion is ready, **Then** it is injected inline into the document with distinct visual styling (e.g., colored highlight or strikethrough).
2. **Given** an inline suggestion is visible, **When** the user clicks "Accept", **Then** the suggestion replaces the original text and the styling is removed.
3. **Given** an inline suggestion is visible, **When** the user clicks "Reject", **Then** the suggestion is removed and the original text is unchanged.
4. **Given** multiple suggestions are active, **When** the user accepts or rejects one, **Then** only that suggestion is resolved; others remain.

---

### User Story 4 - Collapsed Source Entry (Priority: P4)

A writer wants to add a new source (note, URL, or PDF) but finds the permanent input form visually overwhelming. A single "Add Source" button, when clicked, expands into the relevant input options. After adding the source, the form collapses back.

**Why this priority**: Reducing cognitive load from the permanently visible form improves the experience for users who are focused on writing, not sourcing.

**Independent Test**: Can be fully tested by clicking "Add Source", selecting a type, entering data, submitting, and confirming the source appears in the list while the form collapses.

**Acceptance Scenarios**:

1. **Given** the sources panel is visible, **When** the user views it, **Then** only a single "Add Source" button is shown — not the full Note/URL/PDF input forms.
2. **Given** the user clicks "Add Source", **When** the menu expands, **Then** the user can select the source type (Note, URL, PDF) and enter the relevant data.
3. **Given** a source is successfully added, **When** submission completes, **Then** the form collapses back to the single button state.
4. **Given** the user opens the menu but decides not to add a source, **When** they dismiss the menu, **Then** the form collapses without adding anything.

---

### User Story 5 - De-emphasized Delete for Sources (Priority: P5)

A writer scanning the source list should not be visually distracted by prominent red delete buttons. Delete controls are hidden by default and only appear as subtle icons when the pointer hovers over a specific source item.

**Why this priority**: The bright red persistent delete buttons are visually dominant over primary generative actions and create anxiety about accidental deletion.

**Independent Test**: Can be fully tested by viewing the source list (confirming no red buttons), hovering over a source (confirming a subtle icon appears), clicking delete (confirming removal with confirmation), and moving away (confirming the icon disappears).

**Acceptance Scenarios**:

1. **Given** sources are listed, **When** the user is not hovering over any source, **Then** no delete controls are visible.
2. **Given** a source is in the list, **When** the user hovers over it, **Then** a subtle (non-red) delete icon appears for that source only.
3. **Given** the delete icon is visible, **When** the user clicks it, **Then** the source is removed from the list.
4. **Given** the user moves the pointer away from a source, **When** hover ends, **Then** the delete icon disappears.

---

### User Story 6 - Global Meta-Chat Panel (Priority: P6)

A writer wants a dedicated space for open-ended conversational brainstorming with the AI — separate from inline document edits. A persistent, collapsible panel on the interface serves this purpose. The writer can open it, have a back-and-forth conversation about ideas, and collapse it to return focus to the document.

**Why this priority**: The PRD requires a meta-editing chat that is conceptually distinct from inline document commands. It is lower priority because it adds a new surface rather than fixing an existing friction point.

**Independent Test**: Can be fully tested by opening the panel, sending a message, receiving a reply, and collapsing the panel — independent of the main document editor state.

**Acceptance Scenarios**:

1. **Given** the interface is loaded, **When** the user looks at the layout, **Then** a collapsed meta-chat panel control is visible.
2. **Given** the panel is collapsed, **When** the user clicks to expand it, **Then** the panel opens and displays a conversational chat interface.
3. **Given** the panel is open, **When** the user sends a message, **Then** the AI responds within the panel in a conversational turn-by-turn format.
4. **Given** the panel is open, **When** the user clicks to collapse it, **Then** the panel hides and the document editor occupies the full available space.
5. **Given** a conversation has been held, **When** the user reopens the panel, **Then** prior conversation history is preserved within the session.

---

### Edge Cases

- What happens when the user tries to use the global command modal while an inline suggestion is pending acceptance?
- How does the system handle a very large number of inline suggestions (visual clutter)?
- What happens when the user highlights zero characters and triggers the contextual menu?
- How does the contextual menu behave on touch/mobile devices without hover?
- What happens when a PDF source upload fails mid-expand of the Add Source menu?
- How does the meta-chat panel behave if the session expires while it has an active conversation?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The UI MUST NOT display a permanent "ASK AI" sidebar form; it must be replaced by an on-demand trigger mechanism.
- **FR-002**: Users MUST be able to open a global AI command input via a keyboard shortcut and via a visible floating button.
- **FR-003**: The global command input MUST close automatically after a command is successfully submitted.
- **FR-004**: When the user selects text in the document editor, a floating context menu MUST appear near the selection.
- **FR-005**: The floating context menu MUST include an option to add an AI instruction linked to the selected text.
- **FR-006**: AI instructions submitted via the contextual menu MUST be stored as inline margin comments associated with the specific text passage.
- **FR-007**: The UI MUST NOT display a standalone "AI SUGGESTIONS" sidebar box; AI suggestions MUST be rendered inline within the document.
- **FR-008**: Inline AI suggestions MUST be visually distinct from regular document text.
- **FR-009**: Each inline suggestion MUST have inline accept and reject controls immediately adjacent to it.
- **FR-010**: Accepting a suggestion MUST incorporate the suggested text and remove the suggestion styling.
- **FR-011**: Rejecting a suggestion MUST remove the suggestion without altering the original text.
- **FR-012**: The source input area MUST display only a single "Add Source" button by default, with the full input form hidden.
- **FR-013**: Clicking "Add Source" MUST expand a menu offering the available input types (Note, URL, PDF).
- **FR-014**: After successfully adding a source, the expanded form MUST collapse back to the single-button state.
- **FR-015**: Delete controls on source list items MUST NOT be visible by default.
- **FR-016**: Delete controls MUST appear as a non-red, subtle icon only when the pointer hovers over the source list item.
- **FR-017**: The interface MUST include a collapsible meta-chat panel dedicated to conversational AI interaction.
- **FR-018**: The meta-chat panel MUST maintain conversation history for the duration of the session.
- **FR-019**: The meta-chat panel MUST be visually and functionally distinct from the inline document AI interactions.

### Key Entities

- **Margin Comment**: An AI instruction submitted via the contextual menu, associated with a specific text range in the document.
- **Inline Suggestion**: An AI-generated text change rendered directly in the document with pending accept/reject state.
- **Meta-Chat Message**: A conversational turn (user or AI) within the global meta-chat panel, scoped to the current session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can issue a global AI command in under 10 seconds from any state of the document interface.
- **SC-002**: Users can annotate selected text with an AI instruction without navigating away from the document — zero sidebar interactions required.
- **SC-003**: Users can review, accept, or reject all AI suggestions without the document editor scrolling out of view of the suggestion.
- **SC-004**: The source panel vertical footprint is reduced such that at least 3 additional sources are visible on screen at the default viewport compared to the current layout.
- **SC-005**: Zero red persistent delete buttons are visible in the source list when the user is not hovering.
- **SC-006**: Users can open, use, and collapse the meta-chat panel without losing their document cursor position.
- **SC-007**: All primary generative actions (global command, contextual annotation, suggestion accept/reject) are reachable within 2 interactions from the document editor.

## Assumptions

- The keyboard shortcut for the global command modal will follow common conventions (e.g., Cmd/Ctrl+K or Cmd/Ctrl+Space); the exact key is an implementation detail.
- "Session" for meta-chat history means the browser tab session; cross-session persistence is out of scope for this feature.
- Inline suggestions are scoped to document text modifications; structural changes (e.g., adding sections) are out of scope for this iteration.
- Touch/mobile optimization for the contextual floating menu is out of scope; desktop-first.
- The existing source types (Note, URL, PDF) remain unchanged; the collapsed entry only changes the presentation, not the data model.
