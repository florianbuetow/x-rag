#!/bin/bash
# =============================================================================
# Verify OTel Metrics Pipeline
# =============================================================================
# This script verifies that metrics flow correctly through the pipeline:
#   Services -> Alloy (OTLP) -> Prometheus
#
# Tests all services:
#   - search-ui (HTTP)
#   - ingestion-api (HTTP)
#   - search-service (gRPC, triggered via search-ui)
#   - embedding-service (gRPC, triggered via search/indexer)
#   - indexer (Kafka consumer, triggered via ingestion)
#
# Usage: ./scripts/verify-otel-metrics.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

# Load environment variables from .env if it exists
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Check if observability is disabled
if [[ "${OBSERVABILITY_ENABLED:-true}" == "false" ]]; then
    echo "=============================================="
    echo "  OTel Metrics Verification SKIPPED"
    echo "=============================================="
    echo ""
    echo "Observability is disabled (OBSERVABILITY_ENABLED=false)."
    echo "Set OBSERVABILITY_ENABLED=true in .env to enable metrics."
    echo ""
    exit 0
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SEARCH_UI_URL="${SEARCH_UI_URL:-http://localhost:8080}"
INGESTION_URL="${INGESTION_URL:-http://localhost:8082}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
NUM_REQUESTS="${NUM_REQUESTS:-3}"
WAIT_SECONDS="${WAIT_SECONDS:-25}"

# All services to check
SERVICES=("search-ui" "ingestion-api" "search-service" "embedding-service" "indexer")

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}  OTel Metrics Pipeline Verification (All Services)${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""
echo "Configuration:"
echo "  Search UI:      ${SEARCH_UI_URL}"
echo "  Ingestion API:  ${INGESTION_URL}"
echo "  Prometheus:     ${PROMETHEUS_URL}"
echo "  Requests:       ${NUM_REQUESTS}"
echo "  Wait time:      ${WAIT_SECONDS}s"
echo ""

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

get_service_metric_count() {
    local service=$1
    local result
    local query="sum(http_server_duration_milliseconds_count{job=\"${service}\"})"
    result=$(curl -s --get --data-urlencode "query=${query}" "${PROMETHEUS_URL}/api/v1/query" 2>/dev/null)
    echo "${result}" | jq -r '.data.result[0].value[1] // "0"' 2>/dev/null || echo "0"
}

get_total_metric_count() {
    local result
    result=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=sum(http_server_duration_milliseconds_count)" 2>/dev/null)
    echo "${result}" | jq -r '.data.result[0].value[1] // "0"' 2>/dev/null || echo "0"
}

check_service() {
    local url=$1
    local name=$2
    if curl -s --connect-timeout 5 "${url}" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ${name} is reachable"
        return 0
    else
        echo -e "  ${RED}✗${NC} ${name} is not reachable"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Pre-flight checks
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[1/6] Pre-flight checks...${NC}"

if ! check_service "${SEARCH_UI_URL}/health/live" "Search UI"; then
    echo -e "${RED}ERROR: Search UI is not available. Is the cluster running?${NC}"
    exit 1
fi

if ! check_service "${INGESTION_URL}/health" "Ingestion API"; then
    echo -e "${YELLOW}WARNING: Ingestion API is not reachable. Skipping ingestion tests.${NC}"
    SKIP_INGESTION=true
else
    SKIP_INGESTION=false
fi

if ! check_service "${PROMETHEUS_URL}/-/ready" "Prometheus"; then
    echo -e "${RED}ERROR: Prometheus is not available. Is the cluster running?${NC}"
    exit 1
fi

echo ""

# -----------------------------------------------------------------------------
# Get initial metric counts per service
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[2/6] Getting initial metric counts from Prometheus...${NC}"

declare -A INITIAL_COUNTS
for service in "${SERVICES[@]}"; do
    INITIAL_COUNTS[$service]=$(get_service_metric_count "$service")
    echo "  ${service}: ${INITIAL_COUNTS[$service]}"
done

INITIAL_TOTAL=$(get_total_metric_count)
echo "  ---"
echo "  Total: ${INITIAL_TOTAL}"
echo ""

# -----------------------------------------------------------------------------
# Send ingestion requests (triggers indexer + embedding-service)
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[3/6] Sending ingestion requests...${NC}"

INGEST_SUCCESS=0
if [ "$SKIP_INGESTION" = false ]; then
    for i in $(seq 1 ${NUM_REQUESTS}); do
        TIMESTAMP=$(date +%s%N)
        RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${INGESTION_URL}/ingest" \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"Test document ${i} for metrics verification at ${TIMESTAMP}\", \"metadata\": {\"title\": \"verify-otel-metrics-${TIMESTAMP}\"}}" 2>/dev/null)
        
        HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
        
        if [ "${HTTP_CODE}" = "200" ] || [ "${HTTP_CODE}" = "202" ]; then
            echo -e "  ${GREEN}✓${NC} Ingestion ${i}: HTTP ${HTTP_CODE}"
            INGEST_SUCCESS=$((INGEST_SUCCESS + 1))
        else
            echo -e "  ${RED}✗${NC} Ingestion ${i}: HTTP ${HTTP_CODE}"
        fi
    done
    echo "  Ingestion results: ${INGEST_SUCCESS}/${NUM_REQUESTS} succeeded"
else
    echo "  Skipped (Ingestion API not available)"
fi
echo ""

# -----------------------------------------------------------------------------
# Send search requests (triggers search-service + embedding-service)
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[4/6] Sending search requests...${NC}"

SEARCH_SUCCESS=0
for i in $(seq 1 ${NUM_REQUESTS}); do
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${SEARCH_UI_URL}/api/search" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"test query ${i}\", \"mode\": \"bm25\"}" 2>/dev/null)
    
    HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
    
    if [ "${HTTP_CODE}" = "200" ]; then
        TRACE_ID=$(echo "${RESPONSE}" | head -n -1 | jq -r '.metadata.trace_id // "unknown"')
        echo -e "  ${GREEN}✓${NC} Search ${i}: HTTP ${HTTP_CODE} (trace: ${TRACE_ID:0:16}...)"
        SEARCH_SUCCESS=$((SEARCH_SUCCESS + 1))
    else
        echo -e "  ${RED}✗${NC} Search ${i}: HTTP ${HTTP_CODE}"
    fi
