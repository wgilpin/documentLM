# Data Model: Multi-User Access with Invite Codes and Document Privacy

**Branch**: `009-multi-user-invite` | **Date**: 2026-03-17

---

## New Tables

### `users`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, default gen_random_uuid() | |
| `email` | VARCHAR | NOT NULL, UNIQUE | Login identifier; normalized to lowercase |
| `password_hash` | VARCHAR | NOT NULL | bcrypt hash via passlib |
| `created_at` | TIMESTAMP WITH TIME ZONE | NOT NULL, default now() | |

**Relationships**: One user owns many documents, sources, chat_messages, one user_settings row.

---

### `invite_codes`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, default gen_random_uuid() | |
| `code` | VARCHAR(32) | NOT NULL, UNIQUE | 32-char hex string (secrets.token_hex(16)) |
| `created_at` | TIMESTAMP WITH TIME ZONE | NOT NULL, default now() | |
| `used_at` | TIMESTAMP WITH TIME ZONE | NULLABLE | NULL = unused |
| `used_by_user_id` | UUID | NULLABLE, FK → users(id) | NULL = unused |

**Validation rules**:
- A code is valid iff `used_at IS NULL`.
- On successful registration: set `used_at = now()`, `used_by_user_id = new_user.id` in the same transaction as user creation.
- If registration fails (e.g., email already taken): rollback — code remains unused.

---

## Modified Tables

### `documents` (existing)

**Added columns**:

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `user_id` | UUID | NOT NULL, FK → users(id) ON DELETE CASCADE | |
| `is_private` | BOOLEAN | NOT NULL, DEFAULT FALSE | Private flag |

**Migration**: Clean slate — delete all rows before adding `NOT NULL` columns.

---

### `sources` (existing)

**Added columns**:

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `user_id` | UUID | NOT NULL, FK → users(id) ON DELETE CASCADE | Denormalized for fast user-scoped queries |

**Notes**: `user_id` is denormalized here (could be derived via `document.user_id`) to allow efficient direct source queries without a join. Must always equal the parent document's `user_id`. Set at source creation time.

---

### `chat_messages` (existing)

**Added columns**:

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `user_id` | UUID | NOT NULL, FK → users(id) ON DELETE CASCADE | |

**Notes**: Denormalized from the document for the same reason as sources.

---

### `user_settings` (existing — schema change)

**Before**: `id INTEGER PK` (always 1) — singleton.

**After**: `user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `user_id` | UUID | PK, FK → users(id) ON DELETE CASCADE | Replaces integer id |
| `display_name` | VARCHAR | NULLABLE | |
| `language_code` | VARCHAR | NOT NULL, DEFAULT 'en' | |
| `ai_instructions` | TEXT | NULLABLE | |
| `updated_at` | TIMESTAMP WITH TIME ZONE | NOT NULL | |

**Migration**: Clean slate — drop and recreate with new schema.

---

### `comments` and `suggestions` (no change)

Both are transitively scoped to a user via their FK chain to `documents.user_id`. No direct `user_id` column needed. Authorization checks go through the parent document's ownership.

---

## Not-Modified

`comments`, `suggestions` — no schema changes. User ownership verified via document ownership.

---

## ChromaDB Vector Store

**Collection naming**: One collection per user, named `user_{user_id_no_dashes}`.
- Example: user UUID `a1b2c3d4-...` → collection name `user_a1b2c3d4...`

**Chunk metadata** (stored per embedding):

| Field | Type | Notes |
|-------|------|-------|
| `document_id` | str (UUID) | UUID of the parent document |
| `is_private` | bool | Mirrors parent document's `is_private` flag |

**Query patterns**:

| Context | ChromaDB `where` clause |
|---------|------------------------|
| Agent in non-private doc (cross-user search) | `{"is_private": False}` |
| Agent inside a private doc (self-only search) | `{"document_id": {"$eq": str(doc_id)}}` |

**Privacy toggle**: When `document.is_private` changes, call `collection.update(ids=[...all chunk IDs for doc...], metadatas=[...])` to flip `is_private` on all affected chunks. Chunk IDs already stored in PostgreSQL `sources.chunk_ids` (or tracked during indexing).

---

## Entity Relationships (summary)

```
users (1) ──< (N) documents ──< (N) sources
                 │                    │
                 │               chromadb chunks
                 │               (in user collection)
                 ├──< (N) chat_messages
                 ├──< (N) comments ──< (N) suggestions
                 └── (1) user_settings

invite_codes ──> (0/1) users  [used_by_user_id]
```

---

## Migration Strategy

The Alembic migration performs the following in order:

1. **Clean slate**: `DELETE FROM chat_messages; DELETE FROM suggestions; DELETE FROM comments; DELETE FROM sources; DELETE FROM documents; DELETE FROM user_settings;`
2. **Create** `users` table.
3. **Create** `invite_codes` table.
4. **Add** `user_id UUID NOT NULL` + `is_private BOOLEAN NOT NULL DEFAULT FALSE` to `documents` (safe since table is empty).
5. **Add** `user_id UUID NOT NULL` to `sources` (safe since table is empty).
6. **Add** `user_id UUID NOT NULL` to `chat_messages` (safe since table is empty).
7. **Recreate** `user_settings`: drop old table, create new with `user_id UUID PK`.
8. **Add FK constraints** for all `user_id` columns → `users(id) ON DELETE CASCADE`.

ChromaDB collections: The existing collection(s) are deleted at startup if migration version changes, or handled by `vector_store.py` ensuring collections are per-user.
