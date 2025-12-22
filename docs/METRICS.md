# Prometheus Metrics Reference

This document catalogs all Prometheus metrics exposed by X-RAG services, including their types, labels, and recommended PromQL queries for SLO monitoring.

## Overview

All X-RAG services expose metrics following the **Four Golden Signals**:
- **Latency**: How long requests take (Histograms)
- **Traffic**: How many requests (Counters)
- **Errors**: How many failures (Counters)
- **Saturation**: How "full" the service is (Gauges)

### Time Units

All duration metrics are stored in **seconds** (Prometheus convention). Histogram buckets are designed with millisecond precision:
- 5ms = 0.005s
- 100ms = 0.1s
- 1s = 1.0s

To display in milliseconds in Grafana, multiply by 1000 in your PromQL queries.

### Bucket Configurations

| Type | Target p99 | Buckets (seconds) |
|------|------------|-------------------|
| FAST | < 100ms | 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0 |
| MEDIUM | < 500ms | 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0 |
| SLOW | < 30s | 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0 |
| BATCH | < 5s | 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0 |

---

## Search Service

**Port**: 8080 (metrics), 50052 (gRPC)

### Latency Metrics

| Metric | Type | Labels | Buckets | Description |
|--------|------|--------|---------|-------------|
| `search_service_request_duration_seconds` | Histogram | method | SLOW | Total request duration |
| `search_service_embedding_duration_seconds` | Histogram | - | FAST | Query embedding generation |
| `search_service_retrieval_duration_seconds` | Histogram | mode | MEDIUM | Weaviate document retrieval |
| `search_service_llm_generation_duration_seconds` | Histogram | - | SLOW | LLM answer generation |

### Traffic Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `search_service_requests_total` | Counter | method, status | Total requests |

### Error Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `search_service_errors_total` | Counter | method, error_type | Error count by type |

### Saturation Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `search_service_active_requests` | Gauge | method | Currently active requests |

---

## Embedding Service

**Port**: 8080 (metrics), 50051 (gRPC)

### Latency Metrics

| Metric | Type | Labels | Buckets | Description |
|--------|------|--------|---------|-------------|
| `embedding_service_request_duration_seconds` | Histogram | method | FAST | Total request duration |
| `embedding_service_backend_duration_seconds` | Histogram | model | FAST | Backend embedding generation |
| `embedding_service_batch_size` | Histogram | - | 1-1000 | Batch size distribution |

### Traffic Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `embedding_service_requests_total` | Counter | method, status | Total requests |
| `embedding_service_embeddings_total` | Counter | model | Total embeddings generated |

### Error Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `embedding_service_errors_total` | Counter | method, error_type | Error count by type |

### Saturation Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `embedding_service_active_requests` | Gauge | method | Currently active requests |

---

## Indexer

**Port**: 8081 (metrics), 8080 (health)

### Latency Metrics

| Metric | Type | Labels | Buckets | Description |
|--------|------|--------|---------|-------------|
| `indexer_processing_duration_seconds` | Histogram | namespace | BATCH | Total document processing |
| `indexer_kafka_poll_duration_seconds` | Histogram | - | BATCH | Kafka message polling |
| `indexer_minio_load_duration_seconds` | Histogram | - | MEDIUM | MinIO document loading |
| `indexer_text_cleaning_duration_seconds` | Histogram | - | FAST | Text cleaning |
| `indexer_text_splitting_duration_seconds` | Histogram | - | FAST | Text splitting |
| `indexer_embedding_duration_seconds` | Histogram | - | MEDIUM | Embedding generation |
| `indexer_weaviate_insert_duration_seconds` | Histogram | - | MEDIUM | Weaviate batch insert |
| `indexer_duplicate_check_duration_seconds` | Histogram | - | FAST | Duplicate detection |

### Traffic Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `indexer_documents_processed_total` | Counter | status, namespace | Documents processed |
| `indexer_chunks_created_total` | Counter | namespace | Chunks created |
| `indexer_kafka_messages_total` | Counter | topic | Kafka messages consumed |

### Error Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `indexer_errors_total` | Counter | stage, error_type | Error count by stage |

### Saturation Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `indexer_active_documents` | Gauge | - | Documents being processed |
| `indexer_kafka_lag` | Gauge | partition | Consumer lag |

---

## Ingestion API

**Port**: 8080 (metrics), 8082 (HTTP)

### Latency Metrics

