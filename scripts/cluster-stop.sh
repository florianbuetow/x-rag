#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
HELPERS="${PROJECT_ROOT}/scripts/cluster_helper_functions.sh"

cd "${PROJECT_ROOT}"

# Source helper functions
. "${HELPERS}"

CLUSTER_NAME="xrag-k8"
REGISTRY_NAME="xrag-k8-kind-registry"

# Check Docker is running
if ! docker_running; then
    echo "ERROR: Docker daemon is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

deleted=0

# Stop cluster if it exists (use helper function)
if cluster_exists; then
    echo "  Deleting cluster ${CLUSTER_NAME}..."
    kind delete cluster --name "${CLUSTER_NAME}" 2>/dev/null && deleted=1 || echo "  Warning: Failed to delete cluster"
else
    echo "  No cluster found"
fi

# Stop registry if it exists (use helper function)
if registry_exists; then
    echo "  Removing registry ${REGISTRY_NAME}..."
    docker rm -f "${REGISTRY_NAME}" 2>/dev/null && deleted=1 || echo "  Warning: Failed to remove registry"
else
    echo "  No registry found"
fi

if [ $deleted -eq 0 ]; then
    echo "  Nothing to stop"
fi

echo "✓ Done"
