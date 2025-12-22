#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
REGISTRY="localhost:5000"

cd "${PROJECT_ROOT}"

echo "Building Docker images..."
echo ""

# Get list of services from central script
SERVICES=($(${SCRIPT_DIR}/list-services.sh))

for service in "${SERVICES[@]}"; do
    dockerfile="infra/docker/Dockerfile.${service}"
    image_name="${REGISTRY}/${service}:latest"

    echo "=== Building ${service} ==="

    echo "  Building ${image_name}..."
    docker build --no-cache -t "${image_name}" -f "${dockerfile}" .

    echo "  ✓ ${service} built"
    echo ""
done

echo "✓ All images built successfully"
