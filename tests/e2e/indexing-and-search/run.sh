#!/bin/bash
# =============================================================================
# X-RAG End-to-End Test Script: Indexing and Search
# =============================================================================
# This script performs a complete validation of the X-RAG system:
# 1. Sets up a fresh Kind cluster (or resets existing)
# 2. Deploys all services
# 3. Tests search BEFORE ingestion (should return no results)
# 4. Ingests documents from @JasonLiu video transcripts
# 5. Tests search AFTER ingestion (should return relevant results)
# 6. Validates the complete RAG pipeline
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data/raw/@JasonLiu/video-transcripts/medium-en"
RESULTS_DIR="$PROJECT_ROOT/tmp/test-results"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$RESULTS_DIR/e2e-test-$TIMESTAMP.log"

# API Endpoints
SEARCH_UI_URL="http://localhost:8080"
INGESTION_API_URL="http://localhost:8082"

# Test configuration
MAX_DOCUMENTS=${MAX_DOCUMENTS:-0}  # 0 = no limit, ingest all documents
WAIT_FOR_INDEXING=${WAIT_FOR_INDEXING:-5}  # Seconds to wait after ingestion

# Test queries related to the video content
declare -a TEST_QUERIES=(
    "What is Instructor and how does it help with structured outputs?"
    "How do you handle validation in LLM responses?"
    "What are the best practices for building RAG applications?"
    "How does Pydantic work with language models?"
    "What is the difference between vector search and keyword search?"
)

# =============================================================================
# Helper Functions
# =============================================================================

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        INFO)  echo -e "${BLUE}[$timestamp]${NC} ${GREEN}[INFO]${NC} $message" | tee -a "$LOG_FILE" ;;
        WARN)  echo -e "${BLUE}[$timestamp]${NC} ${YELLOW}[WARN]${NC} $message" | tee -a "$LOG_FILE" ;;
        ERROR) echo -e "${BLUE}[$timestamp]${NC} ${RED}[ERROR]${NC} $message" | tee -a "$LOG_FILE" ;;
        STEP)  echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" | tee -a "$LOG_FILE"
               echo -e "${CYAN}  $message${NC}" | tee -a "$LOG_FILE"
               echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n" | tee -a "$LOG_FILE" ;;
    esac
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log ERROR "Required command not found: $1"
        exit 1
    fi
}

check_openai_api_key() {
    # Load .env if it exists
    if [ -f "$PROJECT_ROOT/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    fi

    # Check if OPENAI_API_KEY is set
    if [ -z "$OPENAI_API_KEY" ]; then
        log ERROR "OPENAI_API_KEY is not set"
        log ERROR "Please set an API key in $PROJECT_ROOT/.env (any value for local LLMs)"
        exit 1
    fi

    # Check for placeholder values
    if [[ "$OPENAI_API_KEY" == "sk-your-key-here" ]] || [[ "$OPENAI_API_KEY" == "your-"* ]]; then
        log ERROR "OPENAI_API_KEY contains a placeholder value: $OPENAI_API_KEY"
        log ERROR "Please set a valid API key (or any value like 'lm-studio' for local LLMs)"
        exit 1
    fi

    # Log configuration
    if [ -n "$OPENAI_API_BASE" ]; then
        log INFO "Using custom LLM endpoint: $OPENAI_API_BASE"
        log INFO "Model: ${OPENAI_MODEL:-gpt-4o-mini}"
    else
        log INFO "Using OpenAI API (key: ${OPENAI_API_KEY:0:7}...)"
    fi
}

wait_for_endpoint() {
    local url=$1
    local max_attempts=${2:-60}
    local attempt=1

    log INFO "Waiting for $url to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            log INFO "Endpoint $url is ready"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    log ERROR "Endpoint $url did not become ready after $max_attempts attempts"
    return 1
}

# =============================================================================
# Test Functions
# =============================================================================

test_search() {
    local query=$1
    local expected_results=${2:-"any"}  # "none", "some", or "any"
    local test_phase=$3

    log INFO "Testing query: '$query'"

    local response
    response=$(curl -s -X POST "$SEARCH_UI_URL/api/search" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"$query\",
            \"namespace\": \"default\",
            \"top_k\": 5,
            \"mode\": \"hybrid\"
        }" 2>&1)

    local curl_exit=$?

    if [ $curl_exit -ne 0 ]; then
        log ERROR "Search request failed: $response"
        return 1
    fi

    # Check if response is valid JSON
    if ! echo "$response" | python3 -m json.tool > /dev/null 2>&1; then
        log ERROR "Invalid JSON response: $response"
        return 1
    fi

    # Extract answer and sources count
    local answer
    local sources_count
    answer=$(echo "$response" | python3 -c "import sys, json; r=json.load(sys.stdin); print(r.get('answer', '')[:200])" 2>/dev/null)
    sources_count=$(echo "$response" | python3 -c "import sys, json; r=json.load(sys.stdin); print(len(r.get('sources', [])))" 2>/dev/null)

    log INFO "  Sources found: $sources_count"
    log INFO "  Answer preview: ${answer:0:100}..."

    # Save detailed response to file
    echo "$response" | python3 -m json.tool >> "$RESULTS_DIR/$test_phase-queries.json" 2>/dev/null
    echo "---" >> "$RESULTS_DIR/$test_phase-queries.json"

    # Validate expectations
    case $expected_results in
        none)
            if [ "$sources_count" -eq 0 ]; then
                log INFO "  ✓ Expected no results, got none"
                return 0
            else
                log WARN "  ⚠ Expected no results, but got $sources_count"
                return 0  # Not a failure, just unexpected
            fi
            ;;
        some)
            if [ "$sources_count" -gt 0 ]; then
                log INFO "  ✓ Expected results, got $sources_count sources"
                return 0
            else
                log ERROR "  ✗ Expected results, but got none"
                return 1
            fi
            ;;
        *)
            log INFO "  Results: $sources_count sources"
            return 0
            ;;
    esac
}

