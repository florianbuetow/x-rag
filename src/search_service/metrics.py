"""OpenTelemetry metrics for Search Service.

Defines metrics following the four golden signals for the Search Service:
- Latency: Request duration histograms with operation-specific buckets
- Traffic: Request counters
- Errors: Error counters with type labels
- Saturation: Active request gauges (using UpDownCounter)

All duration metrics are in seconds (Prometheus convention).
Metrics are exported via OTLP to Grafana Alloy.
"""

from opentelemetry.metrics import Counter, Histogram, UpDownCounter

from src.common.otel_metrics import get_meter

# Module-level metric instances (lazily initialized)
_request_duration: Histogram | None = None
_embedding_duration: Histogram | None = None
_retrieval_duration: Histogram | None = None
_llm_generation_duration: Histogram | None = None
_requests_total: Counter | None = None
_errors_total: Counter | None = None
_active_requests: UpDownCounter | None = None
_initialized = False


def _ensure_metrics() -> None:
    """Initialize metrics if not already done."""
    global _request_duration, _embedding_duration, _retrieval_duration
    global _llm_generation_duration, _requests_total, _errors_total
    global _active_requests, _initialized

    if _initialized:
        return

    meter = get_meter()

    # Latency Metrics (Histograms)
    _request_duration = meter.create_histogram(
        name="search_service_request_duration_seconds",
        description="Total duration of Search Service requests",
        unit="s",
    )

    _embedding_duration = meter.create_histogram(
        name="search_service_embedding_duration_seconds",
        description="Duration of query embedding generation",
        unit="s",
    )

    _retrieval_duration = meter.create_histogram(
        name="search_service_retrieval_duration_seconds",
        description="Duration of document retrieval from Weaviate",
        unit="s",
    )

    _llm_generation_duration = meter.create_histogram(
        name="search_service_llm_generation_duration_seconds",
        description="Duration of LLM answer generation",
        unit="s",
    )

    # Traffic Metrics (Counters)
    _requests_total = meter.create_counter(
        name="search_service_requests_total",
        description="Total number of Search Service requests",
        unit="1",
    )

    # Error Metrics (Counters)
    _errors_total = meter.create_counter(
        name="search_service_errors_total",
        description="Total number of Search Service errors",
        unit="1",
    )

    # Saturation Metrics (UpDownCounter for gauge-like behavior)
    _active_requests = meter.create_up_down_counter(
        name="search_service_active_requests",
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
        method: The gRPC method name (e.g., "Search", "HealthCheck")
    """
    _ensure_metrics()
    assert _request_duration is not None  # nosec B101
    _request_duration.record(duration_seconds, {"method": method})


def record_embedding_duration(duration_seconds: float) -> None:
    """Record embedding generation duration.

    Args:
        duration_seconds: Duration in seconds
    """
    _ensure_metrics()
    assert _embedding_duration is not None  # nosec B101
    _embedding_duration.record(duration_seconds)


def record_retrieval_duration(duration_seconds: float, mode: str) -> None:
    """Record document retrieval duration.

    Args:
        duration_seconds: Duration in seconds
        mode: Search mode (vector, bm25, hybrid)
    """
    _ensure_metrics()
    assert _retrieval_duration is not None  # nosec B101
    _retrieval_duration.record(duration_seconds, {"mode": mode})


def record_llm_generation_duration(duration_seconds: float) -> None:
    """Record LLM generation duration.

    Args:
        duration_seconds: Duration in seconds
    """
    _ensure_metrics()
    assert _llm_generation_duration is not None  # nosec B101
    _llm_generation_duration.record(duration_seconds)


# =============================================================================
# Public API - Counter increment functions
# =============================================================================


def inc_requests_total(method: str, status: str) -> None:
    """Increment request counter.

    Args:
        method: The gRPC method name (e.g., "Search", "HealthCheck")
        status: Request status ("success" or "error")
    """
    _ensure_metrics()
    assert _requests_total is not None  # nosec B101
    _requests_total.add(1, {"method": method, "status": status})


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


def get_embedding_duration() -> Histogram:
    """Get the embedding duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _embedding_duration is not None  # nosec B101
    return _embedding_duration


def get_retrieval_duration() -> Histogram:
    """Get the retrieval duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _retrieval_duration is not None  # nosec B101
    return _retrieval_duration


def get_llm_generation_duration() -> Histogram:
    """Get the LLM generation duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _llm_generation_duration is not None  # nosec B101
    return _llm_generation_duration