| Metric | Type | Labels | Buckets | Description |
|--------|------|--------|---------|-------------|
| `ingestion_duration_seconds` | Histogram | operation | MEDIUM | Total request duration |
| `ingestion_minio_upload_duration_seconds` | Histogram | - | MEDIUM | MinIO upload |
| `ingestion_kafka_publish_duration_seconds` | Histogram | - | FAST | Kafka publish |
| `ingestion_document_size_bytes` | Histogram | - | 1KB-100MB | Document size distribution |

### Traffic Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ingestion_requests_total` | Counter | status, namespace | Total requests |

### Error Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ingestion_errors_total` | Counter | operation, error_type | Error count by operation |

### Saturation Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ingestion_active_requests` | Gauge | - | Currently active requests |

---

## Search UI

**Port**: 9091 (metrics), 8080 (HTTP)

### Latency Metrics

| Metric | Type | Labels | Buckets | Description |
|--------|------|--------|---------|-------------|
| `search_ui_duration_seconds` | Histogram | operation | SLOW | Total request duration |
| `search_ui_grpc_call_duration_seconds` | Histogram | method | SLOW | gRPC call to Search Service |
| `search_ui_sources_returned` | Histogram | - | 0-50 | Sources per search |

### Traffic Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `search_ui_requests_total` | Counter | status, mode | Total requests |

### Error Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `search_ui_errors_total` | Counter | operation, error_type | Error count by operation |

### Saturation Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `search_ui_active_requests` | Gauge | - | Currently active requests |

---

## PromQL Examples

### Latency Percentiles

```promql
# p50 latency for search (milliseconds)
histogram_quantile(0.50,
  sum(rate(search_service_request_duration_seconds_bucket{method="Search"}[5m])) by (le)
) * 1000

# p95 latency for search (milliseconds)
histogram_quantile(0.95,
  sum(rate(search_service_request_duration_seconds_bucket{method="Search"}[5m])) by (le)
) * 1000

# p99 latency for search (milliseconds)
histogram_quantile(0.99,
  sum(rate(search_service_request_duration_seconds_bucket{method="Search"}[5m])) by (le)
) * 1000
```

### Availability (Success Rate)

```promql
# Search service availability (%)
sum(rate(search_service_requests_total{status="success"}[5m]))
/ sum(rate(search_service_requests_total[5m])) * 100

# Embedding service availability (%)
sum(rate(embedding_service_requests_total{status="success"}[5m]))
/ sum(rate(embedding_service_requests_total[5m])) * 100
```

### Error Rate

```promql
# Search service error rate (%)
sum(rate(search_service_requests_total{status="error"}[5m]))
/ sum(rate(search_service_requests_total[5m])) * 100

# Errors by type
sum by (error_type) (rate(search_service_errors_total[5m]))
```

### Throughput

```promql
# Search requests per second
sum(rate(search_service_requests_total[5m]))

# Documents indexed per second
sum(rate(indexer_documents_processed_total{status="success"}[5m]))

# Embeddings generated per second
sum(rate(embedding_service_embeddings_total[5m]))
```

### SLO Compliance

```promql
# % of search requests under 5 seconds
sum(rate(search_service_request_duration_seconds_bucket{method="Search",le="5.0"}[5m]))
/ sum(rate(search_service_request_duration_seconds_count{method="Search"}[5m])) * 100

# % of embedding requests under 100ms
sum(rate(embedding_service_request_duration_seconds_bucket{method="Embed",le="0.1"}[5m]))
/ sum(rate(embedding_service_request_duration_seconds_count{method="Embed"}[5m])) * 100
```

### Component Breakdown

```promql
# Average time spent in each search stage (seconds)
sum(rate(search_service_embedding_duration_seconds_sum[5m]))
/ sum(rate(search_service_embedding_duration_seconds_count[5m]))

sum(rate(search_service_retrieval_duration_seconds_sum[5m]))
/ sum(rate(search_service_retrieval_duration_seconds_count[5m]))

sum(rate(search_service_llm_generation_duration_seconds_sum[5m]))
/ sum(rate(search_service_llm_generation_duration_seconds_count[5m]))
```

---

## Alerting Rules

Example Prometheus alerting rules:

