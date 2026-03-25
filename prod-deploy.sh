#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
# Build context is the parent directory (contains both documentLM/ and nlp_utils/)
BUILD_CONTEXT="$(dirname "$SCRIPT_DIR")"

echo "==> Building writer image..."
docker compose -f "$COMPOSE_FILE" build writer

echo "==> Restarting writer service..."
docker compose -f "$COMPOSE_FILE" up -d --no-build

echo "==> Waiting for writer to be healthy..."
for i in $(seq 1 20); do
    STATUS=$(docker compose -f "$COMPOSE_FILE" ps -q writer | xargs docker inspect --format='{{.State.Status}}' 2>/dev/null || echo "starting")
    if [ "$STATUS" = "running" ]; then
        echo "    writer is running."
        break
    fi
    sleep 2
done

echo "==> Done. Run 'docker compose -f $COMPOSE_FILE logs -f writer' to tail logs."
