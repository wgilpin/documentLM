# HTTP Endpoint Contracts: Multi-User Access

**Branch**: `009-multi-user-invite` | **Date**: 2026-03-17

---

## New Endpoints

### Authentication

#### `GET /auth/login`

Returns the login page HTML.

- **Auth required**: No
- **Redirects to**: `/` if already authenticated
- **Response**: `200 text/html` — login form (email + password fields)

---

#### `POST /auth/login`

Authenticates a user.

- **Auth required**: No
- **Request**: `application/x-www-form-urlencoded`
  - `email: str`
  - `password: str`
- **Success**: `302` redirect to `/`; sets signed session cookie with `user_id`
- **Failure**: `200 text/html` — login page re-rendered with error message (invalid credentials)

---

#### `GET /auth/register`

Returns the registration page HTML.

- **Auth required**: No
- **Redirects to**: `/` if already authenticated
- **Response**: `200 text/html` — registration form (invite_code + email + password fields)

---

#### `POST /auth/register`

Creates a new user account using an invite code.

- **Auth required**: No
- **Request**: `application/x-www-form-urlencoded`
  - `invite_code: str`
  - `email: str`
  - `password: str`
- **Success**: `302` redirect to `/`; sets signed session cookie with `user_id`; marks invite code as used
- **Failure cases** (all re-render registration page with error):
  - Invalid or already-used invite code
  - Email already registered
  - Password too short (minimum 8 characters)

---

#### `POST /auth/logout`

Clears the session cookie.

- **Auth required**: Yes (no-op if not authenticated)
- **Request**: No body
- **Response**: `302` redirect to `/auth/login`

---

## Modified Endpoints

All existing endpoints now require authentication. Unauthenticated requests to any protected route redirect to `GET /auth/login`.

### Document Privacy Toggle (new capability on existing endpoint)

#### `PATCH /api/documents/{doc_id}/privacy`

Toggles the Private flag on a document.

- **Auth required**: Yes
- **Ownership**: Must own `doc_id`
- **Request**: `application/json`
  ```json
  { "is_private": true }
  ```
- **Success**: `200 application/json`
  ```json
  { "id": "...", "is_private": true, ... }
  ```
- **Failure**: `403 Forbidden` if user does not own document; `404 Not Found` if document does not exist (same response for both to avoid enumeration)

---

### Unchanged Contract Surface (auth enforcement added)

The following endpoints retain their existing request/response shape. The only change is:
- Session cookie (`user_id`) is required.
- All query results are filtered to the authenticated user's data.
- Attempting to access another user's resource returns `404` (same as missing resource).

| Method | Path | Change |
|--------|------|--------|
| GET | `/api/documents/` | Now returns only authenticated user's documents |
| POST | `/api/documents/` | Document created with authenticated user's `user_id` |
| GET | `/api/documents/{doc_id}` | `404` if not owned by current user |
| PUT | `/api/documents/{doc_id}` | `404` if not owned by current user |
| DELETE | `/api/documents/{doc_id}` | `404` if not owned by current user |
| GET/POST | `/api/documents/{doc_id}/chat` | Scoped to current user |
| GET | `/api/documents/{doc_id}/chat/stream` | Scoped to current user |
| GET/POST | `/{doc_id}/sources` | Scoped to current user |
| DELETE | `/{doc_id}/sources/{source_id}` | `404` if not owned by current user |
| GET/POST | `/api/settings` | Per-user settings (not singleton) |

---

## Auth Dependency

All protected routes use a FastAPI dependency `get_current_user(request: Request) -> UserResponse` defined in `src/writer/core/auth.py`. If `request.session.get("user_id")` is missing or invalid, it raises an HTTP redirect to `/auth/login`.