```yaml
groups:
  - name: x-rag-slos
    rules:
      - alert: HighSearchLatency
        expr: |
          histogram_quantile(0.99,
            sum(rate(search_service_request_duration_seconds_bucket{method="Search"}[5m])) by (le)
          ) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Search p99 latency exceeds 5 seconds"

      - alert: HighErrorRate
        expr: |
          sum(rate(search_service_requests_total{status="error"}[5m]))
          / sum(rate(search_service_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Search error rate exceeds 5%"

      - alert: EmbeddingServiceDown
        expr: |
          sum(rate(embedding_service_requests_total[1m])) == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Embedding service not receiving requests"
```

---

## Label Reference

| Label | Values | Description |
|-------|--------|-------------|
| `method` | Search, Embed, EmbedBatch, HealthCheck, ingest | Operation name |
| `status` | success, error | Request outcome |
| `error_type` | ValueError, TimeoutError, etc. | Exception class name |
| `mode` | vector, bm25, hybrid | Search mode |
| `namespace` | user-defined (required) | Document namespace |
| `model` | text-embedding-3-small, etc. | Embedding model |
| `stage` | load, clean, split, embed, insert | Indexer pipeline stage |
| `operation` | search, ingest | API operation |

---

## Testing Plan

This section describes how to verify metrics are correctly implemented and exposed.

### Unit Tests

Unit tests verify metrics are recorded correctly without requiring a running cluster.

```bash
# Run all metrics tests
uv run pytest tests/unit/common/test_metrics*.py -v

# Run specific test classes
uv run pytest tests/unit/common/test_metrics_integration.py::TestMetricsRecording -v
uv run pytest tests/unit/common/test_metrics_integration.py::TestBucketConfigCorrectness -v
```

**Key tests:**
- `test_track_latency_records_correct_bucket`: Verifies timing is recorded in correct histogram bucket
- `test_labeled_histogram_records_per_label`: Verifies labels work correctly
- `test_fast_operations_use_millisecond_precision`: Verifies sub-millisecond precision
- `test_track_latency_records_on_exception`: Verifies metrics record even on errors

### Integration Testing with a Running Cluster

After deploying to Kubernetes, verify metrics are exposed correctly.

#### 1. Port-forward to each service's metrics endpoint

```bash
# Search Service (port 8080)
kubectl port-forward svc/search-service 9090:8080

# Embedding Service (port 8080)
kubectl port-forward svc/embedding-service 9091:8080

# Indexer (port 8081)
kubectl port-forward svc/indexer 9092:8081

# Ingestion API (port 8080)
kubectl port-forward svc/ingestion-api 9093:8080

# Search UI (port 9091)
kubectl port-forward svc/search-ui 9094:9091
```

#### 2. Verify metrics are exposed

```bash
# Check Search Service metrics
curl -s http://localhost:9090/metrics | grep search_service

# Expected output should include:
# search_service_request_duration_seconds_bucket{...}
# search_service_requests_total{...}
# search_service_errors_total{...}
# search_service_active_requests{...}
```

#### 3. Generate test traffic and verify metrics change

```bash
# Send a search request
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "namespace": "my-docs"}'

# Check that metrics were recorded
curl -s http://localhost:9090/metrics | grep search_service_requests_total
# Should show count > 0
```

### Querying Prometheus

Once Prometheus is scraping metrics, use these queries to verify the implementation.

#### Verify Metrics Exist

```promql
# List all search service metrics
{__name__=~"search_service_.*"}

# List all histogram bucket metrics
{__name__=~".*_bucket"}

# Count metric series per service
count by (__name__) ({__name__=~"search_service_.*"})
count by (__name__) ({__name__=~"embedding_service_.*"})
count by (__name__) ({__name__=~"indexer_.*"})
count by (__name__) ({__name__=~"ingestion_.*"})
count by (__name__) ({__name__=~"search_ui_.*"})
```

#### Verify Histograms Have Correct Buckets

```promql
# Show bucket boundaries for search request duration
search_service_request_duration_seconds_bucket

# Should show buckets: le="0.1", le="0.25", le="0.5", le="1.0", le="2.5", le="5.0", etc.
```

#### Verify Labels Are Populated

```promql
# Check methods being tracked
count by (method) (search_service_requests_total)

# Check status values
count by (status) (search_service_requests_total)

# Check namespaces in indexer
count by (namespace) (indexer_documents_processed_total)
```

#### Test Latency Percentiles

```promql
# Verify p50, p95, p99 queries work
histogram_quantile(0.50, rate(search_service_request_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(search_service_request_duration_seconds_bucket[5m]))
histogram_quantile(0.99, rate(search_service_request_duration_seconds_bucket[5m]))
```

