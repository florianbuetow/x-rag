#!/bin/bash
set -euo pipefail

CLUSTER_NAME="xrag"
NAMESPACE="rag-system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

echo "=============================================="
echo "  Creating Kind Cluster: ${CLUSTER_NAME}"
echo "=============================================="

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Cluster '${CLUSTER_NAME}' already exists"

    # Verify cluster is healthy
    if kubectl cluster-info --context "kind-${CLUSTER_NAME}" &>/dev/null; then
        echo "Cluster is healthy, reusing existing cluster"

        # Ensure namespace exists
        kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f - &>/dev/null || true
        echo "✓ Cluster ready"
        exit 0
    else
        echo "Existing cluster is unhealthy, deleting and recreating..."
        kind delete cluster --name "${CLUSTER_NAME}"
    fi
fi

# Create data directory
mkdir -p "${PROJECT_ROOT}/data/storage"

# Create cluster
echo "Creating cluster with Kind..."
cd "${PROJECT_ROOT}"
kind create cluster --config infra/kind/cluster-config.yaml --wait 120s

# Create namespace
echo "Creating namespace '${NAMESPACE}'..."
kubectl create namespace ${NAMESPACE}

echo ""
echo "✓ Cluster '${CLUSTER_NAME}' created successfully"
echo "  Nodes: $(kubectl get nodes --no-headers | wc -l | tr -d ' ')"
echo "  Namespace: ${NAMESPACE}"
