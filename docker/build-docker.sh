#!/bin/bash
# Build live ISO using Docker
#
# Usage: ./docker/build-docker.sh [output-dir]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-$REPO_ROOT/output}"

cd "$REPO_ROOT"

echo "Building live-iso Docker image..."
docker build -t live-iso-builder -f docker/Dockerfile .

echo "Running ISO build..."
mkdir -p "$OUTPUT_DIR"

docker run --rm \
    --privileged \
    -v "$OUTPUT_DIR:/output" \
    -v "$REPO_ROOT/config:/live-iso/config:ro" \
    live-iso-builder \
    --output-dir /output

echo ""
echo "Build complete!"
ls -la "$OUTPUT_DIR"/*.iso 2>/dev/null || echo "No ISO found"
