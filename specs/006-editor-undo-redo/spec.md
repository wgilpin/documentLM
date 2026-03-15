# Feature Specification: Editor Undo/Redo

**Feature Branch**: `006-editor-undo-redo`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "Add undo capability. Add a toolbar above the editor with undo and redo buttons. Have an undo buffer of size configured in .env. Undo will undo a single keystroke if that was last, or it could be a whole AI change if that was last."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Undo Last Keystroke (Priority: P1)

A writer is editing a document in the workbench editor. They may have typed anywhere from a single character to thousands of keystrokes. They realise some or all of the typing was a mistake and click Undo repeatedly to step back through their history, one keystroke at a time.

**Why this priority**: Undo is the foundation of the feature and the most critical recovery action. Everything else depends on a working undo stack.

**Independent Test**: Can be fully tested by typing text in the editor and clicking Undo repeatedly, verifying each click reverses one prior keystroke. Delivers immediate value as a safety net for manual edits.

**Acceptance Scenarios**:

1. **Given** the user has typed any number of characters (from 1 to thousands), **When** they click Undo, **Then** the most recently typed character is removed and the cursor returns to its prior position.
2. **Given** the user continues clicking Undo, **Then** each successive click reverses one further keystroke in reverse chronological order, for as many steps as remain in the buffer.
3. **Given** the undo buffer has reached its configured maximum size (as defined in `.env`), **When** the user tries to undo beyond that limit, **Then** the Undo button is disabled and no further undo is possible.

---

### User Story 2 - Undo an AI-Generated Change (Priority: P1)

An AI agent has applied a large replacement or insertion to the document. The writer reviews the result and decides to revert it. They click Undo once and the entire AI change is reversed in a single step.

**Why this priority**: AI changes may affect large portions of text; requiring keystroke-by-keystroke undo would be impractical. Atomic AI undo is essential to the feature.

**Independent Test**: Can be fully tested by triggering an AI edit, then clicking Undo and confirming the document is back to its pre-AI state. No other undo stories need to be implemented first.

**Acceptance Scenarios**:

1. **Given** an AI agent has modified the document, **When** the user clicks Undo, **Then** the entire AI-applied change is reversed in a single undo step.
2. **Given** the user has made manual keystrokes after an AI change, **When** they click Undo multiple times, **Then** keystrokes are undone one at a time until the AI change is reached, after which one more Undo reverses the full AI change.
3. **Given** the buffer contains an AI change entry, **When** the user hovers over the Undo button, **Then** a tooltip indicates the type of change that will be undone.

---

### User Story 3 - Redo a Reversed Change (Priority: P2)

After undoing one or more changes, the writer decides the original content was correct after all. They click Redo to re-apply the previously undone change.

**Why this priority**: Redo completes the undo/redo contract and prevents the user from feeling locked in after an accidental undo.

**Independent Test**: Can be tested by typing text, undoing, then clicking Redo and confirming the text is restored. Delivers standalone value.

**Acceptance Scenarios**:

1. **Given** the user has just undone a keystroke, **When** they click Redo, **Then** that keystroke is re-applied and the document returns to the state before the undo.
2. **Given** the user has just undone an AI change, **When** they click Redo, **Then** the full AI change is re-applied in one step.
3. **Given** the user makes a new manual edit after undoing, **When** they look at the Redo button, **Then** the Redo button is disabled because the redo stack has been cleared.

---

### User Story 4 - Toolbar Always Visible (Priority: P2)

The writer always has easy access to Undo and Redo without memorising keyboard shortcuts. A toolbar appears above the document editor area with clearly labelled Undo and Redo buttons that reflect the current state of the history.

**Why this priority**: Discoverability is important; the toolbar is the primary visible entry point for undo/redo.

**Independent Test**: Can be tested purely visually: load the editor and confirm the toolbar and buttons are rendered with correct enabled/disabled states.

**Acceptance Scenarios**:

1. **Given** the editor is loaded with no changes made, **When** the user views the toolbar, **Then** both the Undo and Redo buttons are disabled.
2. **Given** the user has made at least one change, **When** viewing the toolbar, **Then** the Undo button is enabled.
3. **Given** the redo stack is empty, **When** viewing the toolbar, **Then** the Redo button is disabled.

---

### Edge Cases

