"""Prometheus metrics for Ingestion API.

Defines metrics following the four golden signals for the Ingestion API:
- Latency: Request duration histograms for each operation
- Traffic: Request and document counters
- Errors: Error counters with operation labels
- Saturation: Active request gauges

All duration metrics are in seconds (Prometheus convention).

Note: This module consolidates and extends the existing metrics that were
previously defined in main.py.
"""

from prometheus_client import Counter, Gauge, Histogram

from src.common.metrics import BucketConfig, OperationType

# =============================================================================
# Latency Metrics (Histograms)
# =============================================================================

# Full request duration for ingest endpoint
request_duration = Histogram(
    "ingestion_duration_seconds",
    "Total duration of ingestion requests",
    ["operation"],
    buckets=BucketConfig.get(OperationType.MEDIUM),
)

# MinIO upload duration
minio_upload_duration = Histogram(
    "ingestion_minio_upload_duration_seconds",
    "Duration of document upload to MinIO",
    buckets=BucketConfig.get(OperationType.MEDIUM),
)

# Kafka publish duration
kafka_publish_duration = Histogram(
    "ingestion_kafka_publish_duration_seconds",
    "Duration of event publishing to Kafka",
    buckets=BucketConfig.get(OperationType.FAST),
)

# Document size distribution
document_size_bytes = Histogram(
    "ingestion_document_size_bytes",
    "Distribution of ingested document sizes in bytes",
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600),  # 1KB to 100MB
)

# =============================================================================
# Traffic Metrics (Counters)
# =============================================================================

# Total requests with status
requests_total = Counter(
    "ingestion_requests_total",
    "Total number of ingestion requests",
    ["status", "namespace"],
)

# =============================================================================
# Error Metrics (Counters)
# =============================================================================

# Errors with operation classification
errors_total = Counter(
    "ingestion_errors_total",
    "Total number of ingestion errors",
    ["operation", "error_type"],
)

# =============================================================================
# Saturation Metrics (Gauges)
# =============================================================================

# Currently active requests
active_requests = Gauge(
    "ingestion_active_requests",
    "Number of currently active ingestion requests",
)
