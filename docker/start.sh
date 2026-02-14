#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="neo4j-kg"
CONTAINER_NAME="neo4j-kg"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Build the image (once)
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"

# Remove old container if exists
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Run Neo4j with persistent volumes
docker run -d \
  --name "$CONTAINER_NAME" \
  -p 7474:7474 -p 7687:7687 \
  -v "$PROJECT_DIR/neo4j/kgdata:/data" \
  -v "$PROJECT_DIR/neo4j/kglogs:/logs" \
  -v "$PROJECT_DIR/neo4j/kgimport:/var/lib/neo4j/import" \
  "$IMAGE_NAME"

echo "Neo4j is starting..."
echo "  Browser:  http://localhost:7474"
echo "  Bolt:     bolt://localhost:7687"
echo "  Auth:     neo4j / password"
