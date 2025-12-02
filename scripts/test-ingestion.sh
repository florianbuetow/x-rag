#!/bin/bash
# Test script for document ingestion
#
# Usage: ./scripts/test-ingestion.sh

set -euo pipefail

INGESTION_URL="${INGESTION_URL:-http://localhost:8082/ingest}"

echo "=== Testing Document Ingestion ==="
echo "Ingestion URL: $INGESTION_URL"
echo

# Test document
RESPONSE=$(curl -s -X POST "$INGESTION_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Python is a high-level, interpreted programming language known for its simplicity and readability. Created by Guido van Rossum and first released in 1991, Python emphasizes code readability with its notable use of significant whitespace. The language supports multiple programming paradigms including procedural, object-oriented, and functional programming styles. Python has a comprehensive standard library that supports many common programming tasks such as connecting to web servers, reading and modifying files, and working with data structures.",
    "metadata": {
      "title": "Python Programming Language Overview",
      "source_file": "python_intro.txt",
      "type": "technical"
    },
    "namespace": "test"
  }')

echo "Response:"
echo "$RESPONSE" | python3 -m json.tool

# Extract document ID
DOCUMENT_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['document_id'])")

echo
echo "✓ Document ingested successfully"
echo "Document ID: $DOCUMENT_ID"
echo
echo "You can monitor the indexer logs with:"
echo "  kubectl logs -f -l app=indexer -n rag-system"
