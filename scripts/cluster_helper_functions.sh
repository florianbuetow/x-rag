#!/bin/bash
# Cluster state helper functions - each function is completely independent

CLUSTER_NAME="${CLUSTER_NAME:-xrag-k8}"
REGISTRY_NAME="${REGISTRY_NAME:-xrag-k8-kind-registry}"
NAMESPACE="${NAMESPACE:-rag-system}"

# ==================== Core Infrastructure ====================

# Check if Docker daemon is running
docker_running() {
    docker info &>/dev/null
    return $?
}

# Check if Docker can perform write operations (detect I/O errors)
docker_healthy() {
    # Try to create and remove a test volume to verify write capability
    local test_vol="cluster-health-test-$$"
    local output

    output=$(docker volume create "$test_vol" 2>&1)
    local create_status=$?

    if [ $create_status -ne 0 ]; then
        # Check if error is I/O related
        if echo "$output" | grep -qi "input/output error"; then
            return 1
        fi
        # Other errors might be acceptable (e.g., already exists)
        return $create_status
    fi

    # Clean up test volume
    docker volume rm "$test_vol" &>/dev/null
    return 0
}

# Check if Kind cluster exists (checks kind directly)
cluster_exists() {
    kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"
    return $?
}

# Check if cluster API is responding (checks kubectl directly)
cluster_running() {
    kubectl cluster-info --context "kind-${CLUSTER_NAME}" &>/dev/null
    return $?
}

# Check if registry container exists (checks docker directly)
registry_exists() {
    docker ps -a --filter "name=^${REGISTRY_NAME}$" --format '{{.Names}}' 2>/dev/null | grep -q "^${REGISTRY_NAME}$"
    return $?
}

# Check if registry is accessible (checks HTTP endpoint directly)
registry_running() {
    curl -sf http://localhost:5000/v2/_catalog &>/dev/null
    return $?
}

# Check if namespace exists
namespace_exists() {
    kubectl get namespace "${NAMESPACE}" &>/dev/null
    return $?
}

# ==================== Docker Images ====================

# Check if app Docker images exist locally
app_images_exist() {
    local missing=0
    for dockerfile in infra/docker/Dockerfile.*; do
        if [ -f "$dockerfile" ]; then
            service=$(basename "$dockerfile" | sed 's/Dockerfile\.//')
            if ! docker image inspect "localhost:5000/${service}:latest" &>/dev/null; then
                missing=1
                break
            fi
        fi
    done
    return $missing
}

# ==================== Infrastructure Services ====================

# Check if all infrastructure pods are ready
infrastructure_ready() {
    local ready_count
    ready_count=$(kubectl get pods -n "${NAMESPACE}" \
        -l 'app in (xrag-redis,xrag-minio,xrag-kafka,xrag-weaviate)' \
        -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null \
        | grep -o "True" | wc -l | tr -d ' ')

    # Should have 4 infrastructure pods ready
    [ "$ready_count" -eq 4 ]
    return $?
}

# Check if Weaviate is accessible
weaviate_ready() {
    curl -sf http://localhost:8081/v1/.well-known/ready &>/dev/null
    return $?
}

# Check if Redis is responding
redis_ready() {
    kubectl exec -n "${NAMESPACE}" xrag-redis-0 -- redis-cli ping &>/dev/null
    return $?
}

