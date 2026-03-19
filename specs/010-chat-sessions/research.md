# Research: Chat Session Management

**Branch**: `010-chat-sessions` | **Date**: 2026-03-18

## Decision Log

### 1. Session State Machine — One Active Per User/Document

**Decision**: Enforce exactly one `active` session per `(user_id, document_id)` pair at the service layer. Transitions: creating a new chat or reactivating an archived session sets the target to `active` and archives any previously-active session in a single atomic operation.

**Rationale**: Clarification Q1 confirmed Option A. A single-active-session invariant simplifies queries (get the active session = `WHERE status = 'active'`) and prevents inconsistent UI state.

**Alternatives considered**: Allowing multiple "in-progress" sessions (rejected — user confirmed single active model); per-session "current" flag (redundant with status enum).

---

### 2. Migration Strategy for Existing Messages

**Decision**: Create one default `chat_sessions` row per `(user_id, document_id)` pair that has existing `chat_messages`, then backfill `session_id` on all existing messages. The default session gets `status = 'active'` and `created_at` equal to the earliest message in that group. Make `session_id` NOT NULL after backfill.

**Rationale**: Existing messages must not be orphaned. Creating a synthetic "Session 1" per document preserves all history. Users will see their existing conversation in the dropdown as the first session.

**Alternatives considered**: Delete existing messages on migration (rejected — data loss); keep `session_id` nullable forever (rejected — weakens invariant).

---

### 3. HTMX Strategy for Session Switching

**Decision**: Use HTMX out-of-band (OOB) swaps. When a session is switched or a new one created, the server returns:
- The new session's message history (targets `#chat-history`)
- The updated dropdown (OOB targets `#chat-session-dropdown`)

**Rationale**: HTMX OOB is the idiomatic pattern for updating multiple DOM targets from a single response. Avoids custom JS. Consistent with the project's minimize-JS constitution principle.

**Alternatives considered**: Full-page reload (rejected — disruptive UX); custom JS fetch (rejected — violates constitution); separate HTMX requests (possible but requires coordination, OOB is cleaner).

---

### 4. Session Label in Dropdown

**Decision**: Label each session by creation date/time formatted as `"Chat — MMM D, YYYY h:mm A"` (e.g., "Chat — Mar 18, 2026 2:34 PM"). The active session is labelled `"Current Chat"`. Ordering: most recent first.

**Rationale**: Date/time labels are unambiguous and require no additional user input. "Current Chat" for the active session gives a clear anchor point.

**Alternatives considered**: Sequential numbering ("Chat 1", "Chat 2") — rejected because numbers are meaningless after many sessions; user-defined names — out of scope per spec.

---

### 5. Document Context — Always Current

**Decision**: When the chat agent is invoked for any session (active or reactivated), it receives the current document title, overview, and content — not a snapshot from when the session was created.

**Rationale**: Clarification Q3 confirmed Option A. Avoids storing document snapshots (significant storage/complexity). The assistant always reasons about the living document.

**Alternatives considered**: Document snapshot per session (rejected by user in clarification).

---

### 6. ADK Session Service — No Change

**Decision**: The existing `InMemorySessionService` from `google-adk` used in `invoke_chat_agent` remains unchanged. It is a per-request in-memory session, not a persisted session.

**Rationale**: The ADK session is a temporary vehicle for passing conversation history to the model. Persisted sessions are stored in PostgreSQL and loaded into the ADK call as `history=` parameter. No conflict.

---

### 7. "New Chat" When No Messages Exist

**Decision**: If the current active session has zero messages, clicking "New Chat" is a no-op — no new session is created, no empty session archived. FR-011 satisfied.

**Rationale**: Empty sessions add noise to the dropdown. Service layer enforces: only create + archive if `len(current_session_messages) > 0`.

---

### 8. Reactivated Session — Chat Initialization

**Decision**: When an archived session is reactivated and the user sends a message, the standard `process_chat` flow runs with the reactivated session's history. The automatic overview-seeding initialization (`initialize_chat_with_overview`) does NOT re-run — it only applies to brand-new sessions on first open.

**Rationale**: Reactivated sessions already have history; re-running initialization would corrupt the conversation.

---

### 9. User Isolation

**Decision**: All session queries filter by `user_id`. The `chat_sessions` table has `user_id` as a non-nullable FK. No endpoint exposes another user's sessions.

**Rationale**: Clarification Q2 confirmed sessions are private per user.

---

### 10. No New ADK Agents

**Decision**: No new agent types are introduced. The existing `ChatAgent` is used for all chat sessions.

**Rationale**: Constitution Principle IV (YAGNI) and ADK architecture gate. Multi-session support is a storage/routing concern, not an agent concern.
