#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
NAMESPACE="rag-system"

cd "${PROJECT_ROOT}"

echo "Deploying application services to namespace: ${NAMESPACE}..."
echo ""

# List of services to deploy
SERVICES=(
    "embedding-service"
    "ingestion-api"
)

for service in "${SERVICES[@]}"; do
    manifest_dir="infra/k8s/${service}"

    if [ ! -d "${manifest_dir}" ]; then
        echo "  ⚠️  Manifests not found for ${service}"
        echo "  Skipping..."
        echo ""
        continue
    fi

    echo "=== Deploying ${service} ==="

    # Apply manifests
    kubectl apply -f "${manifest_dir}/" -n "${NAMESPACE}"

    echo "  ✓ ${service} manifests applied"
    echo ""
done

echo "Waiting for deployments to be ready..."
echo ""

# Wait for each deployment
for service in "${SERVICES[@]}"; do
    if kubectl get deployment "${service}" -n "${NAMESPACE}" &>/dev/null; then
        echo "  Waiting for ${service}..."
        kubectl wait --for=condition=Available deployment/"${service}" -n "${NAMESPACE}" --timeout=120s || true
    fi
done

echo ""
echo "✓ Application services deployed successfully"
echo ""
echo "Run 'make status' to check service health"