# Check if Kafka pod is ready
kafka_ready() {
    local ready_status
    ready_status=$(kubectl get pod xrag-kafka-0 -n "${NAMESPACE}" \
        -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [ "$ready_status" = "True" ]
    return $?
}

# Check if MinIO pod is ready
minio_ready() {
    local ready_status
    ready_status=$(kubectl get pod xrag-minio-0 -n "${NAMESPACE}" \
        -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [ "$ready_status" = "True" ]
    return $?
}

# Check if infrastructure resources exist (deployments/statefulsets)
infrastructure_exists() {
    local redis_exists=$(kubectl get statefulset xrag-redis -n "${NAMESPACE}" &>/dev/null && echo "1" || echo "0")
    local minio_exists=$(kubectl get statefulset xrag-minio -n "${NAMESPACE}" &>/dev/null && echo "1" || echo "0")
    local kafka_exists=$(kubectl get statefulset xrag-kafka -n "${NAMESPACE}" &>/dev/null && echo "1" || echo "0")
    local weaviate_exists=$(kubectl get statefulset xrag-weaviate -n "${NAMESPACE}" &>/dev/null && echo "1" || echo "0")
    local total=$((redis_exists + minio_exists + kafka_exists + weaviate_exists))
    [ "$total" -eq 4 ]
    return $?
}

# ==================== Monitoring Services ====================

# Check if all monitoring pods are ready
monitoring_ready() {
    local ready_count
    ready_count=$(kubectl get pods -n "${NAMESPACE}" \
        -l 'app in (xrag-prometheus,xrag-grafana,xrag-tempo)' \
        -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null \
        | grep -o "True" | wc -l | tr -d ' ')

    # Should have 3 monitoring pods ready
    [ "$ready_count" -eq 3 ]
    return $?
}

# Check if Prometheus is accessible
prometheus_ready() {
    curl -sf http://localhost:9090/-/healthy &>/dev/null
    return $?
}

# Check if Grafana is accessible
# Check if Grafana is accessible
grafana_ready() {
    curl -sf http://localhost:3000 &>/dev/null
    return $?
}

# Check if monitoring resources exist (deployments/statefulsets)
monitoring_exists() {
    local prometheus_exists=$(kubectl get deployment xrag-prometheus -n "${NAMESPACE}" &>/dev/null && echo "1" || echo "0")
    local grafana_exists=$(kubectl get deployment xrag-grafana -n "${NAMESPACE}" &>/dev/null && echo "1" || echo "0")
    local tempo_exists=$(kubectl get statefulset xrag-tempo -n "${NAMESPACE}" &>/dev/null && echo "1" || echo "0")
    local total=$((prometheus_exists + grafana_exists + tempo_exists))
    [ "$total" -eq 3 ]
    return $?
}

# Check if Tempo is accessible
tempo_ready() {
    kubectl get pod -n "${NAMESPACE}" -l app=xrag-tempo \
        -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null \
        | grep -q "True"
    return $?
}

# ==================== Application Services ====================

# Check if all application pods are ready
apps_ready() {
    local ready_count
    ready_count=$(kubectl get pods -n "${NAMESPACE}" \
        -l 'app in (embedding-service,indexer,ingestion-api,search-service,search-ui)' \
        -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null \
        | grep -o "True" | wc -l | tr -d ' ')

    # Should have 5 app pods ready
    [ "$ready_count" -eq 5 ]
    return $?
}

# Check if Search UI is accessible
search_ui_ready() {
    curl -sf http://localhost:8080/health/live &>/dev/null
    return $?
}

# Check if Ingestion API is accessible
ingestion_api_ready() {
    curl -sf http://localhost:8082/health/live &>/dev/null
    return $?
}

# Check if Search UI is fully ready (both live and ready endpoints)
search_ui_fully_ready() {
    curl -sf http://localhost:8080/health/live &>/dev/null && \
    curl -sf http://localhost:8080/health/ready &>/dev/null
    return $?
}

# Check if Ingestion API is fully ready (both live and ready endpoints)
ingestion_api_fully_ready() {
    curl -sf http://localhost:8082/health/live &>/dev/null && \
    curl -sf http://localhost:8082/health/ready &>/dev/null
    return $?
}

# Check if Embedding Service pod is ready
embedding_service_ready() {
    local ready_status
    ready_status=$(kubectl get pod -n "${NAMESPACE}" -l app=embedding-service \
        -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [ "$ready_status" = "True" ]
    return $?
}

# Check if Search Service pod is ready
search_service_ready() {
    local ready_status
    ready_status=$(kubectl get pod -n "${NAMESPACE}" -l app=search-service \
        -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [ "$ready_status" = "True" ]
    return $?
}

# Check if Indexer pod is ready
indexer_ready() {
    local ready_status
    ready_status=$(kubectl get pod -n "${NAMESPACE}" -l app=indexer \
        -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [ "$ready_status" = "True" ]
    return $?
}

# Check if Kubernetes Dashboard is ready
dashboard_ready() {
    local ready_status
    ready_status=$(kubectl get pod -n kubernetes-dashboard -l k8s-app=kubernetes-dashboard \
        -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [ "$ready_status" = "True" ]
    return $?
}

# Export all functions
export -f docker_running
export -f docker_healthy
export -f cluster_exists
export -f cluster_running
export -f registry_exists
export -f registry_running
export -f namespace_exists
export -f app_images_exist
export -f infrastructure_ready
export -f infrastructure_exists
export -f weaviate_ready
export -f redis_ready
export -f kafka_ready
export -f minio_ready
export -f monitoring_ready
export -f monitoring_exists
export -f prometheus_ready
export -f grafana_ready
export -f tempo_ready
export -f apps_ready
export -f search_ui_ready
export -f ingestion_api_ready
export -f search_ui_fully_ready
export -f ingestion_api_fully_ready
export -f embedding_service_ready
export -f search_service_ready
export -f indexer_ready
export -f dashboard_ready

# ==================== Wait Functions ====================

# Wait for infrastructure services to be ready (with timeout)
wait_for_infrastructure() {
    local timeout=${1:-60}
    local elapsed=0
    local interval=2

    echo "Waiting for infrastructure services to be ready (timeout: ${timeout}s)..."
    while [ $elapsed -lt $timeout ]; do
        if infrastructure_ready; then
            echo "✓ Infrastructure services are ready"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        echo "  Still waiting... (${elapsed}/${timeout}s)"
    done

    echo "✗ Timeout: Infrastructure services did not become ready within ${timeout}s"
    return 1
}

# Wait for monitoring services to be ready (with timeout)
wait_for_monitoring() {
    local timeout=${1:-60}
    local elapsed=0
    local interval=2

    echo "Waiting for monitoring services to be ready (timeout: ${timeout}s)..."
    while [ $elapsed -lt $timeout ]; do
        if monitoring_ready; then
            echo "✓ Monitoring services are ready"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        echo "  Still waiting... (${elapsed}/${timeout}s)"
    done

    echo "✗ Timeout: Monitoring services did not become ready within ${timeout}s"
    return 1
}

# Wait for application services to be ready (with timeout)
wait_for_apps() {
    local timeout=${1:-60}
    local elapsed=0
    local interval=2

    echo "Waiting for application services to be ready (timeout: ${timeout}s)..."
    while [ $elapsed -lt $timeout ]; do
        if apps_ready; then
            echo "✓ Application services are ready"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        echo "  Still waiting... (${elapsed}/${timeout}s)"
    done

    echo "✗ Timeout: Application services did not become ready within ${timeout}s"
    return 1
}

# Export wait functions
export -f wait_for_infrastructure
export -f wait_for_monitoring
export -f wait_for_apps