### Validation Checklist

Run through this checklist for each service after deployment:

| Check | Query/Command | Expected Result |
|-------|---------------|-----------------|
| Metrics endpoint accessible | `curl http://<service>:PORT/metrics` | 200 OK with Prometheus format |
| Histogram has `_bucket` metrics | `grep _bucket` output | Multiple bucket lines per histogram |
| Histogram has `_count` metrics | `grep _count` output | Count metric for each histogram |
| Histogram has `_sum` metrics | `grep _sum` output | Sum metric for each histogram |
| Counter increments on request | Query before/after request | Count increases by 1 |
| Gauge reflects active requests | Watch during request | Gauge goes up then down |
| Labels present | `grep {method=` output | Labels appear on metrics |
| Buckets match config | Check le values | Match BucketConfig values |

---

## Grafana Dashboards

X-RAG includes a pre-built Grafana dashboard that is automatically provisioned when deploying the monitoring stack.

### Accessing the Dashboard

```bash
# Open Grafana in browser
make open-grafana

# Or manually port-forward
kubectl port-forward svc/grafana 3000:3000 -n monitoring
# Then open http://localhost:3000
```

**Credentials:** admin / admin

**Dashboard location:** Dashboards > Browse > X-RAG folder > X-RAG Overview

### Dashboard Panels

The X-RAG Overview dashboard includes 22 panels organized into sections:

| Section | Panels |
|---------|--------|
| **Overview** | Availability (%), p99 Latency, Throughput (req/s), Active Requests |
| **Search Service** | Latency Distribution (p50/p95/p99), Request Rate by status, Component Latencies (Embedding/Retrieval/LLM), Error Rate by type |
| **Embedding Service** | Latency by Method, Request Rate |
| **Indexer** | Throughput (docs & chunks/s), Pipeline Latencies (MinIO/Cleaning/Splitting/Embedding/Weaviate) |
| **Ingestion API** | Request Rate, Component Latencies (MinIO Upload/Kafka Publish) |
| **Search UI** | Request Rate by mode, gRPC Call Latency |

### Dashboard Provisioning

Dashboards are auto-provisioned via Kubernetes ConfigMaps, meaning they survive pod restarts and cluster recreations.

**How it works:**
1. Dashboard JSON files are stored in `infra/k8s/monitoring/grafana-dashboards/`
2. The `deploy-monitoring.sh` script creates a ConfigMap from these files
3. Grafana mounts the ConfigMap and loads dashboards on startup

**To add or modify dashboards:**

```bash
# 1. Edit or add JSON files in the dashboards directory
vim infra/k8s/monitoring/grafana-dashboards/xrag-overview.json

# 2. Regenerate the ConfigMap and restart Grafana
./scripts/generate-grafana-dashboards-configmap.sh

# Or redeploy the full monitoring stack
./scripts/deploy-monitoring.sh
```

**Exporting dashboards from Grafana UI:**
1. Make changes in Grafana UI
2. Go to Dashboard Settings > JSON Model
3. Copy the JSON and save to `infra/k8s/monitoring/grafana-dashboards/`
4. Run the regenerate script

### Grafana Dashboard Verification

After importing dashboards, verify:

1. **Panel loads without errors**: No "No data" or query errors
2. **Percentile graphs work**: Lines appear on p50/p95/p99 panels
3. **Throughput shows requests/sec**: Not cumulative counts
4. **Error rate is percentage**: 0-100% range, not raw counts
5. **Labels filter correctly**: Dropdown filters affect all panels

### Load Testing Verification

During load tests, verify metrics behavior:

```bash
# Generate load with hey or wrk
hey -n 1000 -c 10 http://localhost:8080/api/search

# While load is running, check:
# 1. Active requests gauge should be > 0
curl -s http://localhost:9090/metrics | grep active_requests

# 2. Request count should increase rapidly
watch -n 1 'curl -s http://localhost:9090/metrics | grep requests_total'

# 3. Histogram buckets should fill up
curl -s http://localhost:9090/metrics | grep request_duration_seconds_bucket
```

### Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| No metrics at /metrics | App not registering metrics | Check import of metrics module |
| Missing labels | Label not passed to metric | Check track_latency calls |
| Wrong bucket boundaries | Using wrong BucketConfig | Verify OperationType |
| Histogram shows NaN | No observations yet | Generate traffic first |
| Counter not incrementing | Metric not called on success path | Check instrumentation points |
