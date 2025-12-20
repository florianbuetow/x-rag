#!/bin/bash
# =============================================================================
# Verify OTel Metrics Pipeline
# =============================================================================
# This script verifies that metrics flow correctly through the pipeline:
#   Services -> Alloy (OTLP) -> Prometheus
#
# Usage: ./scripts/verify-otel-metrics.sh
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SEARCH_UI_URL="${SEARCH_UI_URL:-http://localhost:8080}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
NUM_REQUESTS="${NUM_REQUESTS:-5}"
WAIT_SECONDS="${WAIT_SECONDS:-20}"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}  OTel Metrics Pipeline Verification${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""
echo "Configuration:"
echo "  Search UI:    ${SEARCH_UI_URL}"
echo "  Prometheus:   ${PROMETHEUS_URL}"
echo "  Requests:     ${NUM_REQUESTS}"
echo "  Wait time:    ${WAIT_SECONDS}s"
echo ""

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

get_metric_count() {
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

echo -e "${YELLOW}[1/5] Pre-flight checks...${NC}"

if ! check_service "${SEARCH_UI_URL}/health/live" "Search UI"; then
    echo -e "${RED}ERROR: Search UI is not available. Is the cluster running?${NC}"
    exit 1
fi

if ! check_service "${PROMETHEUS_URL}/-/ready" "Prometheus"; then
    echo -e "${RED}ERROR: Prometheus is not available. Is the cluster running?${NC}"
    exit 1
fi

echo ""

# -----------------------------------------------------------------------------
# Get initial metric count
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[2/5] Getting initial metric count from Prometheus...${NC}"

INITIAL_COUNT=$(get_metric_count)
echo "  Initial http_server_duration_milliseconds_count: ${INITIAL_COUNT}"
echo ""

# -----------------------------------------------------------------------------
# Send search requests
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[3/5] Sending ${NUM_REQUESTS} search requests...${NC}"

SUCCESS_COUNT=0
FAIL_COUNT=0

for i in $(seq 1 ${NUM_REQUESTS}); do
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${SEARCH_UI_URL}/api/search" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"test query ${i}\", \"mode\": \"bm25\"}" 2>/dev/null)
    
    HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
    
    if [ "${HTTP_CODE}" = "200" ]; then
        TRACE_ID=$(echo "${RESPONSE}" | head -n -1 | jq -r '.metadata.trace_id // "unknown"')
        echo -e "  ${GREEN}✓${NC} Request ${i}: HTTP ${HTTP_CODE} (trace: ${TRACE_ID:0:16}...)"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo -e "  ${RED}✗${NC} Request ${i}: HTTP ${HTTP_CODE}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

echo ""
echo "  Results: ${SUCCESS_COUNT} succeeded, ${FAIL_COUNT} failed"
echo ""

if [ ${SUCCESS_COUNT} -eq 0 ]; then
    echo -e "${RED}ERROR: All requests failed. Cannot verify metrics.${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Wait for metrics to propagate
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[4/5] Waiting ${WAIT_SECONDS}s for metrics to propagate...${NC}"
echo "  (Services -> Alloy -> Prometheus)"

for i in $(seq 1 ${WAIT_SECONDS}); do
    printf "\r  Elapsed: %2d/${WAIT_SECONDS}s" ${i}
    sleep 1
done
echo ""
echo ""

# -----------------------------------------------------------------------------
# Verify metrics increased
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[5/5] Verifying metrics in Prometheus...${NC}"

FINAL_COUNT=$(get_metric_count)
echo "  Final http_server_duration_milliseconds_count: ${FINAL_COUNT}"

# Calculate difference
INITIAL_INT=${INITIAL_COUNT%.*}
FINAL_INT=${FINAL_COUNT%.*}
DIFF=$((FINAL_INT - INITIAL_INT))

echo "  Difference: +${DIFF} requests"
echo ""

# -----------------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------------

echo -e "${BLUE}==============================================================================${NC}"

if [ ${DIFF} -ge ${SUCCESS_COUNT} ]; then
    echo -e "${GREEN}  ✓ SUCCESS: Metrics are flowing through the pipeline!${NC}"
    echo ""
    echo "  Pipeline verified:"
    echo "    Services (OTel) -> Alloy:4317 -> Prometheus"
    echo ""
    echo "  View in Grafana: http://localhost:3000/d/xrag-otel-http"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 0
else
    echo -e "${RED}  ✗ FAILURE: Metrics did not increase as expected.${NC}"
    echo ""
    echo "  Expected: +${SUCCESS_COUNT} requests"
    echo "  Actual:   +${DIFF} requests"
    echo ""
    echo "  Troubleshooting:"
    echo "    1. Check Alloy logs:  kubectl logs -l app=xrag-alloy -n rag-system"
    echo "    2. Check service logs: kubectl logs -l app=search-ui -n rag-system | grep otel"
    echo "    3. Verify Alloy config: kubectl get configmap alloy-config -n rag-system -o yaml"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 1
fi
