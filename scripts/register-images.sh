#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
REGISTRY="localhost:5000"

cd "${PROJECT_ROOT}"

echo "=============================================="
echo "  Registering Docker Images with Registry"
echo "=============================================="
echo ""

# Get list of services from central script
SERVICES=($(${SCRIPT_DIR}/list-services.sh))

# Validate all images exist before registering any
echo "Validating images..."
for service in "${SERVICES[@]}"; do
    image_name="${REGISTRY}/${service}:latest"

    if ! docker image inspect "${image_name}" > /dev/null 2>&1; then
        echo "  ✗ Image not found: ${image_name}"
        echo ""
        echo "ERROR: Run 'make apps-build' to build images first"
        exit 1
    fi

    echo "  ✓ Found ${image_name}"
done

echo ""
echo "Registering images with registry..."
echo ""

# Register all images with registry
for service in "${SERVICES[@]}"; do
    image_name="${REGISTRY}/${service}:latest"

    echo "=== Registering ${service} ==="
    docker push "${image_name}" --quiet
    echo "  ✓ ${service} registered"
    echo ""
done

echo "=============================================="
echo "  Registration Complete!"
echo "=============================================="
echo ""
echo "All images available at ${REGISTRY}"
