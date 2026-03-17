# Quickstart: Multi-User Setup

**Branch**: `009-multi-user-invite` | **Date**: 2026-03-17

This guide covers the steps to bring up the multi-user version of the application for the first time.

---

## 1. Add New Dependency

```bash
uv add "passlib[bcrypt]"
```

Verify `itsdangerous` is present (transitive via Starlette — should already be in the lock file):

```bash
uv run python -c "import itsdangerous; print('ok')"
```

---

## 2. Add `SECRET_KEY` to `.env`

Generate a secure key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add to `.env`:

```
SECRET_KEY=<output from above>
```

> **Warning**: Never commit `.env` to version control. The `SECRET_KEY` signs session cookies — if leaked, sessions can be forged.

---

## 3. Run the Migration

> **Warning**: This migration **deletes all existing data** (documents, sources, chunks, settings). There is no rollback for the data deletion.

```bash
uv run alembic upgrade head
```

The migration:
- Creates `users` and `invite_codes` tables
- Adds `user_id` and `is_private` to `documents`
- Adds `user_id` to `sources`, `chat_messages`
- Replaces the singleton `user_settings` row with a per-user schema

---

## 4. Generate Your First Invite Code

```bash
uv run python -m writer.cli.admin generate-invite
```

Copy the printed code — you will need it to register your first account.

---

## 5. Start the Application

```bash
docker-compose up -d postgres
uv run uvicorn writer.main:app --reload
```

Or full stack:

```bash
docker-compose up --build
```

---

## 6. Register Your Account

Navigate to `http://localhost:8000/auth/register` and enter:
- The invite code from Step 4
- Your email address
- A password (minimum 8 characters)

You will be redirected to the home page on success.

---

## 7. Invite Additional Users

```bash
uv run python -m writer.cli.admin generate-invite --count 5
```

Share each code individually. Each code works for exactly one registration.

---

## 8. Reset a Forgotten Password

```bash
uv run python -m writer.cli.admin reset-password user@example.com newpassword123
```
