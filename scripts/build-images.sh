#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
REGISTRY="localhost:5000"

cd "${PROJECT_ROOT}"

echo "Building Docker images and pushing to ${REGISTRY}..."
echo ""

# List of services to build
SERVICES=(
    "embedding-service"
    "ingestion-api"
    "indexer"
    "search-service"
)

for service in "${SERVICES[@]}"; do
    echo "=== Building ${service} ==="

    dockerfile="infra/docker/Dockerfile.${service}"
    image_name="${REGISTRY}/${service}:latest"

    if [ ! -f "${dockerfile}" ]; then
        echo "  ⚠️  Dockerfile not found: ${dockerfile}"
        echo "  Skipping..."
        echo ""
        continue
    fi

    echo "  Building ${image_name}..."
    docker build --no-cache -t "${image_name}" -f "${dockerfile}" . --quiet

    echo "  Pushing ${image_name}..."
    docker push "${image_name}" --quiet

    echo "  ✓ ${service} built and pushed"
    echo ""
done

echo "✓ All images built and pushed successfully"
