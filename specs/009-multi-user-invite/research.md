# Research: Multi-User Access with Invite Codes and Document Privacy

**Branch**: `009-multi-user-invite` | **Date**: 2026-03-17

---

## Decision 1: Session Management

**Decision**: Starlette `SessionMiddleware` with a signed cookie, storing `user_id` in `request.session`.

**Rationale**: This is a server-rendered (HTMX) application — all HTML is generated server-side and there is no JavaScript SPA. Signed server-side sessions via Starlette's built-in middleware are the natural fit. `itsdangerous` (the signing library) is already a transitive dependency of Starlette/FastAPI; no new package needed. JWT tokens are better suited to SPAs with separate API backends.

**Alternatives considered**:
- JWT in cookie: Adds complexity (token expiry, refresh tokens) with no benefit for a server-rendered app.
- `fastapi-users`: Opinionated third-party library that would require restructuring the codebase to fit its assumptions. YAGNI.
- Database-backed sessions: More complex than needed for a prototype.

**Config**:
- Add `SessionMiddleware` to `main.py` with a `SECRET_KEY` from environment.
- `SECRET_KEY` must be at least 32 random bytes (hex or base64). Add to `.env`.

---

## Decision 2: Password Hashing

**Decision**: `passlib[bcrypt]` — `CryptContext(schemes=["bcrypt"])` for hashing and verification.

**Rationale**: Well-established Python standard for password hashing. Simple two-function API (`hash` and `verify`). Bcrypt is a proven adaptive hash function appropriate for credentials. Not currently in `pyproject.toml`; must be added as a dependency.

**Alternatives considered**:
- `argon2-cffi`: More modern (Argon2 won the Password Hashing Competition) but passlib/bcrypt is sufficient for this prototype and has wider documentation coverage.
- `hashlib` (stdlib): Not suitable — no salting, not adaptive, not designed for passwords.

---

## Decision 3: ChromaDB User Isolation Strategy

**Decision**: One ChromaDB collection per user, named `user_{user_id_hex}` (UUID without dashes). Store `document_id` (str) and `is_private` (bool) as metadata on every chunk.

**Rationale**:
- Per-user collections provide hard isolation — cross-user contamination is structurally impossible.
- Deleting a user's entire knowledge base is a single `delete_collection()` call.
- ChromaDB ≥1.5.5 (already in use) supports `$in` and `$nin` metadata operators, enabling efficient filtering.

**Query patterns**:
- Agent in non-private doc → `where={"is_private": False}` (all user's non-private chunks)
- Agent in private doc → `where={"document_id": {"$eq": str(doc_id)}}` (only that doc's chunks)

**Privacy toggle**:
- When doc marked private: `collection.update(ids=[...], metadatas=[{"is_private": True, ...}])` for all chunk IDs belonging to that document.
- When doc unmarked private: same pattern, `is_private=False`.
- Takes effect immediately on next query — no caching layer.

**Alternatives considered**:
- Single shared collection with `user_id` metadata filter: Works, but cross-user contamination possible if a filter bug slips through; harder to delete user data cleanly.
- Query-time document-list filtering (derive from PostgreSQL): Avoids ChromaDB metadata updates on toggle, but requires an extra DB round-trip per agent query and introduces risk of stale state if PG and Chroma diverge.

---

## Decision 4: Invite Code Format

**Decision**: 32-character lowercase hex string (16 random bytes, hex-encoded via `secrets.token_hex(16)`).

**Rationale**: Cryptographically random, unguessable, URL-safe, easy to copy/paste, no special characters. `secrets` is stdlib — no new dependency. 128 bits of entropy makes brute-force impossible.

**Alternatives considered**:
- UUID4: 36 chars with dashes; slightly longer, equivalent entropy.
- Random words: Requires a word list; harder to implement securely.

---

## Decision 5: UserSettings Migration

**Decision**: Replace the singleton `id=1` integer primary key with `user_id UUID PRIMARY KEY REFERENCES users(id)`. One settings row per user, created on first access (upsert by `user_id`).

**Rationale**: The singleton pattern fundamentally breaks with multi-user. The clean-slate migration (all existing data deleted) makes this a non-breaking change — no row migration needed, only schema change.

**Alternatives considered**:
- Keep integer PK, add `user_id` FK: Redundant complexity. The user_id IS the natural key.

---

## Decision 6: Admin CLI Tool

**Decision**: `src/writer/cli/admin.py` using Python `argparse` (stdlib). Invoked via `uv run python -m writer.cli.admin <command>`.

**Commands**:
- `generate-invite [--count N]` — prints N invite codes (default 1)
- `reset-password <email> <new_password>` — sets a new bcrypt hash for the user

**Rationale**: `argparse` requires no new dependency. The CLI runs in the same environment as the app and connects to the same database via SQLAlchemy (synchronous or new async event loop). Simple, YAGNI.

**Alternatives considered**:
- `click`: Nicer API but adds a dependency.
- Django-style management commands: Over-engineered for two commands.

---

## Decision 7: Agent User Identity

**Decision**: Pass `user_id: UUID` through the agent call chain, replacing the hardcoded `_USER_ID = "default_user"` constant in Google ADK session setup.

**Rationale**: Google ADK's `Runner` uses a `user_id` string for session scoping. Replacing the hardcoded constant with the authenticated user's UUID string ensures each user's agent sessions are isolated within ADK's in-memory session store.

**Scope**: No new agent types introduced. Existing agents (chat, research, planner, drafter) remain unchanged in capability; only session scoping changes.

---

## Dependency Changes

| Package | Action | Reason |
|---------|--------|--------|
| `passlib[bcrypt]` | Add | Password hashing |
| `itsdangerous` | Verify present | SessionMiddleware signing (transitive via Starlette — confirm in lock file) |
