#!/bin/bash
# =============================================================================
# X-RAG E2E Test Runner
# =============================================================================
# Runs all end-to-end tests in sequence.
# WARNING: These tests are destructive - they reset/recreate the cluster!
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo "  X-RAG End-to-End Test Suite"
echo "=============================================="
echo ""
echo "WARNING: E2E tests are destructive!"
echo "  - May reset or recreate the cluster"
echo "  - Will delete existing data"
echo ""

# Run all E2E tests
echo "Running: indexing-and-search"
echo "----------------------------------------------"
"$SCRIPT_DIR/indexing-and-search/run.sh"

echo ""
echo "=============================================="
echo "  All E2E tests completed!"
echo "=============================================="
