#!/bin/bash
# Generate Grafana dashboards ConfigMap from JSON files
#
# This script creates a Kubernetes ConfigMap containing all dashboard JSON files
# from the infra/k8s/monitoring/grafana-dashboards/ directory.
#
# Usage: ./scripts/generate-grafana-dashboards-configmap.sh
#
# The generated ConfigMap is applied to the cluster and the Grafana deployment
# is restarted to pick up the new dashboards.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DASHBOARDS_DIR="$PROJECT_ROOT/infra/k8s/monitoring/grafana-dashboards"
NAMESPACE="rag-system"
CONFIGMAP_NAME="grafana-dashboards"

echo "=== Generating Grafana Dashboards ConfigMap ==="

# Check if dashboards directory exists
if [[ ! -d "$DASHBOARDS_DIR" ]]; then
    echo "Error: Dashboards directory not found: $DASHBOARDS_DIR"
    exit 1
fi

# Check for JSON files
json_files=$(find "$DASHBOARDS_DIR" -name "*.json" -type f 2>/dev/null)
if [[ -z "$json_files" ]]; then
    echo "Error: No JSON dashboard files found in $DASHBOARDS_DIR"
    exit 1
fi

echo "Found dashboard files:"
for f in $json_files; do
    echo "  - $(basename "$f")"
done

# Create ConfigMap using kubectl
echo ""
echo "Creating ConfigMap '$CONFIGMAP_NAME' in namespace '$NAMESPACE'..."

kubectl create configmap "$CONFIGMAP_NAME" \
    --namespace="$NAMESPACE" \
    --from-file="$DASHBOARDS_DIR" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "ConfigMap created successfully."

# Check if Grafana is deployed
if kubectl get deployment xrag-grafana -n "$NAMESPACE" &>/dev/null; then
    echo ""
    echo "Restarting Grafana to pick up new dashboards..."
    kubectl rollout restart deployment/xrag-grafana -n "$NAMESPACE"
    kubectl rollout status deployment/xrag-grafana -n "$NAMESPACE" --timeout=60s
    echo "Grafana restarted successfully."
else
    echo ""
    echo "Note: Grafana deployment not found. Apply the dashboards after deploying Grafana."
fi

echo ""
echo "=== Done ==="
echo ""
echo "Access Grafana at: http://localhost:3000 (after port-forward)"
echo "Default credentials: admin/admin"
echo "Dashboard location: Dashboards > Browse > X-RAG folder"
