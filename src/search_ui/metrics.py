"""OpenTelemetry metrics for Search UI.

Defines metrics following the four golden signals for the Search UI:
- Latency: Request duration histograms for each operation
- Traffic: Request counters
- Errors: Error counters with operation labels
- Saturation: Active request gauges (using UpDownCounter)

All duration metrics are in seconds (Prometheus convention).
Metrics are exported via OTLP to Grafana Alloy.
"""

from opentelemetry.metrics import Counter, Histogram, UpDownCounter

from src.common.otel_metrics import get_meter

# Module-level metric instances (lazily initialized)
_request_duration: Histogram | None = None
_grpc_call_duration: Histogram | None = None
_sources_returned: Histogram | None = None
_requests_total: Counter | None = None
_errors_total: Counter | None = None
_active_requests: UpDownCounter | None = None
_initialized = False


def _ensure_metrics() -> None:
    """Initialize metrics if not already done."""
    global _request_duration, _grpc_call_duration, _sources_returned
    global _requests_total, _errors_total, _active_requests, _initialized

    if _initialized:
        return

    meter = get_meter()

    # Latency Metrics (Histograms)
    _request_duration = meter.create_histogram(
        name="search_ui_duration_seconds",
        description="Total duration of Search UI requests",
        unit="s",
    )

    _grpc_call_duration = meter.create_histogram(
        name="search_ui_grpc_call_duration_seconds",
        description="Duration of gRPC calls to Search Service",
        unit="s",
    )

    _sources_returned = meter.create_histogram(
        name="search_ui_sources_returned",
        description="Distribution of number of sources returned per search",
        unit="1",
    )

    # Traffic Metrics (Counters)
    _requests_total = meter.create_counter(
        name="search_ui_requests_total",
        description="Total number of Search UI requests",
        unit="1",
    )

    # Error Metrics (Counters)
    _errors_total = meter.create_counter(
        name="search_ui_errors_total",
        description="Total number of Search UI errors",
        unit="1",
    )

    # Saturation Metrics (UpDownCounter for gauge-like behavior)
    _active_requests = meter.create_up_down_counter(
        name="search_ui_active_requests",
        description="Number of currently active Search UI requests",
        unit="1",
    )

    _initialized = True


# =============================================================================
# Public API - Histogram recording functions
# =============================================================================


def record_request_duration(duration_seconds: float, operation: str) -> None:
    """Record request duration."""
    _ensure_metrics()
    assert _request_duration is not None  # nosec B101
    _request_duration.record(duration_seconds, {"operation": operation})


def record_grpc_call_duration(duration_seconds: float, method: str) -> None:
    """Record gRPC call duration."""
    _ensure_metrics()
    assert _grpc_call_duration is not None  # nosec B101
    _grpc_call_duration.record(duration_seconds, {"method": method})


def record_sources_returned(count: int) -> None:
    """Record number of sources returned."""
    _ensure_metrics()
    assert _sources_returned is not None  # nosec B101
    _sources_returned.record(count)


# =============================================================================
# Public API - Counter increment functions
# =============================================================================


def inc_requests_total(status: str, mode: str) -> None:
    """Increment requests counter."""
    _ensure_metrics()
    assert _requests_total is not None  # nosec B101
    _requests_total.add(1, {"status": status, "mode": mode})


def inc_errors_total(operation: str, error_type: str) -> None:
    """Increment error counter."""
    _ensure_metrics()
    assert _errors_total is not None  # nosec B101
    _errors_total.add(1, {"operation": operation, "error_type": error_type})


# =============================================================================
# Public API - Gauge-like functions (UpDownCounter)
# =============================================================================


def inc_active_requests() -> None:
    """Increment active requests gauge."""
    _ensure_metrics()
    assert _active_requests is not None  # nosec B101
    _active_requests.add(1)


def dec_active_requests() -> None:
    """Decrement active requests gauge."""
    _ensure_metrics()
    assert _active_requests is not None  # nosec B101
    _active_requests.add(-1)


# =============================================================================
# Raw histogram accessors for track_latency context manager
# =============================================================================


def get_request_duration() -> Histogram:
    """Get the request duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _request_duration is not None  # nosec B101
    return _request_duration


def get_grpc_call_duration() -> Histogram:
    """Get the gRPC call duration histogram for use with track_latency."""
    _ensure_metrics()
    assert _grpc_call_duration is not None  # nosec B101
    return _grpc_call_duration
