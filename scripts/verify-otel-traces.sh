#!/bin/bash
# =============================================================================
# Verify OTel Traces Pipeline
# =============================================================================
# This script verifies that traces flow correctly through the pipeline:
#   Services -> Alloy (OTLP) -> Tempo
#
# Usage: ./scripts/verify-otel-traces.sh
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
TEMPO_URL="${TEMPO_URL:-http://localhost:3200}"
NUM_REQUESTS="${NUM_REQUESTS:-3}"
WAIT_SECONDS="${WAIT_SECONDS:-15}"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}  OTel Traces Pipeline Verification${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""
echo "Configuration:"
echo "  Search UI:    ${SEARCH_UI_URL}"
echo "  Tempo:        ${TEMPO_URL}"
echo "  Requests:     ${NUM_REQUESTS}"
echo "  Wait time:    ${WAIT_SECONDS}s"
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
    local result
    result=$(curl -s "${TEMPO_URL}/api/traces/${trace_id}" 2>/dev/null)
    echo "${result}"
}

# -----------------------------------------------------------------------------
# Pre-flight checks
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[1/5] Pre-flight checks...${NC}"

if ! check_service "${SEARCH_UI_URL}/health/live" "Search UI"; then
    echo -e "${RED}ERROR: Search UI is not available. Is the cluster running?${NC}"
    exit 1
fi

if ! check_service "${TEMPO_URL}/ready" "Tempo"; then
    echo -e "${RED}ERROR: Tempo is not available. Is the cluster running?${NC}"
    exit 1
fi

echo ""

# -----------------------------------------------------------------------------
# Send search requests and collect trace IDs
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[2/5] Sending ${NUM_REQUESTS} search requests...${NC}"

declare -a TRACE_IDS
SUCCESS_COUNT=0
FAIL_COUNT=0

for i in $(seq 1 ${NUM_REQUESTS}); do
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${SEARCH_UI_URL}/api/search" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"trace test query ${i}\", \"mode\": \"bm25\"}" 2>/dev/null)
    
    HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
    
    if [ "${HTTP_CODE}" = "200" ]; then
        TRACE_ID=$(echo "${RESPONSE}" | head -n -1 | jq -r '.metadata.trace_id // ""')
        if [ -n "${TRACE_ID}" ] && [ "${TRACE_ID}" != "null" ]; then
            TRACE_IDS+=("${TRACE_ID}")
            echo -e "  ${GREEN}✓${NC} Request ${i}: HTTP ${HTTP_CODE} (trace: ${TRACE_ID:0:16}...)"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo -e "  ${YELLOW}!${NC} Request ${i}: HTTP ${HTTP_CODE} (no trace_id in response)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        echo -e "  ${RED}✗${NC} Request ${i}: HTTP ${HTTP_CODE}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

echo ""
echo "  Results: ${SUCCESS_COUNT} succeeded with trace IDs, ${FAIL_COUNT} failed"
echo ""

if [ ${SUCCESS_COUNT} -eq 0 ]; then
    echo -e "${RED}ERROR: No trace IDs collected. Cannot verify traces.${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Wait for traces to propagate
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[3/5] Waiting ${WAIT_SECONDS}s for traces to propagate...${NC}"
echo "  (Services -> Alloy -> Tempo)"

for i in $(seq 1 ${WAIT_SECONDS}); do
    printf "\r  Elapsed: %2d/${WAIT_SECONDS}s" ${i}
    sleep 1
done
echo ""
echo ""

# -----------------------------------------------------------------------------
# Verify traces in Tempo
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[4/5] Verifying traces in Tempo...${NC}"

FOUND_COUNT=0
NOT_FOUND_COUNT=0

for trace_id in "${TRACE_IDS[@]}"; do
    TRACE_RESULT=$(query_trace_by_id "${trace_id}")
    
    if echo "${TRACE_RESULT}" | jq -e '.batches' > /dev/null 2>&1; then
        SPAN_COUNT=$(echo "${TRACE_RESULT}" | jq '[.batches[].scopeSpans[].spans | length] | add // 0')
        echo -e "  ${GREEN}✓${NC} Trace ${trace_id:0:16}... found (${SPAN_COUNT} spans)"
        FOUND_COUNT=$((FOUND_COUNT + 1))
    elif echo "${TRACE_RESULT}" | jq -e '.resourceSpans' > /dev/null 2>&1; then
        SPAN_COUNT=$(echo "${TRACE_RESULT}" | jq '[.resourceSpans[].scopeSpans[].spans | length] | add // 0')
        echo -e "  ${GREEN}✓${NC} Trace ${trace_id:0:16}... found (${SPAN_COUNT} spans)"
        FOUND_COUNT=$((FOUND_COUNT + 1))
    else
        echo -e "  ${RED}✗${NC} Trace ${trace_id:0:16}... not found"
        NOT_FOUND_COUNT=$((NOT_FOUND_COUNT + 1))
    fi
done

echo ""

# -----------------------------------------------------------------------------
# Search for recent traces by service
# -----------------------------------------------------------------------------

echo -e "${YELLOW}[5/5] Querying recent traces by service...${NC}"

SEARCH_RESULT=$(curl -s "${TEMPO_URL}/api/search?tags=service.name%3Dsearch-ui&limit=5" 2>/dev/null)

if echo "${SEARCH_RESULT}" | jq -e '.traces' > /dev/null 2>&1; then
    TRACE_COUNT=$(echo "${SEARCH_RESULT}" | jq '.traces | length')
    echo -e "  ${GREEN}✓${NC} Found ${TRACE_COUNT} recent traces for search-ui service"
else
    echo -e "  ${YELLOW}!${NC} Could not query traces by service tag"
fi

echo ""

# -----------------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------------

echo -e "${BLUE}==============================================================================${NC}"

if [ ${FOUND_COUNT} -gt 0 ]; then
    echo -e "${GREEN}  ✓ SUCCESS: Traces are flowing through the pipeline!${NC}"
    echo ""
    echo "  Pipeline verified:"
    echo "    Services (OTel) -> Alloy:4317 -> Tempo"
    echo ""
    echo "  Traces found: ${FOUND_COUNT}/${SUCCESS_COUNT}"
    echo ""
    echo "  View in Grafana: http://localhost:3000/explore"
    echo "    - Select 'Tempo' as data source"
    echo "    - Search by trace ID or service name"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 0
else
    echo -e "${RED}  ✗ FAILURE: No traces found in Tempo.${NC}"
    echo ""
    echo "  Expected: ${SUCCESS_COUNT} traces"
    echo "  Found:    ${FOUND_COUNT} traces"
    echo ""
    echo "  Troubleshooting:"
    echo "    1. Check Alloy logs:  kubectl logs -l app=xrag-alloy -n rag-system"
    echo "    2. Check Tempo logs:  kubectl logs -l app=xrag-tempo -n rag-system"
    echo "    3. Check service tracing: kubectl logs -l app=search-ui -n rag-system | grep -i trace"
    echo "    4. Verify Alloy config: kubectl get configmap alloy-config -n rag-system -o yaml"
    echo -e "${BLUE}==============================================================================${NC}"
    exit 1
fi
