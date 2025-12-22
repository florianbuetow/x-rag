"""Common metrics utilities for X-RAG services.

This module re-exports OpenTelemetry metrics utilities for backward compatibility.
All metrics are now exported via OTLP to Grafana Alloy.

Usage:
    from src.common.metrics import track_latency, OperationType, get_buckets

    # Use track_latency context manager
    with track_latency(histogram, {"method": "search"}):
        result = do_search()
"""

from src.common.otel_metrics import (
    HISTOGRAM_BUCKETS,
    OperationType,
    get_buckets,
    get_meter,
    init_otel_metrics,
    shutdown_otel_metrics,
    track_latency,
)

# Re-export BucketConfig as an alias for backward compatibility
BucketConfig = type(
    "BucketConfig",
    (),
    {"get": staticmethod(lambda op_type: get_buckets(op_type))},
)

__all__ = [
    "BucketConfig",
    "HISTOGRAM_BUCKETS",
    "OperationType",
    "get_buckets",
    "get_meter",
    "init_otel_metrics",
    "shutdown_otel_metrics",
    "track_latency",
]
