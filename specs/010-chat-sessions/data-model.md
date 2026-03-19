# Data Model: Chat Session Management

**Branch**: `010-chat-sessions` | **Date**: 2026-03-18

## New Table: `chat_sessions`

| Column        | Type                      | Constraints                                         |
|---------------|---------------------------|-----------------------------------------------------|
| `id`          | UUID                      | PK, default `uuid4()`                               |
| `user_id`     | UUID                      | FK → `users.id` ON DELETE CASCADE, NOT NULL         |
| `document_id` | UUID                      | FK → `documents.id` ON DELETE CASCADE, NOT NULL     |
| `status`      | Enum(`active`,`archived`) | NOT NULL, default `active`                          |
| `created_at`  | DateTime (timezone)       | NOT NULL, server default `now()`                    |

**Indexes**:
- `ix_chat_sessions_user_document` on `(user_id, document_id)` — used for "get active session" and "list sessions" queries
- Partial unique index on `(user_id, document_id) WHERE status = 'active'` — enforces at-most-one-active-session invariant at the database level

**Invariant**: At most one row may have `status = 'active'` for any given `(user_id, document_id)` pair. Enforced by the partial unique index.

---

## Modified Table: `chat_messages`

**Added column**:

| Column       | Type | Constraints                                             |
|--------------|------|---------------------------------------------------------|
| `session_id` | UUID | FK → `chat_sessions.id` ON DELETE CASCADE, NOT NULL (after migration backfill) |

**New index**: `ix_chat_messages_session_created` on `(session_id, created_at)` — replaces the existing `(document_id, created_at)` index for history queries.

**Existing columns retained unchanged**: `id`, `user_id`, `document_id`, `role`, `content`, `created_at`

Note: `document_id` is kept on `chat_messages` to preserve the existing cascade-delete behaviour and avoid a JOIN for document-level queries.

---

## New Enum: `SessionStatus`

```
SessionStatus:
  active    — the session currently displayed; receives new messages
  archived  — prior session; read-only unless reactivated
```

---

## SQLAlchemy ORM (new model)

```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

---

## State Transition Diagram

```
                  ┌──────────────┐
                  │   [created]  │
                  └──────┬───────┘
                         │ auto on doc open (if no active session)
                         ▼
                    ┌─────────┐
          ◄─────── │  active  │ ───────────►
    reactivate      └─────────┘   new chat /
    (from archived)       │       reactivate other
                          │
                          ▼
                    ┌──────────┐
                    │ archived │
                    └──────────┘
                    (read-only unless reactivated)
```

**Transitions**:

| Trigger | From | To (target) | Side effect |
|---------|------|-------------|-------------|
| User opens doc, no active session | — | `active` (new) | Create new ChatSession row |
| User clicks "New Chat" (session has messages) | `active` | `archived` | Previous session archived; new `active` session created |
| User clicks "New Chat" (session empty) | `active` | no change | No-op (FR-011) |
| User selects archived session + sends message | `archived` | `active` | Previous `active` session archived; selected session set to `active` |

---

## Pydantic Schemas (new/updated)

```python
class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    status: SessionStatus
    created_at: datetime
    label: str  # computed: "Current Chat" or "Chat — MMM D, YYYY h:mm A"

class ChatMessageResponse(BaseModel):  # updated — add session_id
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    session_id: uuid.UUID
    document_id: uuid.UUID
    role: ChatRole
    content: str
    created_at: datetime
```

---

## Migration Plan

**Migration file**: `migrations/versions/XXXX_add_chat_sessions.py`

Steps (in order):
1. Create `session_status` enum type
2. Create `chat_sessions` table
3. Backfill: for each distinct `(user_id, document_id)` pair in `chat_messages`, insert one `chat_sessions` row with `status = 'active'` and `created_at = MIN(created_at)` for that group
4. Add `session_id` column to `chat_messages` (nullable initially)
5. Backfill `session_id` on all `chat_messages` rows by matching `(user_id, document_id)` to the session created in step 3
6. Set `session_id` NOT NULL
7. Add FK constraint `chat_messages.session_id → chat_sessions.id ON DELETE CASCADE`
8. Add index `ix_chat_messages_session_created` on `chat_messages(session_id, created_at)`
9. Add partial unique index on `chat_sessions(user_id, document_id) WHERE status = 'active'`
