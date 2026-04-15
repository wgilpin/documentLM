#!/bin/bash
set -e

# Start postgres in Docker
docker compose -f ../docker-compose.dev.yml --project-name documentlm up -d

# Wait for postgres to be ready
echo "Waiting for postgres..."
until docker compose -f ../docker-compose.dev.yml --project-name documentlm exec -T postgres pg_isready -q; do
  sleep 1
done

# Load .env, override DATABASE_URL host to localhost
set -a
source .env
set +a
export DATABASE_URL="${DATABASE_URL//@postgres:/@localhost:}"

export DEV_PASSWORD=devPassword1234

# Build JS bundle (install deps on first run)
[ -d node_modules ] || npm install --silent
npm run build:dev

# Start esbuild watch in background
npm run watch &
ESBUILD_PID=$!
trap "kill $ESBUILD_PID 2>/dev/null" EXIT

# Run migrations then start the app
uv run alembic upgrade head
uv run uvicorn writer.main:app --reload
