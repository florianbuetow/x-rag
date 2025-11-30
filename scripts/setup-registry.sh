#!/bin/bash
set -euo pipefail

REG_NAME="xrag-k8-kind-registry"
REG_PORT="5000"

echo "=============================================="
echo "  Setting Up Local Container Registry"
echo "=============================================="

# Check if registry is already running
if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" = "true" ]; then
    echo "Registry '${REG_NAME}' is already running at localhost:${REG_PORT}"
    exit 0
fi

# Remove any stopped registry container
docker rm -f "${REG_NAME}" 2>/dev/null || true

# Create and start registry
echo "Creating registry container..."
docker run -d --restart=always \
    -p "127.0.0.1:${REG_PORT}:5000" \
    --name "${REG_NAME}" \
    registry:2

# Connect registry to Kind network
echo "Connecting registry to Kind network..."
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${REG_NAME}")" = 'null' ]; then
    docker network connect "kind" "${REG_NAME}"
fi

# Create ConfigMap to inform Kind about the registry
echo "Configuring registry in cluster..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REG_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

echo ""
echo "✓ Container registry ready at localhost:${REG_PORT}"
