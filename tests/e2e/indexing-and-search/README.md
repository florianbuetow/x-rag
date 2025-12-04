# E2E Test: Indexing and Search

End-to-end test suite for validating the complete X-RAG pipeline.

## Overview

This test validates the full RAG workflow:
1. Environment setup (cluster creation or reset)
2. Pre-ingestion search tests (empty index)
3. Document ingestion from video transcripts
4. Post-ingestion search tests (populated index)
5. System health validation

## Usage

```bash
# Run full test suite
./tests/e2e/indexing-and-search/run.sh

# Limit number of documents (for faster testing)
MAX_DOCUMENTS=10 ./tests/e2e/indexing-and-search/run.sh

# Custom indexing wait time
WAIT_FOR_INDEXING=30 ./tests/e2e/indexing-and-search/run.sh
```

## Prerequisites

- Kind cluster (will be created if not exists)
- Docker running
- `kubectl`, `curl`, `python3`, `make` available
- `OPENAI_API_KEY` set in `.env` (any value for local LLMs)
- Test data in `data/raw/@JasonLiu/video-transcripts/medium-en/`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_DOCUMENTS` | 0 (all) | Limit documents to ingest |
| `WAIT_FOR_INDEXING` | 5 | Seconds to wait after ingestion |
| `OPENAI_API_BASE` | - | Custom LLM endpoint (e.g., LM Studio) |
| `OPENAI_MODEL` | gpt-4o-mini | Model for answer synthesis |

## Output

Results are saved to `tmp/test-results/`:
- `e2e-test-YYYYMMDD-HHMMSS.log` - Full test log
- `pre-ingestion-queries.json` - Search results before ingestion
- `post-ingestion-queries.json` - Search results after ingestion

## Test Phases

### Phase 1: Setup
- Creates Kind cluster if not exists
- Resets data if cluster exists
- Builds and deploys all services

### Phase 2: Pre-Ingestion Tests
- Runs search queries on empty index
- Validates that no results are returned

### Phase 3: Document Ingestion
- Ingests video transcripts via ingestion API
- Waits for indexer to process documents
- Verifies chunks in Weaviate

### Phase 4: Post-Ingestion Tests
- Runs same search queries
- Validates that relevant results are returned

### Phase 5: Validation
- Checks service health endpoints
- Verifies pod status
- Generates summary report
