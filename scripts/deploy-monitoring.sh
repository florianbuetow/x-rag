#!/bin/bash
set -euo pipefail

NAMESPACE="rag-system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

echo "=============================================="
echo "  Deploying Monitoring Stack"
echo "=============================================="

# Deploy Prometheus
echo ""
echo "[1/2] Deploying Prometheus..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/prometheus.yaml" -n ${NAMESPACE}
echo "Waiting for Prometheus to be ready..."
kubectl wait --for=condition=Ready pod -l app=prometheus -n ${NAMESPACE} --timeout=120s
echo "✓ Prometheus ready"

# Deploy Grafana
echo ""
echo "[2/2] Deploying Grafana..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/grafana.yaml" -n ${NAMESPACE}
echo "Waiting for Grafana to be ready..."
kubectl wait --for=condition=Ready pod -l app=grafana -n ${NAMESPACE} --timeout=120s
echo "✓ Grafana ready"

echo ""
echo "=============================================="
echo "  Monitoring Deployment Complete!"
echo "=============================================="
echo ""
echo "Access points:"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000 (admin/admin)"
echo ""
echo "Verify with: kubectl get pods -n ${NAMESPACE} -l 'app in (prometheus,grafana)'"
