#!/bin/bash
# =============================================================================
# Verify OTel Traces Pipeline
# =============================================================================
# This script verifies that traces flow correctly through the pipeline:
#   Services -> Alloy (OTLP) -> Tempo
#
# Tests all services:
#   - search-ui (HTTP)
#   - ingestion-api (HTTP)
#   - search-service (gRPC, triggered via search-ui)
#   - embedding-service (gRPC, triggered via search/indexer)
#   - indexer (Kafka consumer, triggered via ingestion)
#
# Usage: ./scripts/verify-otel-traces.sh
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
    echo "  OTel Traces Verification SKIPPED"
    echo "=============================================="
    echo ""
    echo "Observability is disabled (OBSERVABILITY_ENABLED=false)."
    echo "Set OBSERVABILITY_ENABLED=true in .env to enable tracing."
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
TEMPO_URL="${TEMPO_URL:-http://localhost:3200}"
NUM_REQUESTS="${NUM_REQUESTS:-2}"
WAIT_SECONDS="${WAIT_SECONDS:-20}"

# All services to check
SERVICES=("search-ui" "ingestion-api" "search-service" "embedding-service" "indexer")

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}  OTel Traces Pipeline Verification (All Services)${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""
echo "Configuration:"
echo "  Search UI:      ${SEARCH_UI_URL}"
echo "  Ingestion API:  ${INGESTION_URL}"
echo "  Tempo:          ${TEMPO_URL}"
echo "  Requests:       ${NUM_REQUESTS}"
echo "  Wait time:      ${WAIT_SECONDS}s"
echo ""

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

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

query_trace_by_id() {
    local trace_id=$1
    curl -s "${TEMPO_URL}/api/traces/${trace_id}" 2>/dev/null
}

get_service_trace_count() {
    local service=$1
    local result
    result=$(curl -s "${TEMPO_URL}/api/search?tags=service.name%3D${service}&limit=100" 2>/dev/null)
    echo "${result}" | jq -r '.traces | length // 0' 2>/dev/null || echo "0"
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

if ! check_service "${TEMPO_URL}/ready" "Tempo"; then
    echo -e "${RED}ERROR: Tempo is not available. Is the cluster running?${NC}"
    exit 1
fi

echo ""

# -----------------------------------------------------------------------------
# Get initial trace counts per service
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[2/6] Getting initial trace counts from Tempo...${NC}"

declare -A INITIAL_COUNTS
for service in "${SERVICES[@]}"; do
    INITIAL_COUNTS[$service]=$(get_service_trace_count "$service")
    echo "  ${service}: ${INITIAL_COUNTS[$service]} traces"
done
echo ""

# -----------------------------------------------------------------------------
# Send ingestion requests (triggers indexer + embedding-service)
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[3/6] Sending ingestion requests...${NC}"

declare -a INGEST_TRACE_IDS
INGEST_SUCCESS=0

if [ "$SKIP_INGESTION" = false ]; then
    for i in $(seq 1 ${NUM_REQUESTS}); do
        TIMESTAMP=$(date +%s%N)
        RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${INGESTION_URL}/ingest" \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"Test document ${i} for trace verification at ${TIMESTAMP}\", \"metadata\": {\"title\": \"verify-otel-traces-${TIMESTAMP}\"}}" 2>/dev/null)
        
        HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
        BODY=$(echo "${RESPONSE}" | head -n -1)
        
        if [ "${HTTP_CODE}" = "200" ] || [ "${HTTP_CODE}" = "202" ]; then
            TRACE_ID=$(echo "${BODY}" | jq -r '.trace_id // .metadata.trace_id // ""' 2>/dev/null)
            if [ -n "${TRACE_ID}" ] && [ "${TRACE_ID}" != "null" ]; then
                INGEST_TRACE_IDS+=("${TRACE_ID}")
                echo -e "  ${GREEN}✓${NC} Ingestion ${i}: HTTP ${HTTP_CODE} (trace: ${TRACE_ID:0:16}...)"
            else
                echo -e "  ${GREEN}✓${NC} Ingestion ${i}: HTTP ${HTTP_CODE} (no trace_id in response)"
            fi
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

declare -a SEARCH_TRACE_IDS
SEARCH_SUCCESS=0

for i in $(seq 1 ${NUM_REQUESTS}); do
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${SEARCH_UI_URL}/api/search" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"trace test query ${i}\", \"mode\": \"bm25\"}" 2>/dev/null)
    
    HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
    
    if [ "${HTTP_CODE}" = "200" ]; then
        TRACE_ID=$(echo "${RESPONSE}" | head -n -1 | jq -r '.metadata.trace_id // ""')
        if [ -n "${TRACE_ID}" ] && [ "${TRACE_ID}" != "null" ]; then
            SEARCH_TRACE_IDS+=("${TRACE_ID}")
            echo -e "  ${GREEN}✓${NC} Search ${i}: HTTP ${HTTP_CODE} (trace: ${TRACE_ID:0:16}...)"
            SEARCH_SUCCESS=$((SEARCH_SUCCESS + 1))
        else
            echo -e "  ${YELLOW}!${NC} Search ${i}: HTTP ${HTTP_CODE} (no trace_id in response)"
        fi
    else
        echo -e "  ${RED}✗${NC} Search ${i}: HTTP ${HTTP_CODE}"
    fi
