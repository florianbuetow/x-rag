#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
NAMESPACE="rag-system"

cd "${PROJECT_ROOT}"

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# Set defaults for required variables
: "${OPENAI_API_BASE:=https://api.openai.com/v1}"
: "${OPENAI_MODEL:=gpt-4o-mini}"
: "${OPENAI_EMBEDDING_MODEL:=text-embedding-3-small}"
: "${OPENAI_API_KEY:=sk-your-key-here}"

export OPENAI_API_BASE OPENAI_MODEL OPENAI_EMBEDDING_MODEL OPENAI_API_KEY

echo "Deploying application services to namespace: ${NAMESPACE}..."
echo ""

# List of services to deploy
SERVICES=(
    "embedding-service"
    "ingestion-api"
    "indexer"
    "search-service"
    "search-ui"
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

    # Apply manifests with environment variable substitution
    for manifest in "${manifest_dir}"/*.yaml; do
        envsubst '${OPENAI_API_BASE} ${OPENAI_MODEL} ${OPENAI_EMBEDDING_MODEL} ${OPENAI_API_KEY}' < "${manifest}" | kubectl apply -n "${NAMESPACE}" -f -
    done

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
echo "Run 'make cluster-status' to check service health"
