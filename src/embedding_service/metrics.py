"""OpenTelemetry metrics for Embedding Service.

Defines metrics following the four golden signals for the Embedding Service:
- Latency: Request duration histograms with operation-specific buckets
- Traffic: Request and embedding counters
- Errors: Error counters with type labels
- Saturation: Active request gauges (using UpDownCounter)

All duration metrics are in seconds (Prometheus convention).
Metrics are exported via OTLP to Grafana Alloy.
"""

from opentelemetry.metrics import Counter, Histogram, UpDownCounter

from src.common.otel_metrics import get_meter

# Module-level metric instances (lazily initialized)
_request_duration: Histogram | None = None
_backend_duration: Histogram | None = None
_batch_size: Histogram | None = None
_requests_total: Counter | None = None
_embeddings_total: Counter | None = None
_errors_total: Counter | None = None
_active_requests: UpDownCounter | None = None
_initialized = False


def _ensure_metrics() -> None:
    """Initialize metrics if not already done."""
    global _request_duration, _backend_duration, _batch_size
    global _requests_total, _embeddings_total, _errors_total
    global _active_requests, _initialized

    if _initialized:
        return

    meter = get_meter()

    # Latency Metrics (Histograms)
    _request_duration = meter.create_histogram(
        name="embedding_service_request_duration_seconds",
        description="Total duration of Embedding Service requests",
        unit="s",
    )

    _backend_duration = meter.create_histogram(
        name="embedding_service_backend_duration_seconds",
        description="Duration of backend embedding generation",
        unit="s",
    )

    _batch_size = meter.create_histogram(
        name="embedding_service_batch_size",
        description="Distribution of batch sizes for EmbedBatch requests",
        unit="1",
    )

    # Traffic Metrics (Counters)
    _requests_total = meter.create_counter(
        name="embedding_service_requests_total",
        description="Total number of Embedding Service requests",
        unit="1",
    )

    _embeddings_total = meter.create_counter(
        name="embedding_service_embeddings_total",
        description="Total number of embeddings generated",
        unit="1",
    )

    # Error Metrics (Counters)
    _errors_total = meter.create_counter(
        name="embedding_service_errors_total",
        description="Total number of Embedding Service errors",
        unit="1",
    )

    # Saturation Metrics (UpDownCounter for gauge-like behavior)
    _active_requests = meter.create_up_down_counter(
        name="embedding_service_active_requests",
        description="Number of currently active requests",
        unit="1",
    )

    _initialized = True


# =============================================================================
# Public API - Histogram recording functions
# =============================================================================


def record_request_duration(duration_seconds: float, method: str) -> None:
    """Record request duration.

    Args:
        duration_seconds: Duration in seconds
        method: The gRPC method name (e.g., "Embed", "EmbedBatch")
    """
    _ensure_metrics()
    assert _request_duration is not None  # nosec B101
    _request_duration.record(duration_seconds, {"method": method})


def record_backend_duration(duration_seconds: float, model: str) -> None:
    """Record backend embedding generation duration.

    Args:
        duration_seconds: Duration in seconds
        model: The model name
    """
    _ensure_metrics()
    assert _backend_duration is not None  # nosec B101
    _backend_duration.record(duration_seconds, {"model": model})


def record_batch_size(size: int) -> None:
    """Record batch size.

    Args:
        size: Number of texts in the batch
    """
    _ensure_metrics()
    assert _batch_size is not None  # nosec B101
    _batch_size.record(size)


# =============================================================================
# Public API - Counter increment functions
# =============================================================================


def inc_requests_total(method: str, status: str) -> None:
    """Increment request counter.

    Args:
        method: The gRPC method name (e.g., "Embed", "EmbedBatch")
        status: Request status ("success" or "error")
    """
    _ensure_metrics()
    assert _requests_total is not None  # nosec B101
    _requests_total.add(1, {"method": method, "status": status})


def inc_embeddings_total(model: str, count: int) -> None:
    """Increment embeddings generated counter.

    Args:
        model: The model name
        count: Number of embeddings generated
    """
    _ensure_metrics()
    assert _embeddings_total is not None  # nosec B101
    _embeddings_total.add(count, {"model": model})


def inc_errors_total(method: str, error_type: str) -> None:
    """Increment error counter.

    Args:
        method: The gRPC method name
        error_type: The exception type name
    """
    _ensure_metrics()
    assert _errors_total is not None  # nosec B101
    _errors_total.add(1, {"method": method, "error_type": error_type})


# =============================================================================
# Public API - Gauge-like functions (UpDownCounter)
# =============================================================================


def inc_active_requests(method: str) -> None:
    """Increment active requests gauge.

    Args:
        method: The gRPC method name
    """
    _ensure_metrics()
    assert _active_requests is not None  # nosec B101
    _active_requests.add(1, {"method": method})


def dec_active_requests(method: str) -> None:
    """Decrement active requests gauge.

    Args:
        method: The gRPC method name
    """
    _ensure_metrics()
    assert _active_requests is not None  # nosec B101
    _active_requests.add(-1, {"method": method})


# =============================================================================
# Raw histogram accessors for track_latency context manager
# =============================================================================


def get_request_duration() -> Histogram:
    """Get the request duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _request_duration is not None  # nosec B101
    return _request_duration


def get_backend_duration() -> Histogram:
    """Get the backend duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _backend_duration is not None  # nosec B101
    return _backend_duration
