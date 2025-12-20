#!/bin/bash
set -euo pipefail

NAMESPACE="rag-system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
DASHBOARDS_DIR="${PROJECT_ROOT}/infra/k8s/monitoring/grafana-dashboards"

echo "=============================================="
echo "  Deploying Monitoring Stack"
echo "=============================================="

# Deploy Prometheus
echo ""
echo "[1/6] Deploying Prometheus..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/prometheus.yaml" -n ${NAMESPACE}
echo "Waiting for Prometheus to be ready..."
kubectl wait --for=condition=Ready pod -l app=xrag-prometheus -n ${NAMESPACE} --timeout=120s
echo "Prometheus ready"

# Deploy Tempo (distributed tracing)
echo ""
echo "[2/6] Deploying Tempo..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/tempo.yaml" -n ${NAMESPACE}
echo "Waiting for Tempo to be ready..."
kubectl wait --for=condition=Ready pod -l app=xrag-tempo -n ${NAMESPACE} --timeout=120s
echo "Tempo ready"

# Deploy Grafana provisioning ConfigMaps
echo ""
echo "[3/6] Setting up Grafana provisioning..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/grafana-provisioning.yaml" -n ${NAMESPACE}
echo "Grafana provisioning ConfigMaps created"

# Generate dashboard ConfigMap from JSON files
if [[ -d "$DASHBOARDS_DIR" ]] && [[ -n "$(ls -A "$DASHBOARDS_DIR"/*.json 2>/dev/null)" ]]; then
    echo "Creating dashboards ConfigMap from JSON files..."
    kubectl create configmap grafana-dashboards \
        --namespace="${NAMESPACE}" \
        --from-file="$DASHBOARDS_DIR" \
        --dry-run=client -o yaml | kubectl apply -f -
    echo "Dashboard ConfigMap created"
else
    echo "Warning: No dashboard JSON files found in $DASHBOARDS_DIR"
    echo "Creating empty dashboards ConfigMap..."
    kubectl create configmap grafana-dashboards \
        --namespace="${NAMESPACE}" \
        --dry-run=client -o yaml | kubectl apply -f -
fi

# Deploy Grafana
echo ""
echo "[4/6] Deploying Grafana..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/grafana.yaml" -n ${NAMESPACE}
echo "Waiting for Grafana to be ready..."
kubectl wait --for=condition=Ready pod -l app=xrag-grafana -n ${NAMESPACE} --timeout=120s
echo "Grafana ready"

# Deploy Grafana Alloy (OpenTelemetry collector)
echo ""
echo "[5/6] Deploying Grafana Alloy..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/alloy-config.yaml" -n ${NAMESPACE}
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/alloy.yaml" -n ${NAMESPACE}
echo "Waiting for Alloy to be ready..."
kubectl wait --for=condition=Ready pod -l app=xrag-alloy -n ${NAMESPACE} --timeout=120s
echo "Grafana Alloy ready"

# Deploy Kubernetes Dashboard
echo ""
echo "[6/6] Deploying Kubernetes Dashboard..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/monitoring/dashboard.yaml"
echo "Waiting for Dashboard to be ready..."
kubectl wait --for=condition=Ready pod -l k8s-app=kubernetes-dashboard -n kubernetes-dashboard --timeout=120s 2>/dev/null || true
echo "Kubernetes Dashboard ready"

echo ""
echo "=============================================="
echo "  Monitoring Deployment Complete!"
echo "=============================================="
echo ""
echo "Access points:"
echo "  Prometheus:     http://localhost:9090"
echo "  Tempo:          http://localhost:3200 (traces)"
echo "  Grafana:        http://localhost:3000 (admin/admin)"
echo "  Alloy:          http://localhost:12345 (OTLP receiver)"
echo "  K8s Dashboard:  https://localhost:8443 (token required)"
echo ""
echo "Grafana dashboards are auto-provisioned in the 'X-RAG' folder."
echo "To update dashboards:"
echo "  1. Edit JSON files in infra/k8s/monitoring/grafana-dashboards/"
echo "  2. Run: ./scripts/generate-grafana-dashboards-configmap.sh"
echo ""
echo "Get dashboard token: make show-k8-dashboard-token"
echo ""
echo "Verify with: kubectl get pods -n ${NAMESPACE} -l 'app in (xrag-prometheus,xrag-tempo,xrag-grafana)'"
