#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
HELPERS="${SCRIPT_DIR}/cluster_helper_functions.sh"

# Source helper functions
. "${HELPERS}"

NAMESPACE="${NAMESPACE:-rag-system}"
CLUSTER_NAME="${CLUSTER_NAME:-xrag-k8}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

check_mark="${GREEN}✓${NC}"
cross_mark="${RED}✗${NC}"

echo -e "${BLUE}=============================================="
echo "  X-RAG Platform - System Status"
echo -e "==============================================${NC}"
echo ""

# Check Docker
echo -e "${BLUE}[1/8] Docker Daemon${NC}"
if docker_running; then
    echo -e "  ${check_mark} Docker daemon running"
    docker_version=$(docker version --format '{{.Server.Version}}')
    echo -e "  Version: ${docker_version}"
else
    echo -e "  ${cross_mark} Docker daemon not running"
    exit 1
fi
echo ""

# Check Kind Cluster
echo -e "${BLUE}[2/8] Kind Cluster${NC}"
if cluster_exists; then
    echo -e "  ${check_mark} Cluster '${CLUSTER_NAME}' exists"

    # Check cluster health
    if cluster_running; then
        echo -e "  ${check_mark} Cluster is running"
        nodes=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
        echo -e "  Nodes: ${nodes}"
    else
        echo -e "  ${cross_mark} Cluster is not running"
    fi
else
    echo -e "  ${cross_mark} Cluster '${CLUSTER_NAME}' not found"
    exit 1
fi
echo ""

# Check Registry
echo -e "${BLUE}[3/8] Container Registry${NC}"
if registry_running; then
    echo -e "  ${check_mark} Registry running at localhost:5000"
else
    echo -e "  ${cross_mark} Registry not running"
fi
echo ""

# Check Namespace and Pods
echo -e "${BLUE}[4/8] Kubernetes Pods${NC}"
if namespace_exists; then
    echo -e "  ${check_mark} Namespace '${NAMESPACE}' exists"
    echo ""

    # Get pod status
    pod_status=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null || echo "")

    if [ -z "$pod_status" ]; then
        echo -e "  ${cross_mark} No pods found"
    else
        echo "  Pod Status:"
        echo "$pod_status" | while read line; do
            pod_name=$(echo $line | awk '{print $1}')
            ready=$(echo $line | awk '{print $2}')
            status=$(echo $line | awk '{print $3}')

            # Jobs that complete successfully should show as success
            if [[ "$status" == "Completed" ]] && [[ "$ready" == "0/1" ]]; then
                echo -e "    ${check_mark} ${pod_name} (job completed)"
            elif [[ "$ready" == "1/1" ]] && [[ "$status" == "Running" ]]; then
                echo -e "    ${check_mark} ${pod_name}"
            else
                echo -e "    ${cross_mark} ${pod_name} (${status}, ${ready})"
            fi
        done
    fi
else
    echo -e "  ${cross_mark} Namespace '${NAMESPACE}' not found"
fi
echo ""

