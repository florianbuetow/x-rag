# X-RAG Observability Guide

This document describes the three pillars of observability in X-RAG: **Tracing**, **Metrics**, and **Logs**. Each pillar provides a different view into system behavior, and together they enable comprehensive debugging, performance analysis, and monitoring.

## Table of Contents

1. [Overview](#overview)
2. [Distributed Tracing](#distributed-tracing)
3. [Metrics](#metrics)
4. [Logs](#logs)
5. [Correlation Between Signals](#correlation-between-signals)
6. [Accessing Observability Data](#accessing-observability-data)

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         X-RAG Observability Stack                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│   │   TRACING   │    │   METRICS   │    │    LOGS     │                    │
│   │             │    │             │    │             │                    │
│   │  "What      │    │  "How much  │    │  "What      │                    │
│   │   happened  │    │   and how   │    │   exactly   │                    │
│   │   across    │    │   fast?"    │    │   happened?"│                    │
│   │   services?"│    │             │    │             │                    │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                    │
│          │                  │                  │                            │
│          ▼                  ▼                  ▼                            │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│   │    Tempo    │    │ Prometheus  │    │    Loki     │                    │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                    │
│          │                  │                  │                            │
│          └──────────────────┼──────────────────┘                            │
│                             ▼                                               │
│                      ┌─────────────┐                                        │
│                      │   Grafana   │                                        │
│                      │  (Unified   │                                        │
│                      │    View)    │                                        │
│                      └─────────────┘                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Signal | Purpose | Storage | Query Language |
|--------|---------|---------|----------------|
| Tracing | Request flow across services | Tempo | TraceQL |
| Metrics | Quantitative measurements over time | Prometheus | PromQL |
| Logs | Detailed event records | Loki | LogQL |

---

## Distributed Tracing

### What is Distributed Tracing?

Distributed tracing tracks a request as it flows through multiple services. Each operation creates a **span**, and all spans for a single request share a **trace ID**, forming a tree structure.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRACING PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPLICATION LAYER                                                          │
│  ─────────────────                                                          │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  search-ui   │  │search-service│  │embed-service │  │   indexer    │   │
│  │              │  │              │  │              │  │              │   │
│  │ FastAPI      │  │ gRPC Server  │  │ gRPC Server  │  │ Kafka        │   │
│  │ Instrumentor │  │ Instrumentor │  │ Instrumentor │  │ Consumer     │   │
│  │              │  │              │  │              │  │              │   │
│  │ gRPC Client  │  │ gRPC Client  │  │ OpenAI       │  │ gRPC Client  │   │
│  │ Instrumentor │  │ Instrumentor │  │ Instrumentor │  │ Instrumentor │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │            │
│         └─────────────────┴─────────────────┴─────────────────┘            │
│                                    │                                        │
│                                    ▼                                        │
│  OPENTELEMETRY SDK                                                          │
│  ─────────────────                                                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        TracerProvider                                │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │ BatchSpanProcessor                                             │  │   │
│  │  │  • Buffers spans in memory (max 2048)                         │  │   │
│  │  │  • Exports every 5 seconds                                    │  │   │
│  │  │  • Batches up to 512 spans per export                         │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │ OTLPSpanExporter (gRPC)                                       │  │   │
│  │  │  • Endpoint: alloy.monitoring:4317                            │  │   │
│  │  │  • Protocol: OTLP/gRPC                                        │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ OTLP/gRPC (port 4317)                  │
│                                    ▼                                        │
│  COLLECTION LAYER                                                           │
│  ────────────────                                                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Grafana Alloy                                 │   │
│  │                                                                      │   │
│  │  otelcol.receiver.otlp ──► otelcol.processor.batch ──► otelcol.     │   │
│  │       (receive)                  (batch)               exporter.otlp│   │
│  │                                                         (forward)   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ OTLP/gRPC (port 4317)                  │
│                                    ▼                                        │
│  STORAGE LAYER                                                              │
│  ─────────────                                                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Grafana Tempo                                 │   │
│  │                                                                      │   │
│  │  • Receives spans via OTLP                                          │   │
│  │  • Correlates spans by trace_id                                     │   │
│  │  • Builds trace tree from parent_span_id                            │   │
│  │  • Query API: http://tempo.monitoring:3200                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Trace Context Propagation

When Service A calls Service B, the trace context must be propagated so spans are linked:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TRACE CONTEXT PROPAGATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  HTTP (W3C Trace Context)                                                   │
│  ─────────────────────────                                                  │
│                                                                             │
│    POST /api/search HTTP/1.1                                                │
│    Host: search-ui:8080                                                     │
│    traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01    │
│                 │   │                                │                 │    │
│                 │   │                                │                 │    │
│                 │   │                                │                 │    │
│             version │                           span_id            flags    │
│                     │                                                       │
│                 trace_id (32 hex = 128 bits)                                │
│                                                                             │
│                                                                             │
│  gRPC (Metadata)                                                            │
│  ───────────────                                                            │
│                                                                             │
│    Metadata: [                                                              │
│      ("traceparent", "00-0af7651916cd43dd8448eb211c80319c-b7ad...-01"),    │
│      ("content-type", "application/grpc"),                                  │
│    ]                                                                        │
│                                                                             │
│    Note: gRPC metadata maps to HTTP/2 headers internally                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Example Trace Structure

A search request creates the following trace tree:

```
Trace ID: 0af7651916cd43dd8448eb211c80319c

├─ [search-ui] POST /api/search (300ms)
│   │
│   ├─ [search-ui] /xrag.search.SearchService/Search (gRPC client) (280ms)
│   │   │
│   │   ├─ [search-service] /xrag.search.SearchService/Search (gRPC server) (275ms)
│   │   │   │
│   │   │   ├─ [search-service] embedding.generate (50ms)
│   │   │   │   │
│   │   │   │   └─ [embedding-service] /xrag.embedding.EmbeddingService/Embed (45ms)
│   │   │   │       │
│   │   │   │       └─ [embedding-service] openai.embeddings (40ms)
│   │   │   │           │
│   │   │   │           └─ [embedding-service] POST https://api.openai.com (35ms)
│   │   │   │
│   │   │   ├─ [search-service] vector_search.query (100ms)
│   │   │   │
│   │   │   └─ [search-service] llm.rag_completion (120ms)
│   │   │       │
│   │   │       └─ [search-service] openai.chat (115ms)
```

### Instrumentation in X-RAG

| Instrumentor | Purpose | Location |
|--------------|---------|----------|
| `FastAPIInstrumentor` | HTTP server spans | search-ui, ingestion-api |
| `GrpcAioInstrumentorServer` | gRPC server spans | search-service, embedding-service |
| `GrpcAioInstrumentorClient` | gRPC client spans + context propagation | All services |
| `OpenAIInstrumentor` | OpenAI API calls | embedding-service, search-service |
| `HTTPXClientInstrumentor` | HTTP client calls | All services |
| Manual spans | Custom operations | `trace_storage_operation`, `trace_database_operation`, etc. |

### Key Files

- `src/common/tracing.py` - TracerProvider initialization
- `src/common/tracing_utils.py` - Manual span context managers
- `src/*/grpc_clients.py` - gRPC client instrumentation
- `infra/k8s/monitoring/alloy-config.yaml` - Alloy trace pipeline
- `infra/k8s/monitoring/tempo.yaml` - Tempo configuration

---

## Metrics

### What are Metrics?

Metrics are numerical measurements collected over time. They answer questions like "How many requests per second?" and "What's the 99th percentile latency?"

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           METRICS PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPLICATION LAYER (Push via OTLP)                                          │
│  ─────────────────────────────────                                          │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  search-ui   │  │search-service│  │embed-service │  │   indexer    │   │
│  │              │  │              │  │              │  │              │   │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │   │
│  │ │OTel Meter│ │  │ │OTel Meter│ │  │ │OTel Meter│ │  │ │OTel Meter│ │   │
│  │ │Provider  │ │  │ │Provider  │ │  │ │Provider  │ │  │ │Provider  │ │   │
│  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │   │
│  │      │       │  │      │       │  │      │       │  │      │       │   │
│  │      ▼       │  │      ▼       │  │      ▼       │  │      ▼       │   │
│  │ OTLPExporter │  │ OTLPExporter │  │ OTLPExporter │  │ OTLPExporter │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │            │
│         └─────────────────┴─────────────────┴─────────────────┘            │
│                                    │                                        │
│                                    │ OTLP/gRPC (port 4317)                  │
│                                    ▼                                        │
│  COLLECTION LAYER                                                           │
│  ────────────────                                                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Grafana Alloy                                 │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ otelcol.        │  │ prometheus.     │  │ prometheus.         │  │   │
│  │  │ receiver.otlp   │  │ scrape          │  │ scrape              │  │   │
│  │  │ (app metrics)   │  │ (kubelet)       │  │ (kube-state-metrics)│  │   │
│  │  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │   │
│  │           │                    │                      │              │   │
│  │           ▼                    │                      │              │   │
│  │  otelcol.exporter.prometheus   │                      │              │   │
│  │           │                    │                      │              │   │
│  │           └────────────────────┴──────────────────────┘              │   │
│  │                                │                                     │   │
│  │                                ▼                                     │   │
│  │                    prometheus.remote_write                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ remote_write                           │
│                                    ▼                                        │
│  STORAGE LAYER                                                              │
│  ─────────────                                                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Prometheus                                    │   │
│  │                                                                      │   │
│  │  • TSDB (Time Series Database)                                      │   │
│  │  • 15-day retention (configurable)                                  │   │
│  │  • PromQL query engine                                              │   │
│  │  • API: http://prometheus.monitoring:9090                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**How metrics flow:**

1. **Application metrics** → Services use OpenTelemetry SDK to push metrics via OTLP to Alloy (port 4317). Alloy converts OTLP to Prometheus format and remote-writes to Prometheus.

2. **System metrics** → Alloy scrapes kubelet `/metrics/resource`, `/metrics/cadvisor`, and kube-state-metrics, then remote-writes to Prometheus.

### Metric Types

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROMETHEUS METRIC TYPES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  COUNTER                                                                    │
│  ───────                                                                    │
│  • Monotonically increasing value                                           │
│  • Only goes up (or resets to zero)                                         │
│  • Example: requests_total, errors_total                                    │
│                                                                             │
│    Value                                                                    │
│      │     ╭──────────────────────────────                                  │
│      │    ╱                                                                 │
│      │   ╱                                                                  │
│      │  ╱                                                                   │
│      │ ╱                                                                    │
│      │╱                                                                     │
│      └──────────────────────────────────► Time                              │
│                                                                             │
│                                                                             │
│  GAUGE                                                                      │
│  ─────                                                                      │
│  • Current value at a point in time                                         │
│  • Can go up or down                                                        │
│  • Example: active_requests, temperature                                    │
│                                                                             │
│    Value                                                                    │
│      │      ╱╲      ╱╲                                                      │
│      │     ╱  ╲    ╱  ╲    ╱╲                                               │
│      │    ╱    ╲  ╱    ╲  ╱  ╲                                              │
│      │   ╱      ╲╱      ╲╱    ╲                                             │
│      │  ╱                      ╲                                            │
│      │ ╱                        ╲                                           │
│      └──────────────────────────────────► Time                              │
│                                                                             │
│                                                                             │
│  HISTOGRAM                                                                  │
│  ─────────                                                                  │
│  • Distribution of values in buckets                                        │
│  • Enables percentile calculations (p50, p95, p99)                          │
│  • Example: request_duration_seconds                                        │
│                                                                             │
│    Count                                                                    │
│      │                                                                      │
│      │  ████                                                                │
│      │  ████ ████                                                           │
│      │  ████ ████ ████                                                      │
│      │  ████ ████ ████ ████                                                 │
│      │  ████ ████ ████ ████ ████                                            │
│      └────────────────────────────► Bucket (latency)                        │
│        10ms 50ms 100ms 500ms 1s                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Metrics Exposed by X-RAG Services

| Service | Metric | Type | Description |
|---------|--------|------|-------------|
| search-ui | `search_ui_request_duration_seconds` | Histogram | HTTP request latency |
| search-ui | `search_ui_requests_total` | Counter | Total requests by status |
| search-ui | `search_ui_active_requests` | Gauge | Currently processing |
| search-service | `search_service_request_duration_seconds` | Histogram | gRPC request latency |
| search-service | `search_service_retrieval_duration_seconds` | Histogram | Weaviate query time |
| embedding-service | `embedding_service_embed_duration_seconds` | Histogram | Embedding generation time |
| indexer | `indexer_documents_processed_total` | Counter | Documents indexed |
| indexer | `indexer_processing_duration_seconds` | Histogram | Document processing time |

### Key Files

- `src/*/metrics.py` - Metric definitions per service
- `src/common/metrics.py` - Shared metric utilities
- `infra/k8s/monitoring/alloy-config.yaml` - Scrape configuration
- `infra/k8s/monitoring/prometheus.yaml` - Prometheus deployment

### Infrastructure Service Metrics

In addition to application metrics, X-RAG collects metrics from infrastructure services (Redis, Kafka, MinIO) via dedicated exporters. These provide internal service health and performance data beyond what cAdvisor/kube-state-metrics provide.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE METRICS PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐        │
│  │      Redis       │   │      Kafka       │   │      MinIO       │        │
│  │                  │   │                  │   │                  │        │
│  │ ┌──────────────┐ │   │                  │   │ Native metrics   │        │
│  │ │redis-exporter│ │   │                  │   │ endpoint         │        │
│  │ │  (sidecar)   │ │   │                  │   │                  │        │
│  │ └──────┬───────┘ │   │                  │   │                  │        │
│  │        │ :9121   │   │                  │   │        :9000     │        │
│  └────────┼─────────┘   └────────┬─────────┘   └────────┬─────────┘        │
│           │                      │                      │                   │
│           │             ┌────────┴────────┐             │                   │
│           │             │  kafka-exporter │             │                   │
│           │             │  (standalone)   │             │                   │
│           │             │      :9308      │             │                   │
│           │             └────────┬────────┘             │                   │
│           │                      │                      │                   │
│           └──────────────────────┼──────────────────────┘                   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        Grafana Alloy                                  │  │
│  │                                                                       │  │
│  │  prometheus.scrape "redis_exporter"   ──┐                            │  │
│  │  prometheus.scrape "kafka_exporter"   ──┼──► prometheus.remote_write │  │
│  │  prometheus.scrape "minio"            ──┘                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        Prometheus                                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Redis Metrics (redis-exporter)

The `oliver006/redis_exporter` runs as a sidecar in the Redis pod, scraping Redis INFO commands and exposing them as Prometheus metrics.

| Metric | Type | Description |
|--------|------|-------------|
| `redis_up` | Gauge | Redis availability (1=up, 0=down) |
| `redis_uptime_in_seconds` | Gauge | Server uptime |
| `redis_connected_clients` | Gauge | Number of connected clients |
| `redis_blocked_clients` | Gauge | Clients blocked on BLPOP/BRPOP |
| `redis_memory_used_bytes` | Gauge | Total memory used by Redis |
| `redis_memory_max_bytes` | Gauge | Max memory limit (maxmemory config) |
| `redis_mem_fragmentation_ratio` | Gauge | Memory fragmentation (>1.5 = fragmented) |
| `redis_keyspace_hits_total` | Counter | Successful key lookups |
| `redis_keyspace_misses_total` | Counter | Failed key lookups |
| `redis_commands_total` | Counter | Commands processed by type |
| `redis_expired_keys_total` | Counter | Keys expired by TTL |
| `redis_evicted_keys_total` | Counter | Keys evicted due to maxmemory |
| `redis_db_keys` | Gauge | Number of keys per database |

**Key PromQL queries:**

```promql
# Cache hit rate
redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)

# Commands per second
rate(redis_commands_total[5m])

# Memory usage percentage
redis_memory_used_bytes / redis_memory_max_bytes
```

#### Kafka Metrics (kafka-exporter)

The `danielqsj/kafka-exporter` runs as a standalone deployment, connecting to Kafka brokers and exposing cluster-wide metrics.

| Metric | Type | Description |
|--------|------|-------------|
| `kafka_brokers` | Gauge | Number of active brokers |
| `kafka_broker_info` | Gauge | Broker metadata (address, ID) |
| `kafka_topic_partitions` | Gauge | Partition count per topic |
| `kafka_topic_partition_current_offset` | Gauge | Latest offset per partition |
| `kafka_topic_partition_oldest_offset` | Gauge | Earliest offset per partition |
| `kafka_topic_partition_replicas` | Gauge | Replica count per partition |
| `kafka_topic_partition_in_sync_replica` | Gauge | In-sync replicas per partition |
| `kafka_topic_partition_under_replicated_partition` | Gauge | Under-replicated partitions |
| `kafka_consumergroup_current_offset` | Gauge | Consumer group offset per partition |
| `kafka_consumergroup_lag` | Gauge | Consumer lag (messages behind) |
| `kafka_consumergroup_members` | Gauge | Members per consumer group |

**Key PromQL queries:**

```promql
# Total consumer lag across all groups
sum(kafka_consumergroup_lag)

# Consumer lag by group and topic
sum by (consumergroup, topic) (kafka_consumergroup_lag)

# Messages produced per second
sum by (topic) (rate(kafka_topic_partition_current_offset[5m]))

# Under-replicated partitions (should be 0)
sum(kafka_topic_partition_under_replicated_partition)
```

#### MinIO Metrics (native endpoint)

MinIO exposes Prometheus metrics natively at `/minio/v2/metrics/cluster`. Authentication is disabled via `MINIO_PROMETHEUS_AUTH_TYPE=public`.

| Metric | Type | Description |
|--------|------|-------------|
| `minio_s3_requests_total` | Counter | Total S3 API requests by operation |
| `minio_s3_requests_errors_total` | Counter | Failed S3 requests |
| `minio_s3_requests_4xx_errors_total` | Counter | Client errors (4xx) |
| `minio_s3_requests_5xx_errors_total` | Counter | Server errors (5xx) |
| `minio_s3_traffic_received_bytes` | Counter | Bytes uploaded |
| `minio_s3_traffic_sent_bytes` | Counter | Bytes downloaded |
| `minio_s3_requests_ttfb_seconds_distribution` | Histogram | Time to first byte |
| `minio_bucket_usage_total_bytes` | Gauge | Storage used per bucket |
| `minio_bucket_usage_object_total` | Gauge | Object count per bucket |
| `minio_node_drive_total_bytes` | Gauge | Total disk capacity |
| `minio_node_drive_used_bytes` | Gauge | Disk space used |
| `minio_node_drive_free_bytes` | Gauge | Disk space available |
| `minio_cluster_capacity_usable_free_bytes` | Gauge | Cluster-wide free space |
| `minio_cluster_health_status` | Gauge | Cluster health (1=healthy) |
| `minio_node_process_uptime_seconds` | Gauge | Node uptime |

**Key PromQL queries:**

```promql
# S3 request rate by API
sum by (api) (rate(minio_s3_requests_total[5m]))

# Error rate
sum(rate(minio_s3_requests_errors_total[5m])) / sum(rate(minio_s3_requests_total[5m]))

# Disk usage percentage
sum(minio_node_drive_used_bytes) / sum(minio_node_drive_total_bytes)

# Upload/download throughput
rate(minio_s3_traffic_received_bytes[5m])  # Upload
rate(minio_s3_traffic_sent_bytes[5m])      # Download
```

#### Infrastructure Dashboards

Grafana includes pre-built dashboards for infrastructure monitoring:

| Dashboard | UID | Key Panels |
|-----------|-----|------------|
| **Redis** | `redis-dashboard` | Memory usage, hit rate, commands/sec, connections, fragmentation |
| **Kafka** | `kafka-dashboard` | Consumer lag, broker count, topic partitions, message throughput |
| **MinIO** | `minio-dashboard` | S3 requests, error rate, traffic, bucket sizes, disk usage |

Access at: http://localhost:3000 → Browse → X-RAG folder

---

## Logs

### What are Logs?

Logs are timestamped text records of events. They provide detailed context about what happened at a specific moment, including error messages, debug information, and audit trails.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LOGS PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPLICATION LAYER                                                          │
│  ─────────────────                                                          │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  search-ui   │  │search-service│  │embed-service │  │   indexer    │   │
│  │              │  │              │  │              │  │              │   │
│  │ import       │  │ import       │  │ import       │  │ import       │   │
│  │ logging      │  │ logging      │  │ logging      │  │ logging      │   │
│  │              │  │              │  │              │  │              │   │
│  │ logger.info()│  │ logger.info()│  │ logger.info()│  │ logger.info()│   │
│  │ logger.error│  │ logger.error │  │ logger.error │  │ logger.error │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │ stdout          │ stdout          │ stdout          │ stdout    │
│         └─────────────────┴─────────────────┴─────────────────┘            │
│                                    │                                        │
│                                    ▼                                        │
│  KUBERNETES RUNTIME                                                         │
│  ──────────────────                                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Container Runtime (containerd)                                      │   │
│  │                                                                      │   │
│  │  stdout/stderr ──► /var/log/pods/<namespace>_<pod>_<uid>/<container> │   │
│  │                                                                      │   │
│  │  Example:                                                            │   │
│  │  /var/log/pods/rag-system_search-ui-abc123_xyz/search-ui/0.log      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ File tail                              │
│                                    ▼                                        │
│  COLLECTION LAYER                                                           │
│  ────────────────                                                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 Grafana Alloy (DaemonSet)                            │   │
│  │                 Runs on every Kubernetes node                        │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ loki.source.kubernetes                                       │    │   │
│  │  │  • Discovers pods via Kubernetes API                         │    │   │
│  │  │  • Tails log files from /var/log/pods                        │    │   │
│  │  │  • Extracts Kubernetes metadata                              │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                          │                                           │   │
│  │                          ▼                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ loki.process                                                 │    │   │
│  │  │  • Adds labels: namespace, pod, container, node              │    │   │
│  │  │  • Parses log format (JSON, logfmt)                          │    │   │
│  │  │  • Filters unwanted logs                                     │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                          │                                           │   │
│  │                          ▼                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ loki.write                                                   │    │   │
│  │  │  • Batches log entries                                       │    │   │
│  │  │  • Sends to Loki via HTTP                                    │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ HTTP POST /loki/api/v1/push            │
│                                    ▼                                        │
│  STORAGE LAYER                                                              │
│  ─────────────                                                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Grafana Loki                                  │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ Distributor                                                  │    │   │
│  │  │  • Receives log streams                                      │    │   │
│  │  │  • Validates and forwards to ingesters                       │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                          │                                           │   │
│  │                          ▼                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ Ingester                                                     │    │   │
│  │  │  • Builds compressed chunks                                  │    │   │
│  │  │  • Indexes by labels (not full-text!)                        │    │   │
│  │  │  • Writes to storage                                         │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                          │                                           │   │
│  │                          ▼                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ Storage                                                      │    │   │
│  │  │  • Chunks: compressed log data                               │    │   │
│  │  │  • Index: label → chunk mappings                             │    │   │
│  │  │  • Query API: http://loki.monitoring:3100                    │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Log Format in X-RAG

All services use Python's standard logging with a consistent format:

```
2024-01-15 10:23:45,123 - src.search_service.server - INFO - Search request: query='what is RAG?', mode=hybrid, top_k=5
│                         │                           │      │
│                         │                           │      └─ Message
│                         │                           └─ Level
│                         └─ Logger name (module path)
└─ Timestamp
```

### Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostic information |
| `INFO` | General operational messages |
| `WARNING` | Something unexpected but recoverable |
| `ERROR` | Error that prevented an operation |
| `CRITICAL` | System-level failure |

### LogQL Examples

```
# All logs from search-ui
{namespace="rag-system", container="search-ui"}

# Error logs only
{namespace="rag-system"} |= "ERROR"

# Logs containing a specific trace ID
{namespace="rag-system"} |= "trace_id=abc123"

# Parse JSON logs and filter
{namespace="rag-system"} | json | level="error"
```

### Key Files

- `src/*/main.py` - Logging configuration per service
- `infra/k8s/monitoring/alloy-config.yaml` - Log collection pipeline
- `infra/k8s/monitoring/loki.yaml` - Loki deployment

---

## Correlation Between Signals

The power of observability comes from correlating all three signals:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SIGNAL CORRELATION                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Alert fires: "High error rate on search-service"                        │
│     │                                                                       │
│     │  ┌──────────────────────────────────────────────────────────────┐    │
│     │  │ METRICS (Prometheus)                                          │    │
│     │  │ rate(search_service_errors_total[5m]) > 0.1                   │    │
│     │  │                                                               │    │
│     │  │ Shows: Error spike started at 10:23:00                        │    │
│     │  └──────────────────────────────────────────────────────────────┘    │
│     │                                                                       │
│     ▼                                                                       │
│  2. Find example trace with error                                           │
│     │                                                                       │
│     │  ┌──────────────────────────────────────────────────────────────┐    │
│     │  │ TRACES (Tempo)                                                │    │
│     │  │ {status=error && resource.service.name="search-service"}      │    │
│     │  │                                                               │    │
│     │  │ Shows: Trace abc123, error in embedding.generate span         │    │
│     │  │        Duration: 30s (timeout)                                │    │
│     │  └──────────────────────────────────────────────────────────────┘    │
│     │                                                                       │
│     ▼                                                                       │
│  3. Get detailed error message                                              │
│                                                                             │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │ LOGS (Loki)                                                       │   │
│     │ {namespace="rag-system"} |= "abc123" |= "error"                   │   │
│     │                                                                   │   │
│     │ Shows: "OpenAI API rate limit exceeded. Retry after 60s"          │   │
│     │        Stack trace with exact line numbers                        │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Result: Root cause identified in minutes, not hours                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Exemplars (Metrics → Traces)

Prometheus supports exemplars that link a metric sample to a specific trace:

```
# Histogram bucket with exemplar
search_service_request_duration_seconds_bucket{le="0.5"} 1234 # {trace_id="abc123"} 0.45
```

In Grafana, clicking the exemplar jumps directly to that trace in Tempo.

---

## Accessing Observability Data

### Grafana (Unified UI)

- **URL**: http://localhost:3000
- **Credentials**: admin/admin (development)

| Data Source | Query Language | Example Query |
|-------------|----------------|---------------|
| Prometheus | PromQL | `rate(requests_total[5m])` |
| Tempo | TraceQL | `{resource.service.name="search-ui"}` |
| Loki | LogQL | `{namespace="rag-system"} \|= "error"` |

### Direct API Access

```bash
# Prometheus metrics
curl http://localhost:9090/api/v1/query?query=up

# Tempo traces
curl http://localhost:3000/api/datasources/proxy/uid/tempo/api/search

# Loki logs
curl http://localhost:3000/api/datasources/proxy/uid/loki/loki/api/v1/query?query={namespace="rag-system"}
```

### Port Mappings

| Service | Port | Purpose |
|---------|------|---------|
| Grafana | 3000 | Unified visualization |
| Prometheus | 9090 | Metrics API |
| Tempo | 3200 | Trace query API |
| Loki | 3100 | Log query API |
| Alloy | 4317 | OTLP gRPC receiver |
| Alloy | 4318 | OTLP HTTP receiver |
