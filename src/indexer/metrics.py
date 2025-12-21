"""OpenTelemetry metrics for Indexer Service.

Defines metrics following the four golden signals for the Indexer:
- Latency: Processing duration histograms for each pipeline stage
- Traffic: Document and chunk counters
- Errors: Error counters with stage labels
- Saturation: Active document processing gauges (using UpDownCounter)

All duration metrics are in seconds (Prometheus convention).
Metrics are exported via OTLP to Grafana Alloy.
"""

from opentelemetry.metrics import Counter, Histogram, UpDownCounter

from src.common.otel_metrics import get_meter

# Module-level metric instances (lazily initialized)
_processing_duration: Histogram | None = None
_kafka_poll_duration: Histogram | None = None
_minio_load_duration: Histogram | None = None
_text_cleaning_duration: Histogram | None = None
_text_splitting_duration: Histogram | None = None
_embedding_duration: Histogram | None = None
_weaviate_insert_duration: Histogram | None = None
_duplicate_check_duration: Histogram | None = None
_documents_processed_total: Counter | None = None
_chunks_created_total: Counter | None = None
_kafka_messages_total: Counter | None = None
_errors_total: Counter | None = None
_active_documents: UpDownCounter | None = None
_kafka_lag: UpDownCounter | None = None
_initialized = False


def _ensure_metrics() -> None:
    """Initialize metrics if not already done."""
    global _processing_duration, _kafka_poll_duration, _minio_load_duration
    global _text_cleaning_duration, _text_splitting_duration, _embedding_duration
    global _weaviate_insert_duration, _duplicate_check_duration
    global _documents_processed_total, _chunks_created_total, _kafka_messages_total
    global _errors_total, _active_documents, _kafka_lag, _initialized

    if _initialized:
        return

    meter = get_meter()

    # Latency Metrics (Histograms)
    _processing_duration = meter.create_histogram(
        name="indexer_processing_duration_seconds",
        description="Total duration of document processing",
        unit="s",
    )

    _kafka_poll_duration = meter.create_histogram(
        name="indexer_kafka_poll_duration_seconds",
        description="Duration of Kafka message polling",
        unit="s",
    )

    _minio_load_duration = meter.create_histogram(
        name="indexer_minio_load_duration_seconds",
        description="Duration of loading document from MinIO",
        unit="s",
    )

    _text_cleaning_duration = meter.create_histogram(
        name="indexer_text_cleaning_duration_seconds",
        description="Duration of text cleaning",
        unit="s",
    )

    _text_splitting_duration = meter.create_histogram(
        name="indexer_text_splitting_duration_seconds",
        description="Duration of text splitting into chunks",
        unit="s",
    )

    _embedding_duration = meter.create_histogram(
        name="indexer_embedding_duration_seconds",
        description="Duration of embedding generation for chunks",
        unit="s",
    )

    _weaviate_insert_duration = meter.create_histogram(
        name="indexer_weaviate_insert_duration_seconds",
        description="Duration of batch insert into Weaviate",
        unit="s",
    )

    _duplicate_check_duration = meter.create_histogram(
        name="indexer_duplicate_check_duration_seconds",
        description="Duration of duplicate document check",
        unit="s",
    )

    # Traffic Metrics (Counters)
    _documents_processed_total = meter.create_counter(
        name="indexer_documents_processed_total",
        description="Total number of documents processed",
        unit="1",
    )

    _chunks_created_total = meter.create_counter(
        name="indexer_chunks_created_total",
        description="Total number of chunks created",
        unit="1",
    )

    _kafka_messages_total = meter.create_counter(
        name="indexer_kafka_messages_total",
        description="Total number of Kafka messages consumed",
        unit="1",
    )

    # Error Metrics (Counters)
    _errors_total = meter.create_counter(
        name="indexer_errors_total",
        description="Total number of indexer errors",
        unit="1",
    )

    # Saturation Metrics (UpDownCounter for gauge-like behavior)
    _active_documents = meter.create_up_down_counter(
        name="indexer_active_documents",
        description="Number of documents currently being processed",
        unit="1",
    )

    _kafka_lag = meter.create_up_down_counter(
        name="indexer_kafka_lag",
        description="Kafka consumer lag by partition",
        unit="1",
    )

    _initialized = True


# =============================================================================
# Public API - Histogram recording functions
# =============================================================================


def record_processing_duration(duration_seconds: float, namespace: str) -> None:
    """Record document processing duration."""
    _ensure_metrics()
    assert _processing_duration is not None
    _processing_duration.record(duration_seconds, {"namespace": namespace})


