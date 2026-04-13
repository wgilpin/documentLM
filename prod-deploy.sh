#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$(dirname "$SCRIPT_DIR")/docker-compose.yml"
PROJECT_NAME="documentlm"
# Build context is two levels up (projects/ — contains document-projects/ and nlp_utils/)
BUILD_CONTEXT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "==> Building writer image..."
docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" build writer

echo "==> Restarting writer service..."
docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" up -d --no-build

echo "==> Waiting for writer to be healthy..."
for i in $(seq 1 20); do
    STATUS=$(docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" ps -q writer | xargs docker inspect --format='{{.State.Status}}' 2>/dev/null || echo "starting")
    if [ "$STATUS" = "running" ]; then
        echo "    writer is running."
        break
    fi
    sleep 2
done

echo "==> Done. Run 'docker compose -f $COMPOSE_FILE logs -f writer' to tail logs."
