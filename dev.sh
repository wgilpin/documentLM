#!/bin/bash
set -e

# Start postgres in Docker
docker compose -f docker-compose.dev.yml up -d

# Load .env, override DATABASE_URL host to localhost
set -a
source .env
set +a
export DATABASE_URL="${DATABASE_URL//@postgres:/@localhost:}"

export DEV_PASSWORD=devPassword1234

# Build JS bundle (install deps on first run)
[ -d node_modules ] || npm install --silent
npm run build:dev

# Run migrations then start the app
uv run alembic upgrade head
uv run uvicorn writer.main:app --reload
