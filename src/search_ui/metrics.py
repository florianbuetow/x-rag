"""Prometheus metrics for Search UI.

Defines metrics following the four golden signals for the Search UI:
- Latency: Request duration histograms for each operation
- Traffic: Request counters
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

# Full request duration for search endpoint
request_duration = Histogram(
    "search_ui_duration_seconds",
    "Total duration of Search UI requests",
    ["operation"],
    buckets=BucketConfig.get(OperationType.SLOW),
)

# gRPC call duration to Search Service
grpc_call_duration = Histogram(
    "search_ui_grpc_call_duration_seconds",
    "Duration of gRPC calls to Search Service",
    ["method"],
    buckets=BucketConfig.get(OperationType.SLOW),
)

# Number of sources returned
sources_returned = Histogram(
    "search_ui_sources_returned",
    "Distribution of number of sources returned per search",
    buckets=(0, 1, 2, 3, 5, 10, 15, 20, 25, 50),
)

# =============================================================================
# Traffic Metrics (Counters)
# =============================================================================

# Total requests with status
requests_total = Counter(
    "search_ui_requests_total",
    "Total number of Search UI requests",
    ["status", "mode"],
)

# =============================================================================
# Error Metrics (Counters)
# =============================================================================

# Errors with operation classification
errors_total = Counter(
    "search_ui_errors_total",
    "Total number of Search UI errors",
    ["operation", "error_type"],
)

# =============================================================================
# Saturation Metrics (Gauges)
# =============================================================================

# Currently active requests
active_requests = Gauge(
    "search_ui_active_requests",
    "Number of currently active Search UI requests",
)
