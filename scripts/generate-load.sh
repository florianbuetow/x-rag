#!/usr/bin/env bash
# Generate load for X-RAG services to populate metrics dashboards
#
# Usage:
#   ./scripts/generate-load.sh              # Default: 50 requests
#   ./scripts/generate-load.sh 100          # 100 requests
#   ./scripts/generate-load.sh 100 0.5      # 100 requests, 0.5s delay between

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Configuration
SEARCH_UI_URL="${SEARCH_UI_URL:-http://localhost:8080}"
INGESTION_URL="${INGESTION_URL:-http://localhost:8082}"
NUM_REQUESTS="${1:-50}"
DELAY="${2:-0.2}"

# Sample queries for search
QUERIES=(
    "what is machine learning?"
    "explain RAG architecture"
    "how do vector databases work?"
    "what is semantic search?"
    "explain embeddings"
    "what is transformer architecture?"
    "how does attention mechanism work?"
    "explain neural networks"
    "what is deep learning?"
    "how to build a chatbot?"
    "what is natural language processing?"
    "explain word embeddings"
    "what is BERT?"
    "how does GPT work?"
    "explain retrieval augmented generation"
)

# Search modes
MODES=("hybrid" "vector" "bm25")

echo -e "${BLUE}=== X-RAG Load Generator ===${NC}"
echo -e "Search URL: ${SEARCH_UI_URL}"
echo -e "Ingestion URL: ${INGESTION_URL}"
echo -e "Requests: ${NUM_REQUESTS}"
echo -e "Delay: ${DELAY}s"
echo ""

# Check if services are accessible
echo -e "${BLUE}Checking service availability...${NC}"
if ! curl -s "${SEARCH_UI_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}✗ Search UI not accessible at ${SEARCH_UI_URL}${NC}"
    echo "  Make sure the cluster is running and port-forwards are active"
    exit 1
fi
echo -e "${GREEN}✓ Search UI accessible${NC}"

if ! curl -s "${INGESTION_URL}/health" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Ingestion API not accessible at ${INGESTION_URL} (skipping ingestion tests)${NC}"
    SKIP_INGESTION=true
else
    echo -e "${GREEN}✓ Ingestion API accessible${NC}"
    SKIP_INGESTION=false
fi
echo ""

# Counters
search_success=0
search_error=0
ingest_success=0
ingest_error=0

# Generate search load
echo -e "${BLUE}Generating search load...${NC}"
for i in $(seq 1 "$NUM_REQUESTS"); do
    # Pick random query and mode
    query_idx=$((RANDOM % ${#QUERIES[@]}))
    mode_idx=$((RANDOM % ${#MODES[@]}))
    query="${QUERIES[$query_idx]}"
    mode="${MODES[$mode_idx]}"
    top_k=$((3 + RANDOM % 8))  # Random top_k between 3 and 10
    
    # Make search request
    response=$(curl -s -w "\n%{http_code}" -X POST "${SEARCH_UI_URL}/api/search" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"${query}\", \"mode\": \"${mode}\", \"top_k\": ${top_k}}" 2>/dev/null || echo "error")
    
    http_code=$(echo "$response" | tail -n1)
    
    if [[ "$http_code" == "200" ]]; then
        ((search_success++))
        printf "\r  Search: %d/%d (success: %d, errors: %d)" "$i" "$NUM_REQUESTS" "$search_success" "$search_error"
    else
        ((search_error++))
        printf "\r  Search: %d/%d (success: %d, errors: %d)" "$i" "$NUM_REQUESTS" "$search_success" "$search_error"
    fi
    
    sleep "$DELAY"
done
echo ""

# Generate ingestion load (smaller batch)
if [[ "$SKIP_INGESTION" != "true" ]]; then
    ingest_count=$((NUM_REQUESTS / 5))  # 20% of search requests
    if [[ $ingest_count -lt 5 ]]; then
        ingest_count=5
    fi
    
    echo -e "${BLUE}Generating ingestion load (${ingest_count} documents)...${NC}"
    for i in $(seq 1 "$ingest_count"); do
        # Generate random document
        doc_title="Load Test Document $i - $(date +%s%N)"
        doc_text="This is a test document generated for load testing purposes. It contains sample text about machine learning, natural language processing, and information retrieval. Document number $i was created at $(date -Iseconds). The purpose of this document is to test the ingestion pipeline, including MinIO storage and Kafka message publishing."
        
        response=$(curl -s -w "\n%{http_code}" -X POST "${INGESTION_URL}/ingest" \
            -H "Content-Type: application/json" \
            -d "{
                \"text\": \"${doc_text}\",
                \"metadata\": {
                    \"title\": \"${doc_title}\",
                    \"type\": \"test\"
                },
                \"namespace\": \"loadtest\"
            }" 2>/dev/null || echo "error")
        
        http_code=$(echo "$response" | tail -n1)
        
        if [[ "$http_code" == "200" ]] || [[ "$http_code" == "201" ]]; then
            ((ingest_success++))
            printf "\r  Ingest: %d/%d (success: %d, errors: %d)" "$i" "$ingest_count" "$ingest_success" "$ingest_error"
        else
            ((ingest_error++))
            printf "\r  Ingest: %d/%d (success: %d, errors: %d)" "$i" "$ingest_count" "$ingest_success" "$ingest_error"
        fi
        
        sleep "$DELAY"
    done
    echo ""
fi

# Summary
echo ""
echo -e "${BLUE}=== Load Generation Complete ===${NC}"
echo -e "Search requests:    ${GREEN}${search_success} success${NC}, ${RED}${search_error} errors${NC}"
if [[ "$SKIP_INGESTION" != "true" ]]; then
    echo -e "Ingestion requests: ${GREEN}${ingest_success} success${NC}, ${RED}${ingest_error} errors${NC}"
fi
echo ""
echo -e "${BLUE}View metrics in Grafana:${NC}"
echo "  http://localhost:3000/d/xrag-overview/x-rag-overview"
echo ""