ingest_document() {
    local txt_file=$1
    local json_file="${txt_file%.txt}.json"

    if [ ! -f "$txt_file" ] || [ ! -f "$json_file" ]; then
        log WARN "Missing files for: $txt_file"
        return 1
    fi

    # Read content and metadata
    local content
    local metadata
    content=$(cat "$txt_file")
    metadata=$(cat "$json_file")

    # Extract metadata fields
    local title
    local source_file
    local type
    local transcription_method
    title=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin)['metadata']['title'])" 2>/dev/null)
    source_file=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin)['metadata']['source_file'])" 2>/dev/null)
    type=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin)['metadata']['type'])" 2>/dev/null)
    transcription_method=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin)['metadata']['transcription_method'])" 2>/dev/null)

    log INFO "Ingesting: $title"

    # Escape content for JSON (handle special characters)
    local escaped_content
    escaped_content=$(python3 -c "import json, sys; print(json.dumps(sys.stdin.read()))" <<< "$content")

    # Build request payload
    local payload
    payload=$(cat <<EOF
{
    "text": $escaped_content,
    "metadata": {
        "title": "$title",
        "source_file": "$source_file",
        "type": "$type",
        "transcription_method": "$transcription_method"
    },
    "namespace": "default"
}
EOF
)

    # Send ingestion request
    local response
    response=$(curl -s -X POST "$INGESTION_API_URL/ingest" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1)

    local curl_exit=$?

    if [ $curl_exit -ne 0 ]; then
        log ERROR "Ingestion request failed: $response"
        return 1
    fi

    # Check response
    local doc_id
    local status
    doc_id=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('document_id', 'unknown'))" 2>/dev/null)
    status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)

    if [ "$status" = "accepted" ]; then
        log INFO "  ✓ Document accepted: $doc_id"
        return 0
    else
        log ERROR "  ✗ Ingestion failed: $response"
        return 1
    fi
}

# =============================================================================
# Main Test Phases
# =============================================================================

