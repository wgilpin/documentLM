# API Contract: Chat Sessions

**Branch**: `010-chat-sessions` | **Date**: 2026-03-18

All endpoints require an authenticated session (`user_id` in `request.session`). All paths are prefixed under the existing document router.

---

## New Endpoints

### POST `/api/documents/{doc_id}/chat/sessions`

**Purpose**: Start a new chat session. Archives the current active session (if it has messages). Creates a new active session.

**Request**: No body.

**Response** (HTMX or JSON):
- `200 OK` — new session created (or no-op if current session is empty)

HTMX response body:
```html
<!-- Clears chat history -->
<div id="chat-history"></div>
<!-- OOB: updates dropdown -->
<div id="chat-session-dropdown" hx-swap-oob="true">
  ... updated dropdown HTML ...
</div>
```

JSON response (non-HTMX):
```json
{
  "session": {
    "id": "uuid",
    "status": "active",
    "created_at": "ISO8601",
    "label": "Current Chat"
  }
}
```

**Error cases**:
- `403 Forbidden` — document does not belong to current user
- `404 Not Found` — document not found

---

### GET `/api/documents/{doc_id}/chat/sessions`

**Purpose**: List all sessions for the dropdown. Ordered most-recent first.

**Response** (JSON):
```json
{
  "sessions": [
    {
      "id": "uuid",
      "status": "active",
      "created_at": "ISO8601",
      "label": "Current Chat"
    },
    {
      "id": "uuid",
      "status": "archived",
      "created_at": "ISO8601",
      "label": "Chat — Mar 17, 2026 10:15 AM"
    }
  ]
}
```

**Error cases**:
- `403 Forbidden` — document does not belong to current user

---

### POST `/api/documents/{doc_id}/chat/sessions/activate`

**Purpose**: Reactivate an archived session (making it active, archiving the current active session). Triggered when the user selects an archived session from the dropdown.

**Request body** (form-encoded):

```text
session_id=<uuid>
```

**Response** (HTMX):
```html
<!-- Replaces chat history with the reactivated session's messages -->
<div id="chat-history">
  ... message HTML for selected session ...
</div>
<!-- OOB: updates dropdown -->
<div id="chat-session-dropdown" hx-swap-oob="true">
  ... updated dropdown HTML ...
</div>
```

JSON response:
```json
{
  "session_id": "uuid",
  "status": "active"
}
```

**Error cases**:
- `403 Forbidden` — session does not belong to current user
- `404 Not Found` — session not found
- `409 Conflict` — session is already active

---

## Modified Endpoints

### GET `/api/documents/{doc_id}/chat`

**Change**: Now returns only the messages for the current **active** session (was: all messages for the document).

No change to request/response contract shape — callers still receive HTML partial or JSON list. The filter is now `session_id = active_session.id` instead of `document_id`.

---

### POST `/api/documents/{doc_id}/chat`

**Change**: Message is now associated with the current active session (`session_id` set on new `ChatMessage`). No change to request/response contract.

---

### GET `/api/documents/{doc_id}/chat/stream`

**Change**: Stream is now scoped to the active session. On first open with no active session, a new session is created before seeding. No change to SSE event format.

---

## UI Contract: Chat Panel

The document template chat panel exposes these HTMX-driven elements:

| Element ID              | Purpose                                              |
|-------------------------|------------------------------------------------------|
| `#chat-history`         | Message list; swapped on session switch              |
| `#chat-session-dropdown`| Session selector; OOB-swapped after session changes  |
| `#chat-new-btn`         | "New Chat" button; triggers POST to sessions endpoint|

**Dropdown interaction**: Selecting an archived session triggers `POST /sessions/activate` with `session_id` in the request body, which replaces `#chat-history` and OOB-swaps the dropdown to reflect the new active session.