# Test Weaviate
echo -e "${BLUE}[5/8] Weaviate (Vector Database)${NC}"
if weaviate_ready; then
    echo -e "  ${check_mark} Weaviate is ready"
    echo -e "  URL: http://localhost:8081"

    # Get version via curl
    weaviate_version=$(curl -s http://localhost:8081/v1/meta 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$weaviate_version" ]; then
        echo -e "  Version: ${weaviate_version}"
    fi
else
    echo -e "  ${cross_mark} Weaviate not accessible"
fi
echo ""

# Test Redis
echo -e "${BLUE}[6/8] Redis (Cache)${NC}"
if redis_ready; then
    echo -e "  ${check_mark} Redis is responding"
    echo -e "  Internal: xrag-redis:6379"
else
    echo -e "  ${cross_mark} Redis not responding"
fi
echo ""

# Test Kafka
echo -e "${BLUE}[7/8] Kafka (Message Queue)${NC}"
if kafka_ready; then
    echo -e "  ${check_mark} Kafka is ready"
    echo -e "  Internal: xrag-kafka:9092"
else
    echo -e "  ${cross_mark} Kafka not ready"
fi
echo ""

# Test MinIO
echo -e "${BLUE}[8/8] MinIO (Object Storage)${NC}"
if minio_ready; then
    echo -e "  ${check_mark} MinIO is ready"
    echo -e "  Internal: xrag-minio:9000"
else
    echo -e "  ${cross_mark} MinIO not ready"
fi
echo ""

# Test Prometheus
echo -e "${BLUE}[Monitoring] Prometheus${NC}"
if prometheus_ready; then
    echo -e "  ${check_mark} Prometheus is healthy"
    echo -e "  URL: http://localhost:9090"

    # Get version via curl
    prom_version=$(curl -s http://localhost:9090/api/v1/status/buildinfo 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$prom_version" ]; then
        echo -e "  Version: ${prom_version}"
    fi
else
    echo -e "  ${cross_mark} Prometheus not accessible"
fi
echo ""

# Test Grafana
echo -e "${BLUE}[Monitoring] Grafana${NC}"
if grafana_ready; then
    echo -e "  ${check_mark} Grafana is accessible"
    echo -e "  URL: http://localhost:3000 (admin/admin)"

    # Get version via curl
    grafana_version=$(curl -s http://localhost:3000/api/health 2>/dev/null | grep version | awk -F'"' '{print $4}')
    if [ -n "$grafana_version" ]; then
        echo -e "  Version: ${grafana_version}"
    fi
else
    echo -e "  ${cross_mark} Grafana not accessible"
fi
echo ""

# Test Kubernetes Dashboard
echo -e "${BLUE}[Monitoring] Kubernetes Dashboard${NC}"
if dashboard_ready; then
    echo -e "  ${check_mark} Dashboard is running"
    echo -e "  URL: https://localhost:8443"
else
    echo -e "  ${cross_mark} Dashboard not ready"
fi
echo ""

# Test Search UI
echo -e "${BLUE}[Application] Search UI${NC}"
if search_ui_ready; then
    echo -e "  ${check_mark} Search UI is accessible"
    echo -e "  URL: http://localhost:8080"

    # Check if fully ready
    if search_ui_fully_ready; then
        echo -e "  Status: Ready"
    fi
else
    echo -e "  ${cross_mark} Search UI not accessible"
fi
echo ""

# Test Ingestion API
echo -e "${BLUE}[Application] Ingestion API${NC}"
if ingestion_api_ready; then
    echo -e "  ${check_mark} Ingestion API is accessible"
    echo -e "  URL: http://localhost:8082"
    echo -e "  Docs: http://localhost:8082/docs"

    # Check if fully ready
    if ingestion_api_fully_ready; then
        echo -e "  Status: Ready"
    fi
else
    echo -e "  ${cross_mark} Ingestion API not accessible"
fi
echo ""

# Summary
echo -e "${BLUE}=============================================="
echo "  Summary"
echo -e "==============================================${NC}"
echo ""

# Count ready pods (include both Running and Completed)
total_pods=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | wc -l | tr -d ' ')
running_pods=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | { grep "1/1.*Running" || true; } | wc -l | tr -d ' ')
completed_pods=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | { grep "0/1.*Completed" || true; } | wc -l | tr -d ' ')
ready_pods=$((running_pods + completed_pods))

if [ "$total_pods" -gt 0 ]; then
    echo -e "  Pods: ${ready_pods}/${total_pods} ready"
else
    echo -e "  Pods: No pods deployed"
fi

# Overall status
if [ "$ready_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ]; then
    echo -e "  Status: ${GREEN}All systems operational${NC}"
else
    echo -e "  Status: ${YELLOW}Some services are not ready${NC}"
fi