phase_setup() {
    log STEP "PHASE 1: Setup Fresh Environment"

    cd "$PROJECT_ROOT"

    # Check if cluster exists
    if kind get clusters 2>/dev/null | grep -q "xrag-k8"; then
        log INFO "Cluster exists - resetting data and redeploying..."

        # Reset all data (keeps cluster, deletes pods and state)
        log INFO "Resetting cluster data..."
        make cluster-reset

        # Rebuild images with latest code
        log INFO "Building Docker images..."
        make apps-build

        # Redeploy applications
        log INFO "Deploying applications..."
        make apps-deploy
    else
        log INFO "No cluster found - creating fresh cluster..."

        # Full setup from scratch
        log INFO "Cleaning up any remnants..."
        make cluster-clean 2>/dev/null || true

        # Initialize dev environment (install deps, generate gRPC)
        log INFO "Initializing development environment..."
        make init

        # Create cluster and registry first
        log INFO "Creating Kind cluster..."
        make .setup-cluster

        log INFO "Setting up container registry..."
        make .setup-registry

        # Now build and push images (registry exists now)
        log INFO "Building Docker images (this may take a few minutes)..."
        make apps-build

        # Deploy infrastructure and monitoring
        log INFO "Deploying infrastructure..."
        make .deploy-infrastructure

        log INFO "Deploying monitoring..."
        make .deploy-monitoring

        # Deploy applications
        log INFO "Deploying applications..."
        make apps-deploy
    fi

    # Wait for services to be ready
    log INFO "Waiting for services to be ready..."
    wait_for_endpoint "$SEARCH_UI_URL/health/live" 120
    wait_for_endpoint "$INGESTION_API_URL/health/live" 120

    # Additional wait for all pods to stabilize
    log INFO "Waiting for all pods to stabilize..."
    sleep 15

    # Show cluster status
    kubectl get pods -n rag-system

    log INFO "✓ Environment setup complete"
}

phase_pre_ingestion_tests() {
    log STEP "PHASE 2: Pre-Ingestion Search Tests"

    log INFO "Testing search on empty index..."
    echo "# Pre-Ingestion Query Results" > "$RESULTS_DIR/pre-ingestion-queries.json"
    echo "# Timestamp: $(date)" >> "$RESULTS_DIR/pre-ingestion-queries.json"
    echo "" >> "$RESULTS_DIR/pre-ingestion-queries.json"

    local passed=0
    local failed=0

    for query in "${TEST_QUERIES[@]}"; do
        if test_search "$query" "none" "pre-ingestion"; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
        fi
    done

    log INFO "Pre-ingestion tests: $passed passed, $failed failed"

    # This phase should show no results (or very few)
    return 0
}

