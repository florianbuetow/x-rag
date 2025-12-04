# X-RAG Comprehensive Test Plan

**Version:** 1.1
**Status:** Partially Implemented
**Current Coverage:** 78.10% line coverage
**Target Coverage:** 90%+ line coverage, 100% critical path coverage

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Test Strategy](#3-test-strategy)
4. [Unit Test Requirements](#4-unit-test-requirements)
5. [Integration Test Requirements](#5-integration-test-requirements)
6. [End-to-End Test Requirements](#6-end-to-end-test-requirements)
7. [Performance Test Requirements](#7-performance-test-requirements)
8. [Security Test Requirements](#8-security-test-requirements)
9. [Test Infrastructure](#9-test-infrastructure)
10. [Coverage Requirements](#10-coverage-requirements)
11. [Certification Checklist](#11-certification-checklist)
12. [Implementation Priority](#12-implementation-priority)

---

## 1. Executive Summary

### 1.1 Objective

Establish a comprehensive test suite that provides confidence for production deployment. This plan ensures:

- **Functional correctness** - All features work as specified
- **Reliability** - System handles failures gracefully
- **Performance** - Meets latency and throughput requirements
- **Security** - No vulnerabilities in OWASP Top 10 categories
- **Maintainability** - Tests serve as living documentation

### 1.2 Scope

| Component | Unit Tests | Integration Tests | E2E Tests | Performance | Security |
|-----------|------------|-------------------|-----------|-------------|----------|
| Core Domain | ✅ Required | - | - | - | - |
| Common Utilities | ✅ Required | - | - | - | - |
| Embedding Service | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Search Service | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Search UI | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Ingestion API | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Indexer | ✅ Required | ✅ Required | ✅ Required | ✅ Required | - |
| Pipelines | ✅ Required | ✅ Required | - | ✅ Required | - |
| Retrievers | ✅ Required | ✅ Required | - | ✅ Required | - |
| LLM Client | ✅ Required | ✅ Required | - | - | ✅ Required |

### 1.3 Success Criteria

- [ ] **90%+ line coverage** on all source modules (excluding proto_gen)
- [ ] **100% branch coverage** on critical paths (auth, data validation, error handling)
- [ ] **Zero critical/high severity** security issues from Bandit
- [ ] **All E2E scenarios pass** in fresh cluster deployment
- [ ] **P95 latency < 500ms** for search operations under load
- [ ] **All tests pass** in CI pipeline before merge

---

## 2. Current State Analysis

### 2.1 Existing Test Inventory

| Test File | Location | Tests | Module Covered |
|-----------|----------|-------|----------------|
| `test_config.py` | tests/ | Config validation | `common/config.py` |
| `test_health.py` | tests/ | Health checker | `common/health.py` |
| `test_prompt_templates.py` | tests/ | Prompt building | `pipelines/prompt_templates.py` |
| `test_indexing_pipeline.py` | tests/ | Indexing pipeline | `pipelines/indexing_pipeline.py` |
| `test_indexer_processor.py` | tests/ | Document processing | `indexer/processor.py` |
| `test_search_service_config.py` | tests/ | Search config | `search_service/config.py` |
| `test_ingestion_api.py` | tests/ | Basic endpoints | `ingestion_api/main.py` |
| `test_embedding_service_server.py` | tests/unit/ | gRPC servicer | `embedding_service/server.py` |
| `test_search_service_server.py` | tests/unit/ | gRPC servicer | `search_service/server.py` |
| `test_search_pipeline.py` | tests/unit/ | Search pipeline | `pipelines/search_pipeline.py` |
| `test_search_ui.py` | tests/unit/ | UI components | `search_ui/*` |
| `test_indexer_consumer.py` | tests/unit/ | Kafka consumer | `indexer/consumer.py` |
| `test_weaviate_retriever.py` | tests/unit/ | Weaviate retriever | `retrievers/weaviate_retriever.py` |
| `test_ingestion_api.py` | tests/unit/ | API endpoints | `ingestion_api/main.py` |
| `test_end_to_end.py` | tests/integration/ | Full flow | All services |
| `test_search_ui_integration.py` | tests/integration/ | UI integration | Search UI + Search Service |

**Current Metrics (as of December 2025):**
- Total test files: 29
- Total tests: 546
- Unit tests: 538
- Integration tests: 8
- Line coverage: 78.10%

### 2.2 Implementation Progress

| Test Category | Status | Tests |
|---------------|--------|-------|
| Core Domain (`src/core/`) | ✅ Complete | 100% coverage |
| Common Utilities (`src/common/`) | ✅ Complete | 87-100% coverage |
| Embedding Generators | ✅ Complete | 97-100% coverage |
| Service Clients (gRPC, Kafka, MinIO) | ✅ Complete | 94-100% coverage |
| LLM Client | ✅ Complete | 100% coverage |
| Service main.py entry points | ⏳ Pending | 0% (need integration tests) |

### 2.3 Coverage Gaps

#### ✅ Resolved Gaps (December 2025)

| Module | File | Status | Coverage |
|--------|------|--------|----------|
| `src/core/` | `document.py` | ✅ Complete | 100% |
| `src/core/` | `errors.py` | ✅ Complete | 100% |
| `src/core/` | `interfaces.py` | ✅ Complete | 100% |
| `src/llm/` | `openai_client.py` | ✅ Complete | 100% |
| `src/common/` | `grpc_utils.py` | ✅ Complete | 87% |
| `src/common/` | `metrics.py` | ✅ Complete | 100% |
| `src/embedding_service/generators/` | `factory.py` | ✅ Complete | 100% |
| `src/embedding_service/generators/` | `openai_generator.py` | ✅ Complete | 100% |
| `src/embedding_service/generators/` | `hash_based_generator.py` | ✅ Complete | 98% |
| `src/ingestion_api/` | `kafka_client.py` | ✅ Complete | 94% |
| `src/ingestion_api/` | `minio_client.py` | ✅ Complete | 100% |
| `src/search_service/` | `grpc_clients.py` | ✅ Complete | 100% |
| `src/indexer/` | `grpc_clients.py` | ✅ Complete | 100% |

#### Remaining Gaps (Low Priority)

| Module | File | Reason | Coverage |
|--------|------|--------|----------|
| `src/embedding_service/` | `main.py` | Service entry point - requires integration tests | 0% |
| `src/indexer/` | `main.py` | Service entry point - requires integration tests | 0% |
| `src/search_service/` | `main.py` | Service entry point - requires integration tests | 0% |
| `src/embedding_service/` | `config.py` | Configuration validation | 0% |

---

## 3. Test Strategy

### 3.1 Test Pyramid

```
                    ┌─────────────┐
                    │    E2E      │  ← 5-10 critical user journeys
                    │   Tests     │     (slow, expensive, high confidence)
                   ─┴─────────────┴─
                  ┌─────────────────┐
                  │  Integration    │  ← Service boundaries, external deps
                  │    Tests        │     (medium speed, mocked infra)
                 ─┴─────────────────┴─
                ┌───────────────────────┐
                │      Unit Tests       │  ← Individual functions/classes
                │                       │     (fast, isolated, comprehensive)
               ─┴───────────────────────┴─
```

### 3.2 Testing Principles

1. **Isolation**: Unit tests mock all external dependencies
2. **Determinism**: No flaky tests - use fixed seeds, controlled time
3. **Speed**: Unit tests < 100ms each, integration < 5s each
4. **Clarity**: Test names describe behavior, not implementation
5. **Maintainability**: Prefer explicit assertions over magic

### 3.3 Test Naming Convention

```python
def test_<unit>_<scenario>_<expected_behavior>():
    """
    Tests that <unit> <expected_behavior> when <scenario>.
    """
```

Example:
```python
def test_document_processor_returns_empty_list_when_input_is_empty():
    """Tests that document processor returns empty list when input is empty."""
```

### 3.4 Test Organization

```
tests/
├── conftest.py                    # Shared fixtures
├── unit/                          # Fast, isolated tests
│   ├── core/                      # Core domain tests
│   │   ├── test_document.py
│   │   ├── test_errors.py
│   │   └── test_interfaces.py
│   ├── common/                    # Common utilities tests
│   │   ├── test_config.py
│   │   ├── test_health.py
│   │   ├── test_grpc_utils.py
│   │   └── test_metrics.py
│   ├── embedding_service/         # Embedding service tests
│   │   ├── test_server.py
│   │   ├── test_config.py
│   │   └── generators/
│   │       ├── test_factory.py
│   │       ├── test_openai_generator.py
│   │       └── test_hash_based_generator.py
│   ├── search_service/            # Search service tests
│   │   ├── test_server.py
│   │   ├── test_config.py
│   │   └── test_grpc_clients.py
│   ├── search_ui/                 # Search UI tests
│   │   ├── test_main.py
│   │   ├── test_models.py
│   │   ├── test_config.py
│   │   └── test_grpc_clients.py
│   ├── ingestion_api/             # Ingestion API tests
│   │   ├── test_main.py
│   │   ├── test_config.py
│   │   ├── test_kafka_client.py
│   │   └── test_minio_client.py
│   ├── indexer/                   # Indexer tests
│   │   ├── test_consumer.py
│   │   ├── test_processor.py
│   │   ├── test_config.py
│   │   └── test_grpc_clients.py
│   ├── pipelines/                 # Pipeline tests
│   │   ├── test_indexing_pipeline.py
│   │   ├── test_search_pipeline.py
│   │   └── test_prompt_templates.py
│   ├── retrievers/                # Retriever tests
│   │   └── test_weaviate_retriever.py
│   └── llm/                       # LLM client tests
│       └── test_openai_client.py
├── integration/                   # Service boundary tests
│   ├── test_embedding_integration.py
│   ├── test_search_integration.py
│   ├── test_ingestion_integration.py
│   ├── test_indexer_integration.py
│   └── test_pipeline_integration.py
├── e2e/                           # End-to-end tests
│   ├── test_document_ingestion_flow.py
│   ├── test_search_flow.py
│   ├── test_health_checks.py
│   └── test_monitoring.py
├── performance/                   # Performance tests
│   ├── test_search_latency.py
│   ├── test_ingestion_throughput.py
│   └── test_embedding_batch.py
└── security/                      # Security tests
    ├── test_input_validation.py
    ├── test_injection_prevention.py
    └── test_authentication.py
```

---

## 4. Unit Test Requirements

### 4.1 Core Domain (`src/core/`)

#### `test_document.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_document_creation_with_valid_data` | Create document with all required fields | Critical |
| `test_document_creation_with_optional_fields` | Create document with metadata | Critical |
| `test_document_validation_rejects_empty_content` | Reject empty content | Critical |
| `test_document_validation_rejects_empty_id` | Reject empty document ID | Critical |
| `test_document_serialization_to_dict` | Serialize to dictionary | High |
| `test_document_deserialization_from_dict` | Deserialize from dictionary | High |
| `test_document_equality_comparison` | Two documents with same data are equal | Medium |
| `test_document_hash_for_deduplication` | Document hashing for sets/dicts | Medium |

#### `test_errors.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_validation_error_contains_field_info` | Error includes which field failed | Critical |
| `test_service_unavailable_error_includes_service_name` | Error identifies failed service | Critical |
| `test_timeout_error_includes_duration` | Error shows timeout duration | High |
| `test_rate_limit_error_includes_retry_after` | Error provides retry guidance | High |
| `test_error_inheritance_hierarchy` | All errors inherit from base | Medium |
| `test_error_string_representation` | Errors have readable `__str__` | Medium |

#### `test_interfaces.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_embedder_protocol_enforcement` | Verify protocol requirements | High |
| `test_retriever_protocol_enforcement` | Verify protocol requirements | High |
| `test_generator_protocol_enforcement` | Verify protocol requirements | High |
| `test_protocol_runtime_checkable` | Protocols work with isinstance | Medium |

### 4.2 Common Utilities (`src/common/`)

#### `test_grpc_utils.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_create_channel_with_valid_address` | Create gRPC channel successfully | Critical |
| `test_create_channel_with_invalid_address_raises` | Reject malformed addresses | Critical |
| `test_channel_options_applied` | Verify keepalive, compression settings | High |
| `test_retry_interceptor_retries_on_unavailable` | Retry transient failures | Critical |
| `test_retry_interceptor_respects_max_retries` | Stop after max attempts | High |
| `test_retry_interceptor_no_retry_on_invalid_argument` | Don't retry client errors | High |
| `test_timeout_interceptor_cancels_slow_calls` | Cancel calls exceeding timeout | Critical |
| `test_logging_interceptor_logs_method_calls` | Log all gRPC method calls | Medium |

#### `test_metrics.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_counter_increment` | Increment Prometheus counter | High |
| `test_histogram_observe` | Record histogram observation | High |
| `test_gauge_set` | Set gauge value | High |
| `test_labels_applied_correctly` | Metrics have correct labels | High |
| `test_metrics_endpoint_returns_prometheus_format` | `/metrics` returns valid format | Critical |

### 4.3 Embedding Service (`src/embedding_service/`)

#### `test_config.py` (embedding_service)

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_config_loads_from_environment` | Load config from env vars | Critical |
| `test_config_validates_model_name` | Reject invalid model names | High |
| `test_config_validates_dimension` | Reject invalid dimensions | High |
| `test_config_default_values` | Defaults applied when env empty | High |

#### `test_factory.py` (generators)

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_factory_creates_openai_generator` | Create OpenAI generator by name | Critical |
| `test_factory_creates_hash_generator` | Create hash generator by name | Critical |
| `test_factory_raises_for_unknown_type` | Error on unknown generator type | High |
| `test_factory_passes_config_to_generator` | Config forwarded correctly | High |

#### `test_openai_generator.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_embed_single_text_returns_vector` | Embed single text successfully | Critical |
| `test_embed_batch_returns_multiple_vectors` | Batch embedding works | Critical |
| `test_embed_handles_rate_limit` | Retry on 429 response | Critical |
| `test_embed_handles_api_error` | Graceful error on API failure | Critical |
| `test_embed_validates_input_length` | Reject too-long inputs | High |
| `test_embed_returns_correct_dimension` | Vector has expected dimension | High |
| `test_embed_caches_results` | Cache hit returns same result | Medium |

#### `test_hash_based_generator.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_embed_returns_deterministic_vector` | Same input → same output | Critical |
| `test_embed_returns_correct_dimension` | Vector has expected dimension | High |
| `test_embed_different_texts_different_vectors` | Different inputs differ | High |
| `test_embed_handles_empty_string` | Empty string handled | High |
| `test_embed_handles_unicode` | Unicode text handled | High |

### 4.4 Search Service (`src/search_service/`)

#### `test_grpc_clients.py` (search_service)

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_client_connects_to_embedding_service` | Establish connection | Critical |
| `test_client_handles_connection_failure` | Graceful error on failure | Critical |
| `test_client_retries_transient_errors` | Retry UNAVAILABLE errors | Critical |
| `test_client_respects_timeout` | Cancel slow requests | High |
| `test_client_reuses_channel` | Connection pooling works | Medium |

### 4.5 Ingestion API (`src/ingestion_api/`)

#### `test_kafka_client.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_publish_document_event_succeeds` | Publish to Kafka topic | Critical |
| `test_publish_validates_event_schema` | Reject invalid events | Critical |
| `test_publish_handles_broker_unavailable` | Graceful error on failure | Critical |
| `test_publish_retries_transient_errors` | Retry on transient failures | High |
| `test_publish_respects_timeout` | Don't block indefinitely | High |
| `test_client_connects_on_first_use` | Lazy connection | Medium |
| `test_client_health_check` | Health check works | High |

#### `test_minio_client.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_upload_document_succeeds` | Upload to MinIO bucket | Critical |
| `test_upload_creates_bucket_if_missing` | Auto-create bucket | High |
| `test_upload_handles_connection_error` | Graceful error on failure | Critical |
| `test_upload_validates_content_type` | Set correct content type | High |
| `test_download_document_succeeds` | Download from MinIO | Critical |
| `test_download_handles_not_found` | 404 handled gracefully | High |
| `test_delete_document_succeeds` | Delete from MinIO | High |
| `test_client_health_check` | Health check works | High |

### 4.6 Indexer (`src/indexer/`)

#### `test_config.py` (indexer)

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_config_loads_kafka_settings` | Load Kafka bootstrap servers | Critical |
| `test_config_loads_weaviate_settings` | Load Weaviate URL | Critical |
| `test_config_validates_batch_size` | Reject invalid batch size | High |
| `test_config_validates_consumer_group` | Reject empty group ID | High |

#### `test_grpc_clients.py` (indexer)

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_embedding_client_connects` | Connect to embedding service | Critical |
| `test_embedding_client_embeds_batch` | Batch embedding works | Critical |
| `test_embedding_client_handles_error` | Graceful error handling | Critical |

### 4.7 LLM Client (`src/llm/`)

#### `test_openai_client.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_generate_answer_succeeds` | Generate answer from context | Critical |
| `test_generate_handles_rate_limit` | Retry on 429 | Critical |
| `test_generate_handles_api_error` | Graceful error on failure | Critical |
| `test_generate_validates_prompt_length` | Reject too-long prompts | High |
| `test_generate_respects_max_tokens` | Response within token limit | High |
| `test_generate_uses_correct_model` | Correct model used | High |
| `test_generate_includes_system_prompt` | System prompt included | High |
| `test_client_health_check` | Health check works | High |

---

## 5. Integration Test Requirements

### 5.1 Embedding Service Integration

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_grpc_server_starts_and_responds` | Server starts, handles requests | Critical |
| `test_grpc_health_check_endpoint` | Health check returns status | Critical |
| `test_embed_request_response_cycle` | Full embed request works | Critical |
| `test_batch_embed_large_input` | Handle 100+ texts | High |
| `test_concurrent_requests` | Handle 10 concurrent requests | High |
| `test_server_graceful_shutdown` | Clean shutdown on SIGTERM | High |

### 5.2 Search Service Integration

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_grpc_server_starts_and_responds` | Server starts, handles requests | Critical |
| `test_search_with_mock_weaviate` | Search flow with mocked DB | Critical |
| `test_search_with_mock_embedding_service` | Search flow with mocked embeddings | Critical |
| `test_search_returns_sources` | Sources included in response | Critical |
| `test_health_check_reports_dependencies` | Health shows dependency status | High |

### 5.3 Search UI Integration

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_fastapi_starts_and_responds` | Server starts on port | Critical |
| `test_search_endpoint_calls_grpc` | API calls Search Service | Critical |
| `test_web_interface_renders` | HTML page renders | High |
| `test_api_returns_json` | JSON response format | Critical |
| `test_error_handling_returns_proper_status` | 4xx/5xx codes correct | High |

### 5.4 Ingestion API Integration

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_ingest_endpoint_accepts_document` | POST /ingest works | Critical |
| `test_ingest_stores_in_minio` | Document stored in MinIO | Critical |
| `test_ingest_publishes_to_kafka` | Event published to Kafka | Critical |
| `test_ingest_validates_content_type` | Reject invalid content types | High |
| `test_ingest_validates_file_size` | Reject oversized files | High |
| `test_health_endpoint` | Health check works | High |

### 5.5 Indexer Integration

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_consumer_processes_kafka_message` | Consume and process message | Critical |
| `test_processor_calls_embedding_service` | Get embeddings via gRPC | Critical |
| `test_processor_stores_in_weaviate` | Store vectors in Weaviate | Critical |
| `test_consumer_handles_malformed_message` | Bad messages don't crash | Critical |
| `test_consumer_commits_offset_after_success` | Offset management correct | High |
| `test_dead_letter_queue` | Failed messages to DLQ | High |

### 5.6 Pipeline Integration

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_indexing_pipeline_full_flow` | Document → chunks → vectors | Critical |
| `test_search_pipeline_full_flow` | Query → embeddings → results → answer | Critical |
| `test_pipeline_handles_empty_results` | Graceful empty response | High |
| `test_pipeline_handles_llm_error` | Graceful LLM failure | High |

---

## 6. End-to-End Test Requirements

### 6.1 Document Ingestion Flow

**Scenario: User uploads a document and it becomes searchable**

```gherkin
Given the cluster is running
And all services are healthy
When I POST a document to /ingest
Then the response status is 202 Accepted
And the document is stored in MinIO
And a Kafka event is published
And within 30 seconds the document is indexed in Weaviate
And I can search for content from the document
```

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_e2e_document_upload_to_searchable` | Full ingestion flow | Critical |
| `test_e2e_multiple_documents_ingestion` | Batch ingestion | High |
| `test_e2e_large_document_chunking` | Large doc split correctly | High |
| `test_e2e_duplicate_document_handling` | Duplicates detected | High |

### 6.2 Search Flow

**Scenario: User searches and gets an AI-generated answer**

```gherkin
Given documents have been indexed
When I POST a search query to /api/search
Then the response contains an answer
And the response contains source documents
And sources have relevance scores
And the answer is relevant to the query
```

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_e2e_search_returns_answer` | Search returns AI answer | Critical |
| `test_e2e_search_returns_sources` | Sources included | Critical |
| `test_e2e_search_no_results` | Graceful empty response | High |
| `test_e2e_search_special_characters` | Unicode, quotes handled | High |
| `test_e2e_hybrid_search_mode` | Hybrid search works | High |

### 6.3 Health Checks

**Scenario: System health is monitorable**

```gherkin
Given the cluster is running
When I GET /health from each service
Then each service reports its status
And dependency health is included
And degraded services show which dependency failed
```

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_e2e_all_services_healthy` | All services report healthy | Critical |
| `test_e2e_degraded_when_dependency_down` | Degraded status on failure | High |
| `test_e2e_liveness_probes` | K8s liveness probes work | Critical |
| `test_e2e_readiness_probes` | K8s readiness probes work | Critical |

### 6.4 Monitoring

**Scenario: Metrics are collected and visible**

```gherkin
Given the cluster is running
When I GET /metrics from each service
Then Prometheus format metrics are returned
And request counts are tracked
And latency histograms are present
And Grafana can display dashboards
```

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_e2e_prometheus_scrapes_metrics` | Prometheus collects metrics | High |
| `test_e2e_grafana_dashboards_load` | Dashboards display data | Medium |
| `test_e2e_metrics_include_request_count` | Request metrics present | High |
| `test_e2e_metrics_include_latency` | Latency metrics present | High |

---

## 7. Performance Test Requirements

### 7.1 Search Latency

| Test Case | Target | Priority |
|-----------|--------|----------|
| `test_search_p50_latency` | < 200ms | Critical |
| `test_search_p95_latency` | < 500ms | Critical |
| `test_search_p99_latency` | < 1000ms | High |
| `test_search_under_load_10_rps` | P95 < 500ms at 10 req/s | High |
| `test_search_under_load_50_rps` | P95 < 1000ms at 50 req/s | Medium |

### 7.2 Ingestion Throughput

| Test Case | Target | Priority |
|-----------|--------|----------|
| `test_ingestion_single_document` | < 100ms per doc | High |
| `test_ingestion_batch_100_documents` | < 5s total | High |
| `test_indexer_processing_rate` | > 10 docs/second | High |

### 7.3 Embedding Performance

| Test Case | Target | Priority |
|-----------|--------|----------|
| `test_embed_single_latency` | < 100ms | High |
| `test_embed_batch_100_latency` | < 2s | High |
| `test_embed_concurrent_requests` | Linear scaling to 10 concurrent | Medium |

### 7.4 Resource Limits

| Test Case | Target | Priority |
|-----------|--------|----------|
| `test_memory_usage_under_load` | < 1GB per service | High |
| `test_cpu_usage_under_load` | < 500m per service | High |
| `test_no_memory_leak_sustained_load` | Stable over 10 minutes | High |

---

## 8. Security Test Requirements

### 8.1 Input Validation

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_sql_injection_prevention` | SQL in queries rejected | Critical |
| `test_xss_prevention` | Script tags sanitized | Critical |
| `test_command_injection_prevention` | Shell metacharacters rejected | Critical |
| `test_path_traversal_prevention` | `../` in paths rejected | Critical |
| `test_oversized_input_rejection` | Large payloads rejected | High |
| `test_malformed_json_rejection` | Invalid JSON returns 400 | High |

### 8.2 Authentication & Authorization

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_api_requires_authentication` | Unauthenticated requests rejected | Critical* |
| `test_invalid_token_rejected` | Bad tokens return 401 | Critical* |
| `test_expired_token_rejected` | Expired tokens return 401 | Critical* |

*Note: Auth not implemented in dev environment - tests should be ready for production*

### 8.3 Data Protection

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_sensitive_data_not_logged` | API keys not in logs | Critical |
| `test_error_messages_not_leaky` | Stack traces not in responses | High |
| `test_credentials_not_in_response` | No secrets in API responses | Critical |

### 8.4 Static Analysis (Bandit)

| Check | Description | Priority |
|-------|-------------|----------|
| B101 | Assert used for security checks | Medium |
| B102 | exec() usage | Critical |
| B103 | set_bad_file_permissions | High |
| B104 | Binding to all interfaces | Medium |
| B105 | Hardcoded passwords | Critical |
| B106 | Hardcoded password in function argument | Critical |
| B107 | Hardcoded password default | Critical |
| B108 | Hardcoded temp directory | Medium |
| B110 | Try-except-pass | High |
| B112 | Try-except-continue | High |
| B201 | Flask debug mode | Critical |
| B301-B303 | Pickle/Marshal/MD5 usage | High |
| B311 | Random for crypto | Critical |
| B324 | Hashlib with insecure hash | High |
| B501-B503 | SSL verification disabled | Critical |
| B506 | Unsafe YAML load | Critical |
| B601-B602 | Shell injection | Critical |
| B608 | SQL injection | Critical |
| B701 | Jinja2 autoescape | Critical |

---

## 9. Test Infrastructure

### 9.1 Fixtures (conftest.py)

```python
# Required fixtures for all tests

@pytest.fixture
def mock_weaviate_client():
    """Mock Weaviate client for unit tests."""

@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer for unit tests."""

@pytest.fixture
def mock_minio_client():
    """Mock MinIO client for unit tests."""

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for unit tests."""

@pytest.fixture
def mock_grpc_channel():
    """Mock gRPC channel for unit tests."""

@pytest.fixture
def sample_document():
    """Sample document for testing."""

@pytest.fixture
def sample_embedding():
    """Sample embedding vector for testing."""

@pytest.fixture
async def running_cluster():
    """Running Kind cluster for integration tests."""

@pytest.fixture
async def deployed_services():
    """All services deployed for E2E tests."""
```

### 9.2 Test Markers

```python
# pytest markers for test categorization

pytest.mark.unit          # Fast, isolated unit tests
pytest.mark.integration   # Service boundary tests
pytest.mark.e2e           # End-to-end tests requiring cluster
pytest.mark.performance   # Performance/load tests
pytest.mark.security      # Security tests
pytest.mark.slow          # Tests taking > 5 seconds
pytest.mark.flaky         # Known flaky tests (should be fixed)
```

### 9.3 CI Configuration

```yaml
# Test stages in CI pipeline

stages:
  - lint:
      - ruff check
      - ruff format --check
      - mypy

  - security:
      - bandit -r src/

  - unit-tests:
      - pytest tests/unit/ -v --cov=src --cov-report=xml
      - coverage >= 90%

  - integration-tests:
      - pytest tests/integration/ -v
      - requires: mock services

  - e2e-tests:
      - pytest tests/e2e/ -v
      - requires: running cluster

  - performance-tests:
      - pytest tests/performance/ -v
      - requires: running cluster
      - only: scheduled/manual
```

---

## 10. Coverage Requirements

### 10.1 Line Coverage Targets

| Module | Minimum | Target |
|--------|---------|--------|
| `src/core/` | 95% | 100% |
| `src/common/` | 90% | 95% |
| `src/embedding_service/` | 85% | 90% |
| `src/search_service/` | 85% | 90% |
| `src/search_ui/` | 85% | 90% |
| `src/ingestion_api/` | 85% | 90% |
| `src/indexer/` | 85% | 90% |
| `src/pipelines/` | 90% | 95% |
| `src/retrievers/` | 90% | 95% |
| `src/llm/` | 85% | 90% |
| **Overall** | **90%** | **95%** |

### 10.2 Branch Coverage Targets

| Category | Minimum |
|----------|---------|
| Error handling paths | 100% |
| Input validation | 100% |
| Configuration loading | 100% |
| Health check logic | 100% |
| gRPC error handling | 100% |
| All other branches | 85% |

### 10.3 Coverage Enforcement

```toml
# pyproject.toml additions

[tool.coverage.report]
fail_under = 90
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
]
```

---

## 11. Certification Checklist

### 11.1 Pre-Release Certification

- [ ] **All unit tests pass** (243+ tests)
- [ ] **All integration tests pass** (20+ tests)
- [ ] **All E2E tests pass** (10+ tests)
- [ ] **Line coverage >= 90%**
- [ ] **Branch coverage >= 85%**
- [ ] **Zero Bandit critical/high issues**
- [ ] **Zero mypy errors**
- [ ] **Zero ruff errors**
- [ ] **All health checks pass in cluster**
- [ ] **P95 search latency < 500ms**
- [ ] **Documentation complete**

### 11.2 Release Sign-Off

| Item | Owner | Date | Signature |
|------|-------|------|-----------|
| Unit Tests Complete | | | |
| Integration Tests Complete | | | |
| E2E Tests Complete | | | |
| Security Review Complete | | | |
| Performance Benchmarks Met | | | |
| Documentation Review | | | |
| Final Approval | | | |

---

## 12. Implementation Priority

### Phase 1: Critical Unit Tests (Week 1)

1. `tests/unit/core/test_document.py`
2. `tests/unit/core/test_errors.py`
3. `tests/unit/llm/test_openai_client.py`
4. `tests/unit/common/test_grpc_utils.py`
5. `tests/unit/common/test_metrics.py`

### Phase 2: Embedding & Generator Tests (Week 1-2)

6. `tests/unit/embedding_service/generators/test_factory.py`
7. `tests/unit/embedding_service/generators/test_openai_generator.py`
8. `tests/unit/embedding_service/generators/test_hash_based_generator.py`
9. `tests/unit/embedding_service/test_config.py`

### Phase 3: Service Client Tests (Week 2)

10. `tests/unit/search_service/test_grpc_clients.py`
11. `tests/unit/indexer/test_grpc_clients.py`
12. `tests/unit/ingestion_api/test_kafka_client.py`
13. `tests/unit/ingestion_api/test_minio_client.py`

### Phase 4: Integration Tests (Week 2-3)

14. `tests/integration/test_embedding_integration.py`
15. `tests/integration/test_search_integration.py`
16. `tests/integration/test_ingestion_integration.py`
17. `tests/integration/test_indexer_integration.py`

### Phase 5: E2E & Performance Tests (Week 3)

18. `tests/e2e/test_document_ingestion_flow.py`
19. `tests/e2e/test_search_flow.py`
20. `tests/e2e/test_health_checks.py`
21. `tests/performance/test_search_latency.py`
22. `tests/performance/test_ingestion_throughput.py`

### Phase 6: Security Tests (Week 3-4)

23. `tests/security/test_input_validation.py`
24. `tests/security/test_injection_prevention.py`

---

## Appendix A: Test File Templates

### Unit Test Template

```python
"""Unit tests for <module_name>.

Tests cover:
- <feature_1>
- <feature_2>
- Error handling
"""

import pytest
from unittest.mock import Mock, patch

from src.<module> import <Class>


class Test<Class>:
    """Tests for <Class>."""

    @pytest.fixture
    def subject(self):
        """Create test subject with mocked dependencies."""
        return <Class>(...)

    def test_<method>_<scenario>_<expected>(self, subject):
        """Tests that <method> <expected> when <scenario>."""
        # Arrange
        ...

        # Act
        result = subject.<method>(...)

        # Assert
        assert result == expected
```

### Integration Test Template

```python
"""Integration tests for <service_name>.

Tests verify:
- Service starts correctly
- External dependencies are called
- Error handling across boundaries
"""

import pytest


@pytest.mark.integration
class Test<Service>Integration:
    """Integration tests for <Service>."""

    @pytest.fixture
    async def running_service(self):
        """Start service with mocked dependencies."""
        ...

    async def test_<operation>_succeeds(self, running_service):
        """Tests that <operation> completes successfully."""
        ...
```

---

## Appendix B: Coverage Gap Summary

### ✅ Implemented Test Files (December 2025)

| Source File | Test File | Status |
|-------------|-----------|--------|
| `src/core/document.py` | `tests/unit/core/test_document.py` | ✅ Created |
| `src/core/errors.py` | `tests/unit/core/test_errors.py` | ✅ Created |
| `src/core/interfaces.py` | `tests/unit/core/test_interfaces.py` | ✅ Created |
| `src/common/grpc_utils.py` | `tests/unit/common/test_grpc_utils.py` | ✅ Created |
| `src/common/metrics.py` | `tests/unit/common/test_metrics.py` | ✅ Created |
| `src/llm/openai_client.py` | `tests/unit/llm/test_openai_client.py` | ✅ Created |
| `src/embedding_service/generators/factory.py` | `tests/unit/embedding_service/generators/test_factory.py` | ✅ Created |
| `src/embedding_service/generators/openai_generator.py` | `tests/unit/embedding_service/generators/test_openai_generator.py` | ✅ Created |
| `src/embedding_service/generators/hash_based_generator.py` | `tests/unit/embedding_service/generators/test_hash_based_generator.py` | ✅ Created |
| `src/search_service/grpc_clients.py` | `tests/unit/search_service/test_grpc_clients.py` | ✅ Created |
| `src/ingestion_api/kafka_client.py` | `tests/unit/ingestion_api/test_kafka_client.py` | ✅ Created |
| `src/ingestion_api/minio_client.py` | `tests/unit/ingestion_api/test_minio_client.py` | ✅ Created |
| `src/indexer/grpc_clients.py` | `tests/unit/indexer/test_grpc_clients.py` | ✅ Created |

**Completed: 13/16 test files**

### Remaining Test Files

| Source File | Test File | Priority |
|-------------|-----------|----------|
| `src/embedding_service/config.py` | `tests/unit/embedding_service/test_config.py` | Low |
| `src/ingestion_api/config.py` | `tests/unit/ingestion_api/test_config.py` | Low |
| `src/indexer/config.py` | `tests/unit/indexer/test_config.py` | Low |

---

## Appendix C: Test Implementation Notes

### gRPC Error Mocking Pattern

When testing gRPC clients that need to handle `grpc.RpcError`, do NOT use `MagicMock(spec=grpc.RpcError)`.
Instead, create a custom exception class:

```python
class MockRpcError(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.UNAVAILABLE

    def details(self):
        return "Service unavailable"

# Usage
client.stub.Method.side_effect = MockRpcError()
```

This pattern is required because `MagicMock` objects cannot be raised as exceptions.

---

*Document generated for X-RAG project certification.*
*Last updated: December 2025*
