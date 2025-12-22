#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
NAMESPACE="rag-system"
REGISTRY="localhost:5000"

cd "${PROJECT_ROOT}"

echo "=============================================="
echo "  Deploying Application Services to: {$NAMESPACE}"
echo "=============================================="

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

# Derive OTEL_METRICS_ENABLED from OBSERVABILITY_ENABLED
if [[ "${OBSERVABILITY_ENABLED:-true}" == "false" ]]; then
    OTEL_METRICS_ENABLED="false"
else
    OTEL_METRICS_ENABLED="true"
fi

export OPENAI_API_BASE OPENAI_MODEL OPENAI_EMBEDDING_MODEL OPENAI_API_KEY OTEL_METRICS_ENABLED

echo "Deploying application services to namespace: ${NAMESPACE}..."
echo ""

# Get list of services from central script
SERVICES=($(${SCRIPT_DIR}/list-services.sh))

# Optional validation with helpful warning
echo "Validating images..."
for service in "${SERVICES[@]}"; do
    image_name="${REGISTRY}/${service}:latest"

    if ! docker image inspect "${image_name}" > /dev/null 2>&1; then
        echo "  ⚠️  Warning: Image not found locally: ${image_name}"
        echo "  This may fail if not registered with registry."
        echo "  Run 'make apps-register' to register images first."
        echo ""
    else
        echo "  ✓ Found ${image_name}"
    fi
done

echo ""
echo "Deploying Kubernetes manifests..."
echo ""

# Deploy to Kubernetes
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
        envsubst '${OPENAI_API_BASE} ${OPENAI_MODEL} ${OPENAI_EMBEDDING_MODEL} ${OPENAI_API_KEY} ${OTEL_METRICS_ENABLED}' < "${manifest}" | kubectl apply -n "${NAMESPACE}" -f -
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
echo "=============================================="
echo "  Deployment Complete!"
echo "=============================================="
echo ""
echo "Run 'make cluster-status' to check service health"
