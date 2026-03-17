# Implementation Plan: Multi-User Access with Invite Codes and Document Privacy

**Branch**: `009-multi-user-invite` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-multi-user-invite/spec.md`

## Summary

Add multi-user support with invite-only registration, complete per-user data isolation, a shared cross-document knowledge pool (per user), and a document-level Private flag. All existing single-user assumptions are removed: the singleton `UserSettings`, unowned documents/sources/chunks, and the hardcoded `"default_user"` agent identity. Existing data is cleared at migration time (clean slate). Authentication uses Starlette `SessionMiddleware` with signed cookies. Passwords are hashed with bcrypt via `passlib`. ChromaDB is reorganised into one collection per user. An admin CLI provides invite code generation and password reset.

---

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg
**New Dependencies**: `passlib[bcrypt]` (password hashing); `itsdangerous` (session signing — confirm present as transitive dep)
**Storage**: PostgreSQL (Docker container) + ChromaDB (local persistent directory `./data/chroma`)
**Auth**: Starlette `SessionMiddleware`, signed cookie, `user_id` stored in session
**Testing**: pytest — TDD for service layer only
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: web-service
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save
**Scale/Scope**: Demo/prototype — YAGNI; no new features without explicit user confirmation

---

## Constitution Check

- [x] **I. Python + uv**: All new code is Python; `uv add` used for new dependency
- [x] **II. TDD scope**: Tests planned for `auth_service`, updated `document_service`, `source_service`, `settings_service`, `vector_store` — no endpoint or frontend tests
- [x] **III. No remote APIs in tests**: Agent calls already mocked in existing tests; no change
- [x] **IV. Simplicity**: Scope matches spec exactly; no unrequested extras (no email notifications, no roles beyond user)
- [x] **V. Strong typing**: New `UserResponse`, `InviteCodeResponse`, `RegisterRequest`, `LoginRequest` Pydantic models; `get_current_user` returns typed `UserResponse`
- [x] **VI. Functional style**: All new code as module-level functions; no new classes beyond ORM models and Pydantic schemas
- [x] **VII. Ruff**: `ruff check --fix && ruff format` run on all modified files
- [x] **VIII. Containers**: No changes to docker-compose needed; `SECRET_KEY` added to `.env` only
- [x] **IX. Logging**: Auth events (login success/fail, registration, logout) logged at INFO/WARNING; all except blocks log at ERROR
- [x] **ADK architecture**: No new agent types; existing agents updated to receive `user_id: str` instead of `"default_user"`

---

## Project Structure

### Documentation (this feature)

```text
specs/009-multi-user-invite/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions and rationale
├── data-model.md        # Phase 1 — new/modified tables and ChromaDB layout
├── quickstart.md        # Phase 1 — setup and first-run guide
├── contracts/
│   ├── http-endpoints.md  # New and modified HTTP routes
│   └── cli.md             # Admin CLI commands
└── tasks.md             # Phase 2 — created by /speckit.tasks
```

### Source Code Changes

```text
src/writer/
├── main.py                        # MOD: add SessionMiddleware
├── api/
│   ├── auth.py                    # NEW: /auth/login, /auth/register, /auth/logout
│   └── documents.py               # MOD: PATCH privacy endpoint; user-scoped queries
│   (all other api/*.py)           # MOD: add get_current_user dependency
├── core/
│   └── auth.py                    # NEW: get_current_user() FastAPI dependency
├── models/
│   ├── db.py                      # MOD: User, InviteCode ORM models; user_id FK on
│   │                              #      documents, sources, chat_messages; is_private
│   │                              #      on documents; user_id PK on user_settings
│   └── schemas.py                 # MOD: UserResponse, RegisterRequest, LoginRequest,
│                                  #      InviteCodeResponse; DocumentResponse +is_private
├── services/
│   ├── auth_service.py            # NEW: register_user, login_user, hash_password,
│   │                              #      verify_password, create_invite_codes,
│   │                              #      reset_user_password
│   ├── document_service.py        # MOD: all queries filter by user_id; toggle_privacy
│   ├── source_service.py          # MOD: all queries filter by user_id; pass user_id on create
│   ├── chat_service.py            # MOD: pass user_id to agent calls
│   ├── settings_service.py        # MOD: per-user (user_id param); remove singleton logic
│   └── vector_store.py            # MOD: per-user collections; is_private metadata;
│                                  #      privacy-aware query; update_privacy()
├── cli/
│   ├── __init__.py                # NEW (empty)
│   └── admin.py                   # NEW: generate-invite, reset-password commands
└── templates/
    ├── login.html                 # NEW
    └── register.html              # NEW

migrations/versions/
└── xxxx_add_multi_user_support.py # NEW: clean-slate migration
```

---

## Complexity Tracking

No constitution violations. No complexity justifications required.

---

## Phase 0: Research

**Status**: Complete. See [research.md](research.md).

Key decisions:

| Topic | Decision |
|-------|----------|
| Session auth | Starlette `SessionMiddleware` + signed cookie |
| Password hashing | `passlib[bcrypt]` |
| ChromaDB isolation | One collection per user; `is_private` metadata on chunks |
| Invite code format | `secrets.token_hex(16)` — 32-char hex |
| UserSettings | Per-user row with `user_id UUID PK`; singleton dropped |
| Admin CLI | `argparse` stdlib; `src/writer/cli/admin.py` |
| Agent user identity | Replace `"default_user"` with `str(user_id)` passed through call chain |

---

## Phase 1: Design & Contracts

**Status**: Complete.

### Data Model

See [data-model.md](data-model.md).

New tables: `users`, `invite_codes`
Modified tables: `documents` (+`user_id`, +`is_private`), `sources` (+`user_id`), `chat_messages` (+`user_id`), `user_settings` (new PK `user_id UUID`)

### Interface Contracts

See [contracts/http-endpoints.md](contracts/http-endpoints.md) and [contracts/cli.md](contracts/cli.md).

New HTTP routes: `GET/POST /auth/login`, `GET/POST /auth/register`, `POST /auth/logout`, `PATCH /api/documents/{doc_id}/privacy`
New CLI commands: `generate-invite [--count N]`, `reset-password <email> <password>`

### Agent Context

Run after writing plan:

```bash
bash .specify/scripts/bash/update-agent-context.sh claude
```

---

## Implementation Notes

### Service Layer Changes

**`auth_service.py`** (new):

- `register_user(db, invite_code: str, email: str, password: str) -> UserResponse` — validate code, create user, mark code used, all in one transaction
- `authenticate_user(db, email: str, password: str) -> UserResponse | None` — look up user, verify hash
- `hash_password(plain: str) -> str` — passlib bcrypt hash
- `verify_password(plain: str, hashed: str) -> bool` — passlib verify
- `create_invite_codes(db, count: int) -> list[str]` — bulk insert, return codes
- `reset_password(db, email: str, new_password: str) -> None` — update hash by email

**`document_service.py`** (modified):

- All `SELECT` queries gain `WHERE documents.user_id = :user_id`
- `toggle_privacy(db, doc_id, user_id, is_private) -> DocumentResponse` — new function; also triggers `vector_store.update_privacy()`

**`vector_store.py`** (modified):

- `get_collection(user_id: UUID) -> Collection` — get or create `user_{user_id_hex}` collection
- `add_chunks(user_id, doc_id, is_private, ...)` — include metadata
- `query_chunks(user_id, doc_id, is_private_doc, query_text, ...)` — privacy-aware query
- `update_privacy(user_id, doc_id, is_private)` — update `is_private` metadata on all chunks for a document
- `delete_document_chunks(user_id, doc_id)` — delete from user collection by `document_id`

### Auth Dependency (`core/auth.py`)

```python
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> UserResponse:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"Location": "/auth/login"})
    user = await get_user_by_id(db, UUID(user_id))
    if not user:
        request.session.clear()
        raise HTTPException(status_code=302, headers={"Location": "/auth/login"})
    return user
```

### Privacy Toggle Consistency

When `toggle_privacy` is called:

1. Update `documents.is_private` in PostgreSQL (in transaction).
2. Call `vector_store.update_privacy(user_id, doc_id, is_private)` — updates ChromaDB chunk metadata.
3. Return updated `DocumentResponse`.

Both updates happen in the same request; if ChromaDB update fails, log error but do not roll back the PostgreSQL transaction (ChromaDB is not transactional). The next re-index of the document would restore consistency.

### Existing ChromaDB Data

On migration, existing ChromaDB data (in the old single default collection) is stale. `vector_store.py` must handle the case where a user's collection does not yet exist (`get_or_create_collection`). Old data in any unnamed or default collection is ignored; no explicit cleanup script is needed since the old collection is never queried.
