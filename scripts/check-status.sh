#!/bin/bash
set -euo pipefail

NAMESPACE="rag-system"
CLUSTER_NAME="xrag-k8"

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
if docker info &>/dev/null; then
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
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo -e "  ${check_mark} Cluster '${CLUSTER_NAME}' exists"

    # Check cluster health
    if kubectl cluster-info --context "kind-${CLUSTER_NAME}" &>/dev/null; then
        echo -e "  ${check_mark} Cluster is healthy"
        nodes=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
        echo -e "  Nodes: ${nodes}"
    else
        echo -e "  ${cross_mark} Cluster is unhealthy"
    fi
else
    echo -e "  ${cross_mark} Cluster '${CLUSTER_NAME}' not found"
    echo -e "  Run: make setup"
    exit 1
fi
echo ""

# Check Registry
echo -e "${BLUE}[3/8] Container Registry${NC}"
if docker ps --format '{{.Names}}' | grep -q "^xrag-k8-kind-registry$"; then
    echo -e "  ${check_mark} Registry running at localhost:5000"
else
    echo -e "  ${cross_mark} Registry not running"
fi
echo ""

# Check Namespace and Pods
echo -e "${BLUE}[4/8] Kubernetes Pods${NC}"
if kubectl get namespace ${NAMESPACE} &>/dev/null; then
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

            if [[ "$ready" == "1/1" ]] && [[ "$status" == "Running" ]]; then
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
if curl -s -f http://localhost:8081/v1/.well-known/ready &>/dev/null; then
    echo -e "  ${check_mark} Weaviate is ready"
    echo -e "  Endpoint: http://localhost:8081"
else
    echo -e "  ${cross_mark} Weaviate not accessible"
fi
echo ""

# Test Redis
echo -e "${BLUE}[6/8] Redis (Cache)${NC}"
if kubectl exec -n ${NAMESPACE} xrag-redis-0 -- redis-cli ping &>/dev/null; then
    redis_response=$(kubectl exec -n ${NAMESPACE} xrag-redis-0 -- redis-cli ping 2>/dev/null || echo "")
    if [[ "$redis_response" == "PONG" ]]; then
        echo -e "  ${check_mark} Redis is responding"
        echo -e "  Internal: xrag-redis:6379"
    else
        echo -e "  ${cross_mark} Redis not responding"
    fi
else
    echo -e "  ${cross_mark} Redis pod not accessible"
fi
echo ""

# Test Kafka
echo -e "${BLUE}[7/8] Kafka (Message Queue)${NC}"
if kubectl get pod xrag-kafka-0 -n ${NAMESPACE} &>/dev/null; then
    kafka_ready=$(kubectl get pod xrag-kafka-0 -n ${NAMESPACE} -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [[ "$kafka_ready" == "True" ]]; then
        echo -e "  ${check_mark} Kafka is ready"
        echo -e "  Internal: xrag-kafka:9092"
    else
        echo -e "  ${cross_mark} Kafka not ready"
    fi
else
    echo -e "  ${cross_mark} Kafka pod not found"
fi
echo ""

# Test MinIO
echo -e "${BLUE}[8/8] MinIO (Object Storage)${NC}"
if kubectl get pod xrag-minio-0 -n ${NAMESPACE} &>/dev/null; then
    minio_ready=$(kubectl get pod xrag-minio-0 -n ${NAMESPACE} -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [[ "$minio_ready" == "True" ]]; then
        echo -e "  ${check_mark} MinIO is ready"
        echo -e "  Internal: xrag-minio:9000"
    else
        echo -e "  ${cross_mark} MinIO not ready"
    fi
else
    echo -e "  ${cross_mark} MinIO pod not found"
fi
echo ""

# Test Prometheus
echo -e "${BLUE}[Monitoring] Prometheus${NC}"
if curl -s -f http://localhost:9090/-/healthy &>/dev/null; then
    echo -e "  ${check_mark} Prometheus is healthy"
    echo -e "  Endpoint: http://localhost:9090"
else
    echo -e "  ${cross_mark} Prometheus not accessible"
fi
echo ""

# Test Grafana
echo -e "${BLUE}[Monitoring] Grafana${NC}"
if curl -s -f http://localhost:3000 &>/dev/null; then
    echo -e "  ${check_mark} Grafana is accessible"
    echo -e "  Endpoint: http://localhost:3000 (admin/admin)"
else
    echo -e "  ${cross_mark} Grafana not accessible"
fi
echo ""

# Summary
echo -e "${BLUE}=============================================="
echo "  Summary"
echo -e "==============================================${NC}"
echo ""

# Count ready pods
total_pods=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | wc -l | tr -d ' ')
ready_pods=$(kubectl get pods -n ${NAMESPACE} --no-headers 2>/dev/null | grep "1/1.*Running" | wc -l | tr -d ' ')

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

echo ""
echo "For detailed pod status, run: kubectl get pods -n ${NAMESPACE}"
echo "For logs, run: make logs-<service-name>"