- What happens when the undo buffer is full and the user makes a new change? The oldest entry is evicted to make room; the user cannot undo beyond the buffer limit.
- What happens if the user refreshes the page? The undo/redo history is not persisted and is lost on page reload.
- What happens with a concurrent AI edit while the user is typing? The in-progress keystroke sequence is closed as a boundary before the AI change is recorded as its own entry.
- How does undo interact with document auto-save? Undo reverses in-memory state; auto-save picks up the post-undo content on the next save cycle.
- What if the buffer size in `.env` is set to zero or a negative value? The system falls back to a safe minimum (default: 1000 entries) and logs a warning at startup.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The editor MUST display a persistent toolbar above the text editing area containing at minimum an Undo button and a Redo button.
- **FR-013**: The editor MUST support keyboard shortcuts for undo (Ctrl+Z) and redo (Ctrl+Y / Ctrl+Shift+Z) as equivalents to the toolbar buttons.
- **FR-002**: Each individual keystroke entered by the user MUST be recorded as a discrete entry in the undo buffer.
- **FR-003**: Each AI-generated change to the document MUST be recorded as a single atomic entry in the undo buffer, regardless of how many characters it affects. The AI change boundary is detected client-side when the agent's document swap is received; the undo system treats this received swap as the atomic boundary signal.
- **FR-004**: Clicking Undo MUST reverse the most recent entry in the undo buffer and move that entry to the redo stack.
- **FR-005**: Clicking Redo MUST re-apply the most recently undone entry from the redo stack.
- **FR-006**: Making any new manual edit after one or more undos MUST clear the redo stack entirely.
- **FR-007**: The Undo button MUST be disabled when the undo buffer is empty.
- **FR-008**: The Redo button MUST be disabled when the redo stack is empty.
- **FR-009**: The maximum number of entries retained in the undo buffer MUST be configurable via an environment variable in `.env`.
- **FR-010**: When the buffer reaches its maximum size, the oldest entry MUST be evicted to accommodate a new entry.
- **FR-011**: If the configured buffer size is invalid (zero, negative, or non-numeric), the system MUST fall back to a safe default and log a warning.
- **FR-012**: The undo/redo history MUST NOT persist across page reloads.

### Key Entities

- **Undo Entry**: A single reversible change. Has a type (keystroke or AI change), and stores only the delta — for a keystroke this is the character and cursor position; for an AI change this is the full diff of what was replaced.
- **Undo Buffer**: An ordered collection of undo entries with a configured maximum capacity. Oldest entries are evicted when the buffer is full.
- **Redo Stack**: An ordered collection of entries that have been undone and can be re-applied. Cleared whenever a new user edit is made.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can undo any manual keystroke within one interaction — either a toolbar button click or a keyboard shortcut (Ctrl+Z) — with the document visually updating immediately.
- **SC-002**: A user can undo a complete AI-generated change within one interaction, restoring the document to its exact pre-AI state.
- **SC-003**: The Undo and Redo buttons accurately reflect availability (enabled/disabled) at all times with no perceptible delay.
- **SC-004**: The undo buffer honours its configured size limit: attempts to undo beyond the limit are blocked and the button is disabled.
- **SC-005**: 100% of undo and redo operations complete without data loss or corruption to the document content.

## Clarifications

### Session 2026-03-15

- Q: How should each undo entry store document state — full snapshot or delta? → A: Delta only — store what changed and where (character + position per keystroke; diff for AI changes).
- Q: How does the undo system know when an AI change begins and ends? → A: Explicit signal from the AI agent — the agent notifies the undo system when its change begins and ends.
- Q: Are keyboard shortcuts (Ctrl+Z / Ctrl+Y) in scope alongside the toolbar buttons? → A: In scope — keyboard shortcuts are required alongside the toolbar buttons.

## Assumptions

- "Keystroke" granularity means one character insertion or deletion per undo step, not word-level grouping. The buffer may therefore hold thousands of entries for a long editing session.
- Keyboard shortcuts (Ctrl+Z for undo, Ctrl+Y or Ctrl+Shift+Z for redo) are in scope and required alongside the toolbar buttons.
- The default buffer size (when the `.env` variable is absent or invalid) is 1000 entries.
- AI changes originate from the existing AI agent workflow already present in the application. The agent is responsible for emitting explicit start/end boundary signals to the undo system.
- Undo/redo state is maintained client-side in the browser session only; no server-side history storage is required.