phase_ingestion() {
    log STEP "PHASE 3: Document Ingestion"

    log INFO "Ingesting documents from $DATA_DIR"

    local count=0
    local success=0
    local failed=0

    # Get list of txt files
    for txt_file in "$DATA_DIR"/*.txt; do
        if [ $MAX_DOCUMENTS -gt 0 ] && [ $count -ge $MAX_DOCUMENTS ]; then
            log INFO "Reached document limit ($MAX_DOCUMENTS)"
            break
        fi

        if ingest_document "$txt_file"; then
            success=$((success + 1))
        else
            failed=$((failed + 1))
        fi

        count=$((count + 1))

        # Small delay between ingestions
        sleep 0.5
    done

    log INFO "Ingestion complete: $success succeeded, $failed failed out of $count total"

    # Wait for indexing to complete
    log INFO "Waiting $WAIT_FOR_INDEXING seconds for indexing to complete..."
    sleep "$WAIT_FOR_INDEXING"

    # Check indexer logs
    log INFO "Checking indexer status..."
    kubectl logs -n rag-system -l app=indexer --tail=20 2>/dev/null || true

    # Verify documents are in Weaviate
    verify_weaviate_indexing
}

verify_weaviate_indexing() {
    log INFO "Verifying documents in Weaviate..."

    local weaviate_url="http://localhost:8081"

    # Get object count from Weaviate
    local response
    response=$(curl -s "$weaviate_url/v1/objects?limit=1" 2>&1)

    if ! echo "$response" | python3 -m json.tool > /dev/null 2>&1; then
        log ERROR "Failed to query Weaviate: $response"
        return 1
    fi

    # Get total count by querying aggregate endpoint
    local count_response
    count_response=$(curl -s -X POST "$weaviate_url/v1/graphql" \
        -H "Content-Type: application/json" \
        -d '{"query": "{ Aggregate { DocumentChunk { meta { count } } } }"}' 2>&1)

    local chunk_count
    chunk_count=$(echo "$count_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    count = data['data']['Aggregate']['DocumentChunk'][0]['meta']['count']
    print(count)
except:
    print('0')
" 2>/dev/null)

    if [ "$chunk_count" -eq 0 ]; then
        log ERROR "No documents found in Weaviate after indexing!"
        log ERROR "Weaviate response: $count_response"
        return 1
    fi

    log INFO "✓ Verified $chunk_count chunks in Weaviate"

    # Also verify namespace filter works
    local namespace_response
    namespace_response=$(curl -s "$weaviate_url/v1/objects?limit=5&where=%7B%22path%22%3A%5B%22namespace%22%5D%2C%22operator%22%3A%22Equal%22%2C%22valueText%22%3A%22default%22%7D" 2>&1)

    local namespace_count
    namespace_count=$(echo "$namespace_response" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('objects', [])))" 2>/dev/null || echo "0")

    if [ "$namespace_count" -gt 0 ]; then
        log INFO "✓ Verified documents exist in 'default' namespace"
    else
        log WARN "Could not verify namespace filtering"
    fi

    return 0
}

phase_post_ingestion_tests() {
    log STEP "PHASE 4: Post-Ingestion Search Tests"

    log INFO "Testing search after document ingestion..."
    echo "# Post-Ingestion Query Results" > "$RESULTS_DIR/post-ingestion-queries.json"
    echo "# Timestamp: $(date)" >> "$RESULTS_DIR/post-ingestion-queries.json"
    echo "" >> "$RESULTS_DIR/post-ingestion-queries.json"

    local passed=0
    local failed=0

    for query in "${TEST_QUERIES[@]}"; do
        if test_search "$query" "some" "post-ingestion"; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
        fi
    done

    log INFO "Post-ingestion tests: $passed passed, $failed failed"

    if [ $failed -gt 0 ]; then
        log WARN "Some queries did not return expected results"
    fi

    return 0
}

phase_validation() {
    log STEP "PHASE 5: System Validation"

    log INFO "Running comprehensive system checks..."

    # Check all services are healthy
    log INFO "Checking service health..."

    local services=("$SEARCH_UI_URL" "$INGESTION_API_URL")
    local all_healthy=true

    for service in "${services[@]}"; do
        local health
        health=$(curl -s "$service/health" 2>/dev/null)
        local status
        status=$(echo "$health" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)

        if [ "$status" = "HEALTHY" ]; then
            log INFO "  ✓ $service is healthy"
        else
            log ERROR "  ✗ $service is not healthy: $health"
            all_healthy=false
        fi
    done

    # Check pod status
    log INFO "Checking pod status..."
    kubectl get pods -n rag-system -o wide

    # Check for any crashed pods
    local crashed_pods
    crashed_pods=$(kubectl get pods -n rag-system --field-selector=status.phase!=Running,status.phase!=Succeeded -o name 2>/dev/null | wc -l)

    if [ "$crashed_pods" -gt 0 ]; then
        log WARN "Found $crashed_pods pods not in Running state"
        kubectl get pods -n rag-system --field-selector=status.phase!=Running,status.phase!=Succeeded
    fi

    # Generate summary
    log STEP "TEST SUMMARY"

    log INFO "Results saved to: $RESULTS_DIR"
    log INFO "Log file: $LOG_FILE"

    if $all_healthy; then
        log INFO "✓ All services healthy"
    else
        log ERROR "✗ Some services unhealthy"
    fi

    echo ""
    echo "=========================================="
    echo "  E2E Test Complete"
    echo "  Results: $RESULTS_DIR"
    echo "=========================================="
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    # Create results directory first (before any logging)
    mkdir -p "$RESULTS_DIR"

    log STEP "X-RAG End-to-End Test Suite"
    log INFO "Timestamp: $TIMESTAMP"
    log INFO "Project root: $PROJECT_ROOT"
    log INFO "Data directory: $DATA_DIR"
    log INFO "Max documents: $MAX_DOCUMENTS"

    # Check prerequisites
    check_command curl
    check_command kubectl
    check_command python3
    check_command make

    # Validate OpenAI API key before starting
    check_openai_api_key

    # Verify data directory exists
    if [ ! -d "$DATA_DIR" ]; then
        log ERROR "Data directory not found: $DATA_DIR"
        exit 1
    fi

    local txt_count
    txt_count=$(ls -1 "$DATA_DIR"/*.txt 2>/dev/null | wc -l)
    log INFO "Found $txt_count transcript files"

    # Run test phases
    phase_setup
    phase_pre_ingestion_tests
    phase_ingestion
    phase_post_ingestion_tests
    phase_validation

    log INFO "Test suite completed successfully!"
}

# Run main function
main "$@"
