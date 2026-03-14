# HTMX Endpoint Contracts: UX Improvements

**Branch**: `003-ux-improvements` | **Date**: 2026-03-13

This document describes the new and modified HTTP endpoints introduced by this feature. All endpoints follow the existing project pattern: return rendered HTML partials when the `HX-Request` header is present, JSON otherwise.

---

## New Endpoints

### `GET /api/documents/{doc_id}/chat`

Retrieve the chat history for a document.

**Request**

| Item          | Value                  |
| ------------- | ---------------------- |
| Method        | GET                    |
| Auth          | None (session-less)    |
| HTMX trigger  | `hx-trigger="load"`    |
| HTMX target   | `#chat-history`        |

**Response (HTMX)**

- Status: `200 OK`
- Body: Zero or more rendered `partials/chat_message.html` fragments, ordered oldest-first.
- Each fragment: `<div class="chat-turn chat-turn--{role}" id="chat-{id}">...</div>`

**Response (JSON)**

```json
[
  {
    "id": "uuid",
    "document_id": "uuid",
    "role": "user",
    "content": "string",
    "created_at": "ISO8601"
  }
]
```

**Errors**

| Status | Condition              |
| ------ | ---------------------- |
| `404`  | Document not found     |

---

### `POST /api/documents/{doc_id}/chat`

Submit a user message and receive the assistant's reply.

**Request**

| Item          | Value                            |
| ------------- | -------------------------------- |
| Method        | POST                             |
| Content-Type  | `application/x-www-form-urlencoded` |
| HTMX trigger  | Form `submit`                    |
| HTMX target   | `#chat-history`                  |
| HTMX swap     | `beforeend`                      |

**Form fields**

| Field     | Type   | Required | Notes               |
| --------- | ------ | -------- | ------------------- |
| `content` | string | Yes      | User message body   |

**Response (HTMX)**

- Status: `200 OK`
- Body: Two rendered `chat_message.html` fragments appended — one for the `user` turn, one for the `assistant` reply.
- The form is reset via `hx-on::after-request="this.reset()"`.

**Response (JSON)**

```json
[
  {"id": "uuid", "role": "user",      "content": "...", ...},
  {"id": "uuid", "role": "assistant", "content": "...", ...}
]
```

**Errors**

| Status | Condition                                   |
| ------ | ------------------------------------------- |
| `404`  | Document not found                          |
| `502`  | `ChatAgent` invocation failed               |

---

## Modified Endpoints

### `POST /api/documents/{doc_id}/comments` — No Contract Change

The command modal and contextual floating menu both submit to this existing endpoint with the same fields (`selection_start`, `selection_end`, `selected_text`, `body`). When the command modal is used without a text selection, `selection_start` and `selection_end` default to `0` and `selected_text` is empty.

The endpoint currently validates that the selection matches document content. For global commands (no selection), the selection validation is skipped when `selection_start == selection_end == 0`.

**Change**: Update the selection-validation logic in `suggestions.py` to allow empty selections (start == end == 0).

---

## Unchanged Endpoints (Reference)

These endpoints are used by the redesigned UI but their contracts do not change:

| Endpoint                                          | Used By                        |
| ------------------------------------------------- | ------------------------------ |
| `GET /api/documents/{doc_id}/sources`             | Source list (still HTMX load)  |
| `POST /api/documents/{doc_id}/sources`            | Add source (details/summary)   |
| `DELETE /api/documents/{doc_id}/sources/{id}`     | Delete source (hover button)   |
| `GET /api/documents/{doc_id}/suggestions`         | Inline overlay (HTMX load)     |
| `POST /api/suggestions/{id}/accept`               | Inline accept button           |
| `POST /api/suggestions/{id}/reject`               | Inline reject button           |

---

## New Partials (Template Contracts)

### `partials/chat_message.html`

**Context variables**

| Variable | Type              | Description               |
| -------- | ----------------- | ------------------------- |
| `msg`    | `ChatMessageResponse` | The chat turn to render |
| `request` | `Request`        | FastAPI request object    |

**Rendered output structure**

```html
<div class="chat-turn chat-turn--{msg.role}" id="chat-{msg.id}">
  <span class="chat-role">{msg.role}</span>
  <div class="chat-content">{msg.content}</div>
</div>
```
