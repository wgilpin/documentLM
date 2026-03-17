# CLI Contract: Admin Tool

**Branch**: `009-multi-user-invite` | **Date**: 2026-03-17
**Module**: `src/writer/cli/admin.py`
**Invocation**: `uv run python -m writer.cli.admin <command> [args]`

---

## Commands

### `generate-invite`

Generates one or more invite codes and prints them to stdout.

```
usage: python -m writer.cli.admin generate-invite [--count N]

optional arguments:
  --count N   Number of codes to generate (default: 1)
```

**Output**: One code per line on stdout. Each code is a 32-character lowercase hex string.

```
$ uv run python -m writer.cli.admin generate-invite --count 3
a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6
d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7
```

**Exit codes**:
- `0` — Success
- `1` — Database connection failure

---

### `reset-password`

Sets a new password for an existing user account.

```
usage: python -m writer.cli.admin reset-password <email> <new_password>

positional arguments:
  email         Email address of the user account
  new_password  New plaintext password (will be hashed before storage)
```

**Output**: Confirmation message on stdout.

```
$ uv run python -m writer.cli.admin reset-password user@example.com newpassword123
Password reset for user@example.com
```

**Exit codes**:
- `0` — Success
- `1` — User not found, or database connection failure

**Notes**:
- The plaintext password is never stored; it is hashed with bcrypt immediately.
- Minimum password length: 8 characters (same rule as registration).
- The user's active sessions are NOT invalidated — they can continue using existing sessions.

---

## Environment

The CLI reads the same `DATABASE_URL` environment variable (from `.env`) as the web application. It must be run from the project root or have the correct `.env` in scope.
