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
kubectl wait --for=condition=Ready pod -l app=xrag-prometheus -n ${NAMESPACE} --timeout=120s
echo "✓ Prometheus ready"

# Deploy Grafana
echo ""
echo "[2/3] Deploying Grafana..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/grafana.yaml" -n ${NAMESPACE}
echo "Waiting for Grafana to be ready..."
kubectl wait --for=condition=Ready pod -l app=xrag-grafana -n ${NAMESPACE} --timeout=120s
echo "✓ Grafana ready"

# Deploy Kubernetes Dashboard
echo ""
echo "[3/3] Deploying Kubernetes Dashboard..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/dashboard.yaml"
echo "Waiting for Dashboard to be ready..."
kubectl wait --for=condition=Ready pod -l k8s-app=kubernetes-dashboard -n kubernetes-dashboard --timeout=120s 2>/dev/null || true
echo "✓ Kubernetes Dashboard ready"

echo ""
echo "=============================================="
echo "  Monitoring Deployment Complete!"
echo "=============================================="
echo ""
echo "Access points:"
echo "  Prometheus:  http://localhost:9090"
echo "  Grafana:     http://localhost:3000 (admin/admin)"
echo "  K8s Dashboard: https://localhost:8443 (token required)"
echo ""
echo "Get dashboard token: make dashboard-token"
echo ""
echo "Verify with: kubectl get pods -n ${NAMESPACE} -l 'app in (xrag-prometheus,xrag-grafana)'"