done

echo "  Search results: ${SEARCH_SUCCESS}/${NUM_REQUESTS} succeeded with trace IDs"
echo ""

if [ ${SEARCH_SUCCESS} -eq 0 ] && [ ${#INGEST_TRACE_IDS[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: No trace IDs collected. Cannot verify traces.${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Wait for traces to propagate
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[5/6] Waiting ${WAIT_SECONDS}s for traces to propagate...${NC}"
echo "  (Services -> Alloy -> Tempo)"

for i in $(seq 1 ${WAIT_SECONDS}); do
    printf "\r  Elapsed: %2d/${WAIT_SECONDS}s" ${i}
    sleep 1
done
echo ""
echo ""

# -----------------------------------------------------------------------------
# Verify traces per service
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[6/6] Verifying traces per service in Tempo...${NC}"

declare -A FINAL_COUNTS
declare -A DIFFS
SERVICES_WITH_TRACES=0

for service in "${SERVICES[@]}"; do
    FINAL_COUNTS[$service]=$(get_service_trace_count "$service")
    DIFFS[$service]=$((FINAL_COUNTS[$service] - INITIAL_COUNTS[$service]))
    
    if [ ${DIFFS[$service]} -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} ${service}: ${INITIAL_COUNTS[$service]} -> ${FINAL_COUNTS[$service]} (+${DIFFS[$service]} traces)"
        SERVICES_WITH_TRACES=$((SERVICES_WITH_TRACES + 1))
    elif [ "${FINAL_COUNTS[$service]}" -gt 0 ]; then
        echo -e "  ${YELLOW}~${NC} ${service}: ${FINAL_COUNTS[$service]} traces (no change)"
    else
        echo -e "  ${RED}✗${NC} ${service}: no traces found"
    fi
done

echo ""

# Verify specific trace IDs from search requests
echo "  Verifying captured search trace IDs:"
FOUND_COUNT=0
for trace_id in "${SEARCH_TRACE_IDS[@]}"; do
    TRACE_RESULT=$(query_trace_by_id "${trace_id}")
    
    if echo "${TRACE_RESULT}" | jq -e '.batches' > /dev/null 2>&1; then
        SPAN_COUNT=$(echo "${TRACE_RESULT}" | jq '[.batches[].scopeSpans[].spans | length] | add // 0')
        echo -e "    ${GREEN}✓${NC} ${trace_id:0:16}... (${SPAN_COUNT} spans)"
        FOUND_COUNT=$((FOUND_COUNT + 1))
    elif echo "${TRACE_RESULT}" | jq -e '.resourceSpans' > /dev/null 2>&1; then
        SPAN_COUNT=$(echo "${TRACE_RESULT}" | jq '[.resourceSpans[].scopeSpans[].spans | length] | add // 0')
        echo -e "    ${GREEN}✓${NC} ${trace_id:0:16}... (${SPAN_COUNT} spans)"
        FOUND_COUNT=$((FOUND_COUNT + 1))
    else
        echo -e "    ${RED}✗${NC} ${trace_id:0:16}... not found"
    fi
done

echo ""

# -----------------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------------

echo -e "${BLUE}==============================================================================${NC}"

if [ ${SERVICES_WITH_TRACES} -ge 2 ] || [ ${FOUND_COUNT} -gt 0 ]; then
    echo -e "${GREEN}  ✓ SUCCESS: Traces are flowing through the pipeline!${NC}"
    echo ""
    echo "  Pipeline verified:"
    echo "    Services (OTel) -> Alloy:4317 -> Tempo"
    echo ""
    echo "  Services with new traces: ${SERVICES_WITH_TRACES}/${#SERVICES[@]}"
    echo "  Search traces found: ${FOUND_COUNT}/${#SEARCH_TRACE_IDS[@]}"
    echo ""
    echo "  View in Grafana: http://localhost:3000/explore"
    echo "    - Select 'Tempo' as data source"
    echo "    - Search by service name or trace ID"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 0
else
    echo -e "${RED}  ✗ FAILURE: Not enough services reporting traces.${NC}"
    echo ""
    echo "  Expected: At least 2 services with new traces"
    echo "  Actual:   ${SERVICES_WITH_TRACES} services"
    echo ""
    echo "  Troubleshooting:"
    echo "    1. Check Alloy logs:  kubectl logs -l app=alloy -n monitoring"
    echo "    2. Check Tempo logs:  kubectl logs -l app=tempo -n monitoring"
    echo "    3. Check service tracing: kubectl logs -l app=search-ui -n rag-system | grep -i trace"
    echo "    4. Verify Alloy config: kubectl get configmap alloy-config -n monitoring -o yaml"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 1
fi