done

echo "  Search results: ${SEARCH_SUCCESS}/${NUM_REQUESTS} succeeded"
echo ""

if [ ${SEARCH_SUCCESS} -eq 0 ] && [ ${INGEST_SUCCESS} -eq 0 ]; then
    echo -e "${RED}ERROR: All requests failed. Cannot verify metrics.${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Wait for metrics to propagate
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[5/6] Waiting ${WAIT_SECONDS}s for metrics to propagate...${NC}"
echo "  (Services -> Alloy -> Prometheus)"

for i in $(seq 1 ${WAIT_SECONDS}); do
    printf "\r  Elapsed: %2d/${WAIT_SECONDS}s" ${i}
    sleep 1
done
echo ""
echo ""

# -----------------------------------------------------------------------------
# Verify metrics increased per service
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[6/6] Verifying metrics per service in Prometheus...${NC}"

declare -A FINAL_COUNTS
declare -A DIFFS
SERVICES_WITH_METRICS=0

for service in "${SERVICES[@]}"; do
    FINAL_COUNTS[$service]=$(get_service_metric_count "$service")
    
    INITIAL_INT=${INITIAL_COUNTS[$service]%.*}
    FINAL_INT=${FINAL_COUNTS[$service]%.*}
    DIFFS[$service]=$((FINAL_INT - INITIAL_INT))
    
    if [ ${DIFFS[$service]} -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} ${service}: ${INITIAL_COUNTS[$service]} -> ${FINAL_COUNTS[$service]} (+${DIFFS[$service]})"
        SERVICES_WITH_METRICS=$((SERVICES_WITH_METRICS + 1))
    elif [ "${FINAL_INT}" -gt 0 ]; then
        echo -e "  ${YELLOW}~${NC} ${service}: ${FINAL_COUNTS[$service]} (no change)"
    else
        echo -e "  ${RED}✗${NC} ${service}: no metrics found"
    fi
done

FINAL_TOTAL=$(get_total_metric_count)
INITIAL_TOTAL_INT=${INITIAL_TOTAL%.*}
FINAL_TOTAL_INT=${FINAL_TOTAL%.*}
TOTAL_DIFF=$((FINAL_TOTAL_INT - INITIAL_TOTAL_INT))

echo "  ---"
echo "  Total: ${INITIAL_TOTAL} -> ${FINAL_TOTAL} (+${TOTAL_DIFF})"
echo ""

# -----------------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------------

echo -e "${BLUE}==============================================================================${NC}"

if [ ${SERVICES_WITH_METRICS} -ge 2 ]; then
    echo -e "${GREEN}  ✓ SUCCESS: Metrics are flowing through the pipeline!${NC}"
    echo ""
    echo "  Pipeline verified:"
    echo "    Services (OTel) -> Alloy:4317 -> Prometheus"
    echo ""
    echo "  Services with new metrics: ${SERVICES_WITH_METRICS}/${#SERVICES[@]}"
    echo ""
    echo "  View in Grafana: http://localhost:3000/d/xrag-otel-http"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 0
else
    echo -e "${RED}  ✗ FAILURE: Not enough services reporting metrics.${NC}"
    echo ""
    echo "  Expected: At least 2 services with new metrics"
    echo "  Actual:   ${SERVICES_WITH_METRICS} services"
    echo ""
    echo "  Troubleshooting:"
    echo "    1. Check Alloy logs:  kubectl logs -l app=alloy -n monitoring"
    echo "    2. Check service logs: kubectl logs -l app=search-ui -n rag-system | grep -i otel"
    echo "    3. Check Prometheus targets: ${PROMETHEUS_URL}/targets"
    echo "    4. Verify Alloy config: kubectl get configmap alloy-config -n monitoring -o yaml"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 1
fi
