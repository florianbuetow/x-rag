#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
REGISTRY="localhost:5000"

cd "${PROJECT_ROOT}"

echo "Deleting application Docker images..."

# Get list of services from central script
SERVICES=($(${SCRIPT_DIR}/list-services.sh))

deleted=0
for service in "${SERVICES[@]}"; do
    image_name="${REGISTRY}/${service}:latest"

    if docker image inspect "${image_name}" &>/dev/null; then
        echo "  Deleting ${image_name}"
        docker rmi -f "${image_name}" 2>/dev/null || echo "  Warning: Failed to delete ${image_name}"
        deleted=1
    fi
done

if [ $deleted -eq 0 ]; then
    echo "  No application images found"
fi

echo "✓ Done"