def record_kafka_poll_duration(duration_seconds: float) -> None:
    """Record Kafka poll duration."""
    _ensure_metrics()
    assert _kafka_poll_duration is not None
    _kafka_poll_duration.record(duration_seconds)


def record_minio_load_duration(duration_seconds: float) -> None:
    """Record MinIO load duration."""
    _ensure_metrics()
    assert _minio_load_duration is not None
    _minio_load_duration.record(duration_seconds)


def record_text_cleaning_duration(duration_seconds: float) -> None:
    """Record text cleaning duration."""
    _ensure_metrics()
    assert _text_cleaning_duration is not None
    _text_cleaning_duration.record(duration_seconds)


def record_text_splitting_duration(duration_seconds: float) -> None:
    """Record text splitting duration."""
    _ensure_metrics()
    assert _text_splitting_duration is not None
    _text_splitting_duration.record(duration_seconds)


def record_embedding_duration(duration_seconds: float) -> None:
    """Record embedding generation duration."""
    _ensure_metrics()
    assert _embedding_duration is not None
    _embedding_duration.record(duration_seconds)


def record_weaviate_insert_duration(duration_seconds: float) -> None:
    """Record Weaviate insert duration."""
    _ensure_metrics()
    assert _weaviate_insert_duration is not None
    _weaviate_insert_duration.record(duration_seconds)


def record_duplicate_check_duration(duration_seconds: float) -> None:
    """Record duplicate check duration."""
    _ensure_metrics()
    assert _duplicate_check_duration is not None
    _duplicate_check_duration.record(duration_seconds)


# =============================================================================
# Public API - Counter increment functions
# =============================================================================


def inc_documents_processed_total(status: str, namespace: str) -> None:
    """Increment documents processed counter."""
    _ensure_metrics()
    assert _documents_processed_total is not None
    _documents_processed_total.add(1, {"status": status, "namespace": namespace})


def inc_chunks_created_total(namespace: str, count: int = 1) -> None:
    """Increment chunks created counter."""
    _ensure_metrics()
    assert _chunks_created_total is not None
    _chunks_created_total.add(count, {"namespace": namespace})


def inc_kafka_messages_total(topic: str) -> None:
    """Increment Kafka messages counter."""
    _ensure_metrics()
    assert _kafka_messages_total is not None
    _kafka_messages_total.add(1, {"topic": topic})


def inc_errors_total(stage: str, error_type: str) -> None:
    """Increment error counter."""
    _ensure_metrics()
    assert _errors_total is not None
    _errors_total.add(1, {"stage": stage, "error_type": error_type})


# =============================================================================
# Public API - Gauge-like functions (UpDownCounter)
# =============================================================================


def inc_active_documents() -> None:
    """Increment active documents gauge."""
    _ensure_metrics()
    assert _active_documents is not None
    _active_documents.add(1)


def dec_active_documents() -> None:
    """Decrement active documents gauge."""
    _ensure_metrics()
    assert _active_documents is not None
    _active_documents.add(-1)


def set_kafka_lag(partition: str, lag: int) -> None:
    """Set Kafka consumer lag for a partition.

    Note: This uses add() since UpDownCounter doesn't have set().
    For accurate lag tracking, you should track the delta.
    """
    _ensure_metrics()
    assert _kafka_lag is not None
    _kafka_lag.add(lag, {"partition": partition})


# =============================================================================
# Raw histogram accessors for track_latency context manager
# =============================================================================


def get_processing_duration() -> Histogram:
    """Get the processing duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _processing_duration is not None
    return _processing_duration


def get_kafka_poll_duration() -> Histogram:
    """Get the Kafka poll duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _kafka_poll_duration is not None
    return _kafka_poll_duration


def get_minio_load_duration() -> Histogram:
    """Get the MinIO load duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _minio_load_duration is not None
    return _minio_load_duration


def get_text_cleaning_duration() -> Histogram:
    """Get the text cleaning duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _text_cleaning_duration is not None
    return _text_cleaning_duration


def get_text_splitting_duration() -> Histogram:
    """Get the text splitting duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _text_splitting_duration is not None
    return _text_splitting_duration


def get_embedding_duration() -> Histogram:
    """Get the embedding duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _embedding_duration is not None
    return _embedding_duration


def get_weaviate_insert_duration() -> Histogram:
    """Get the Weaviate insert duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _weaviate_insert_duration is not None
    return _weaviate_insert_duration


def get_duplicate_check_duration() -> Histogram:
    """Get the duplicate check duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _duplicate_check_duration is not None
    return _duplicate_check_duration
