"""Prometheus metrics for Indexer Service.

Defines metrics following the four golden signals for the Indexer:
- Latency: Processing duration histograms for each pipeline stage
- Traffic: Document and chunk counters
- Errors: Error counters with stage labels
- Saturation: Active document processing gauges

All duration metrics are in seconds (Prometheus convention).

Note: This module consolidates and extends the existing metrics that were
previously defined in main.py.
"""

from prometheus_client import Counter, Gauge, Histogram

from src.common.metrics import BucketConfig, OperationType

# =============================================================================
# Latency Metrics (Histograms)
# =============================================================================

# Full document processing duration (end-to-end pipeline)
processing_duration = Histogram(
    "indexer_processing_duration_seconds",
    "Total duration of document processing",
    ["namespace"],
    buckets=BucketConfig.get(OperationType.BATCH),
)

# Kafka message polling duration
kafka_poll_duration = Histogram(
    "indexer_kafka_poll_duration_seconds",
    "Duration of Kafka message polling",
    buckets=BucketConfig.get(OperationType.BATCH),
)

# MinIO document loading duration
minio_load_duration = Histogram(
    "indexer_minio_load_duration_seconds",
    "Duration of loading document from MinIO",
    buckets=BucketConfig.get(OperationType.MEDIUM),
)

# Text cleaning duration
text_cleaning_duration = Histogram(
    "indexer_text_cleaning_duration_seconds",
    "Duration of text cleaning",
    buckets=BucketConfig.get(OperationType.FAST),
)

# Text splitting duration
text_splitting_duration = Histogram(
    "indexer_text_splitting_duration_seconds",
    "Duration of text splitting into chunks",
    buckets=BucketConfig.get(OperationType.FAST),
)

# Embedding generation duration (calling Embedding Service)
embedding_duration = Histogram(
    "indexer_embedding_duration_seconds",
    "Duration of embedding generation for chunks",
    buckets=BucketConfig.get(OperationType.MEDIUM),
)

# Weaviate batch insert duration
weaviate_insert_duration = Histogram(
    "indexer_weaviate_insert_duration_seconds",
    "Duration of batch insert into Weaviate",
    buckets=BucketConfig.get(OperationType.MEDIUM),
)

# Duplicate check duration
duplicate_check_duration = Histogram(
    "indexer_duplicate_check_duration_seconds",
    "Duration of duplicate document check",
    buckets=BucketConfig.get(OperationType.FAST),
)

# =============================================================================
# Traffic Metrics (Counters)
# =============================================================================

# Total documents processed with status
documents_processed_total = Counter(
    "indexer_documents_processed_total",
    "Total number of documents processed",
    ["status", "namespace"],
)

# Total chunks created
chunks_created_total = Counter(
    "indexer_chunks_created_total",
    "Total number of chunks created",
    ["namespace"],
)

# Kafka messages consumed
kafka_messages_total = Counter(
    "indexer_kafka_messages_total",
    "Total number of Kafka messages consumed",
    ["topic"],
)

# =============================================================================
# Error Metrics (Counters)
# =============================================================================

# Errors with stage classification
errors_total = Counter(
    "indexer_errors_total",
    "Total number of indexer errors",
    ["stage", "error_type"],
)

# =============================================================================
# Saturation Metrics (Gauges)
# =============================================================================

# Currently active document processing
active_documents = Gauge(
    "indexer_active_documents",
    "Number of documents currently being processed",
)

# Kafka consumer lag (if available)
kafka_lag = Gauge(
    "indexer_kafka_lag",
    "Kafka consumer lag by partition",
    ["partition"],
)
