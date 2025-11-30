#!/bin/bash
set -euo pipefail

NAMESPACE="rag-system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

echo "=============================================="
echo "  Deploying Infrastructure Services"
echo "=============================================="

# Deploy services in dependency order

# 1. Redis (fast startup)
echo ""
echo "[1/4] Deploying Redis..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/redis/" -n ${NAMESPACE}
echo "Waiting for Redis to be ready..."
kubectl wait --for=condition=Ready pod -l app=redis -n ${NAMESPACE} --timeout=120s
echo "✓ Redis ready"

# 2. MinIO (medium startup)
echo ""
echo "[2/4] Deploying MinIO..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/minio/" -n ${NAMESPACE}
echo "Waiting for MinIO to be ready..."
kubectl wait --for=condition=Ready pod -l app=minio -n ${NAMESPACE} --timeout=120s
echo "✓ MinIO ready"

# 3. Kafka (slow startup)
echo ""
echo "[3/4] Deploying Kafka..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/kafka/" -n ${NAMESPACE}
echo "Waiting for Kafka to be ready..."
kubectl wait --for=condition=Ready pod -l app=kafka -n ${NAMESPACE} --timeout=240s
echo "✓ Kafka ready"

# 4. Weaviate (slow startup, requires initialization)
echo ""
echo "[4/4] Deploying Weaviate..."
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/weaviate/weaviate.yaml" -n ${NAMESPACE}
echo "Waiting for Weaviate to be ready..."
kubectl wait --for=condition=Ready pod -l app=weaviate -n ${NAMESPACE} --timeout=240s
echo "✓ Weaviate ready"

# Initialize Weaviate schema
echo ""
echo "Initializing Weaviate schema..."
# Delete existing job if present
kubectl delete job weaviate-schema-init -n ${NAMESPACE} --ignore-not-found
# Create schema initialization job
kubectl apply -f "${PROJECT_ROOT}/infra/k8s/weaviate/schema-init.yaml" -n ${NAMESPACE}
# Wait for job to complete
kubectl wait --for=condition=Complete job/weaviate-schema-init -n ${NAMESPACE} --timeout=120s
echo "✓ Weaviate schema initialized"

echo ""
echo "=============================================="
echo "  Infrastructure Deployment Complete!"
echo "=============================================="
echo ""
echo "Services:"
echo "  ✓ Redis     - redis:6379"
echo "  ✓ MinIO     - minio:9000"
echo "  ✓ Kafka     - kafka:9092"
echo "  ✓ Weaviate  - weaviate:8080 (also http://localhost:8081)"
echo ""
echo "Verify with: kubectl get pods -n ${NAMESPACE}"
