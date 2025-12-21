#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

cd "${PROJECT_ROOT}"

echo "Deleting Kind cluster images..."

deleted=0

# Delete registry image
if docker image inspect registry:2 &>/dev/null; then
    echo "  Deleting registry:2"
    docker rmi -f registry:2 2>/dev/null || echo "  Warning: Failed to delete registry:2"
    deleted=1
fi

# Delete Kind node image
if docker image inspect kindest/node &>/dev/null; then
    echo "  Deleting kindest/node"
    docker rmi -f kindest/node 2>/dev/null || echo "  Warning: Failed to delete kindest/node"
    deleted=1
fi

if [ $deleted -eq 0 ]; then
    echo "  No Kind cluster images found"
fi

echo "✓ Done"
