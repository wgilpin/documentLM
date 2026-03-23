#!/bin/bash
set -e

# Start postgres in Docker
docker compose -f docker-compose.dev.yml up -d

# Load .env, override DATABASE_URL host to localhost
set -a
source .env
set +a
export DATABASE_URL="${DATABASE_URL//@postgres:/@localhost:}"

# Run migrations then start the app
uv run alembic upgrade head
uv run uvicorn writer.main:app --reload
