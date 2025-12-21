"""OpenTelemetry metrics for Ingestion API.

Defines metrics following the four golden signals for the Ingestion API:
- Latency: Request duration histograms for each operation
- Traffic: Request and document counters
- Errors: Error counters with operation labels
- Saturation: Active request gauges (using UpDownCounter)

All duration metrics are in seconds (Prometheus convention).
Metrics are exported via OTLP to Grafana Alloy.
"""

from opentelemetry.metrics import Counter, Histogram, UpDownCounter

from src.common.otel_metrics import get_meter

# Module-level metric instances (lazily initialized)
_request_duration: Histogram | None = None
_minio_upload_duration: Histogram | None = None
_kafka_publish_duration: Histogram | None = None
_document_size_bytes: Histogram | None = None
_requests_total: Counter | None = None
_errors_total: Counter | None = None
_active_requests: UpDownCounter | None = None
_initialized = False


def _ensure_metrics() -> None:
    """Initialize metrics if not already done."""
    global _request_duration, _minio_upload_duration, _kafka_publish_duration
    global _document_size_bytes, _requests_total, _errors_total
    global _active_requests, _initialized

    if _initialized:
        return

    meter = get_meter()

    # Latency Metrics (Histograms)
    _request_duration = meter.create_histogram(
        name="ingestion_duration_seconds",
        description="Total duration of ingestion requests",
        unit="s",
    )

    _minio_upload_duration = meter.create_histogram(
        name="ingestion_minio_upload_duration_seconds",
        description="Duration of document upload to MinIO",
        unit="s",
    )

    _kafka_publish_duration = meter.create_histogram(
        name="ingestion_kafka_publish_duration_seconds",
        description="Duration of event publishing to Kafka",
        unit="s",
    )

    _document_size_bytes = meter.create_histogram(
        name="ingestion_document_size_bytes",
        description="Distribution of ingested document sizes in bytes",
        unit="By",
    )

    # Traffic Metrics (Counters)
    _requests_total = meter.create_counter(
        name="ingestion_requests_total",
        description="Total number of ingestion requests",
        unit="1",
    )

    # Error Metrics (Counters)
    _errors_total = meter.create_counter(
        name="ingestion_errors_total",
        description="Total number of ingestion errors",
        unit="1",
    )

    # Saturation Metrics (UpDownCounter for gauge-like behavior)
    _active_requests = meter.create_up_down_counter(
        name="ingestion_active_requests",
        description="Number of currently active ingestion requests",
        unit="1",
    )

    _initialized = True


# =============================================================================
# Public API - Histogram recording functions
# =============================================================================


def record_request_duration(duration_seconds: float, operation: str) -> None:
    """Record request duration."""
    _ensure_metrics()
    assert _request_duration is not None
    _request_duration.record(duration_seconds, {"operation": operation})


def record_minio_upload_duration(duration_seconds: float) -> None:
    """Record MinIO upload duration."""
    _ensure_metrics()
    assert _minio_upload_duration is not None
    _minio_upload_duration.record(duration_seconds)


def record_kafka_publish_duration(duration_seconds: float) -> None:
    """Record Kafka publish duration."""
    _ensure_metrics()
    assert _kafka_publish_duration is not None
    _kafka_publish_duration.record(duration_seconds)


def record_document_size_bytes(size_bytes: int) -> None:
    """Record document size."""
    _ensure_metrics()
    assert _document_size_bytes is not None
    _document_size_bytes.record(size_bytes)


# =============================================================================
# Public API - Counter increment functions
# =============================================================================


def inc_requests_total(status: str, namespace: str) -> None:
    """Increment requests counter."""
    _ensure_metrics()
    assert _requests_total is not None
    _requests_total.add(1, {"status": status, "namespace": namespace})


def inc_errors_total(operation: str, error_type: str) -> None:
    """Increment error counter."""
    _ensure_metrics()
    assert _errors_total is not None
    _errors_total.add(1, {"operation": operation, "error_type": error_type})


# =============================================================================
# Public API - Gauge-like functions (UpDownCounter)
# =============================================================================


def inc_active_requests() -> None:
    """Increment active requests gauge."""
    _ensure_metrics()
    assert _active_requests is not None
    _active_requests.add(1)


def dec_active_requests() -> None:
    """Decrement active requests gauge."""
    _ensure_metrics()
    assert _active_requests is not None
    _active_requests.add(-1)


# =============================================================================
# Raw histogram accessors for track_latency context manager
# =============================================================================


def get_request_duration() -> Histogram:
    """Get the request duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _request_duration is not None
    return _request_duration


def get_minio_upload_duration() -> Histogram:
    """Get the MinIO upload duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _minio_upload_duration is not None
    return _minio_upload_duration


def get_kafka_publish_duration() -> Histogram:
    """Get the Kafka publish duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _kafka_publish_duration is not None
    return _kafka_publish_duration
