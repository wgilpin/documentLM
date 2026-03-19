# Feature Specification: Chat Session Management

**Feature Branch**: `010-chat-sessions`
**Created**: 2026-03-18
**Status**: Draft
**Input**: User description: "you should be able to start a new chat. The old chats should be archived but available via dropdown in the chat ui. A new chat reverts to empty context, apart from system prompt, title, overview, document content"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a New Chat (Priority: P1)

A writer is working on a document and has had a long conversation with the AI assistant. They want to start fresh — perhaps exploring a different angle — without losing access to the previous conversation. They click "New Chat" and immediately have a clean slate, while the old conversation is preserved.

**Why this priority**: Core to the feature. Without the ability to start a new chat, nothing else here is meaningful. Delivers immediate value as a standalone capability.

**Independent Test**: Can be fully tested by clicking "New Chat" from an active chat session, verifying the input area is empty and the message history is cleared, while confirming the document title/overview/content remain visible.

**Acceptance Scenarios**:

1. **Given** a user has an ongoing chat with several messages, **When** they click "New Chat", **Then** a new empty chat session opens with no prior messages visible
2. **Given** a new chat has been started, **When** the user views the chat area, **Then** the document title, overview, and content context are still present in the assistant's context
3. **Given** a new chat has been started, **When** the user views the chat area, **Then** no previous chat messages from the prior session are shown
4. **Given** a new chat has been started, **When** the user sends a message, **Then** the assistant responds with no memory of the previous session's conversation

---

### User Story 2 - Access Archived Chats via Dropdown (Priority: P2)

A writer previously had a productive conversation that generated useful ideas. Later, after starting a new chat, they want to review what was discussed. They open a dropdown in the chat UI and select the previous session to read through it.

**Why this priority**: Without this, users lose access to prior work when starting a new chat. This completes the "archive but accessible" requirement.

**Independent Test**: Can be fully tested by starting a new chat (with Story 1 in place), then opening the dropdown and selecting a prior session — verifying the prior messages are displayed correctly.

**Acceptance Scenarios**:

1. **Given** a user has started one or more new chats, **When** they open the chat session dropdown, **Then** all previous chat sessions are listed with identifiable labels (e.g., date/time or sequential number)
2. **Given** the dropdown is open and shows prior sessions, **When** the user selects an archived session, **Then** that session's messages are displayed in the chat area
3. **Given** an archived session is being viewed, **When** the user sends a new message, **Then** that session becomes the active session, the previously-active session is archived, and the system responds in the context of that session's history
4. **Given** an archived session is selected, **When** the user views it, **Then** the document title, overview, and content are still accessible in context

---

### User Story 3 - Session Persistence Across Page Loads (Priority: P3)

A writer starts a new chat, closes the browser, and returns later. They expect their chat history — including archived sessions — to still be available.

**Why this priority**: Persistence is important for long-term usability but not required for the core feature to be functional. The core value (new chat + archive access) works without cross-session persistence.

**Independent Test**: Can be tested by starting a new chat, reloading the page, and verifying both the current session and archived sessions are still available in the dropdown.

**Acceptance Scenarios**:

1. **Given** a user has multiple chat sessions, **When** they reload the page or return after closing the browser, **Then** all previous sessions are still available in the dropdown
2. **Given** a user was viewing the most recent chat session, **When** they reload, **Then** the most recent session is shown by default

---

### Edge Cases

- What happens when a user tries to start a new chat before sending any messages in the current session? (The current empty session should not create a duplicate entry in the archive)
- What happens if a user has a very large number of archived sessions? (The dropdown must remain usable — consider limiting visible items or providing scroll)
- What happens if a new chat is started but the document has no title or overview? (Chat still starts; those fields are simply absent from the context)
- How does the system handle concurrent sessions from multiple browser tabs? (Assume last-write-wins; no cross-tab synchronisation required in this version)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to start a new chat session from the chat UI via a clearly labelled action (e.g., "New Chat" button)
- **FR-002**: Starting a new chat MUST clear the visible chat message history, presenting an empty conversation view
- **FR-003**: The new chat session MUST inherit the current document's title, overview, and content as context for the assistant, along with the system prompt
- **FR-004**: The new chat session MUST NOT inherit any prior conversation messages from previous sessions
- **FR-005**: Previously active chat sessions MUST be automatically archived when a new chat is started
- **FR-006**: Archived sessions MUST be accessible via a dropdown control in the chat UI
- **FR-007**: Each archived session MUST be identifiable in the dropdown (e.g., by creation date/time or a sequential label)
- **FR-008**: Users MUST be able to select an archived session from the dropdown to view its message history
- **FR-009**: Selecting an archived session MUST display that session's full message history in the chat area
- **FR-010**: Sessions (current and archived) MUST be persisted across page reloads
- **FR-013**: Chat sessions MUST be scoped to the individual user — a user MUST NOT be able to view another user's sessions, even on a shared document
- **FR-011**: Starting a new chat when the current session has no messages MUST NOT create an empty archived session entry
- **FR-012**: The dropdown MUST remain usable when there are many archived sessions (e.g., scrollable list)

### Key Entities

- **Chat Session**: A discrete conversation thread associated with a document. Has a creation timestamp, an ordered list of messages, and a status (active or archived). Belongs to a specific document.
- **Chat Message**: A single message within a session, with a role (user or assistant) and content. Ordered within its session.
- **Document Context**: The title, overview, and content of the document — used to initialise the assistant's context for each session but not stored per-session (always reflects the current document state).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can start a new chat in 1 click
- **SC-002**: A new chat session is ready to accept input within 2 seconds of the user initiating it
- **SC-003**: All previous chat sessions for a document are accessible from the dropdown without navigating away from the document view
- **SC-004**: Users can retrieve and read a prior session's full conversation history within 3 seconds of selecting it from the dropdown
- **SC-005**: Zero prior conversation messages appear in a newly started chat session
- **SC-006**: All sessions (active and archived) survive a page reload without data loss

## Clarifications

### Session 2026-03-18

- Q: When a user selects an archived session and sends a new message, what happens to the previously-active session? → A: Only one active session at a time — reactivating an archived session archives whatever was previously active (Option A)
- Q: Are chat sessions scoped to the individual user, or shared across all collaborators on a document? → A: Private per user — each user sees only their own sessions for a document (Option A)
- Q: When sending a message in a reactivated archived session, should the assistant use current document content or the content at time of session creation? → A: Always use current document content (Option A)

## Assumptions

- Each chat session belongs to a single document; cross-document sessions are out of scope
- The system prompt is a global or document-level setting that applies to all sessions for a document — it is not per-session
- Session labels in the dropdown default to creation date/time; custom naming of sessions is out of scope for this feature
- Deleting or renaming archived sessions is out of scope for this feature
- The number of archived sessions per document is assumed to be small (tens, not thousands) — no pagination or search is required for the initial release
- Selecting an archived session from the dropdown and sending a message reactivates that session, automatically archiving whatever session was previously active — only one session is active at a time
- Chat sessions are private to the user who created them — collaborators on the same document cannot see each other's sessions
- Sharing sessions between users is out of scope for this feature
