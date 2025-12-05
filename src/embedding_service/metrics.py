"""Prometheus metrics for Embedding Service.

Defines metrics following the four golden signals for the Embedding Service:
- Latency: Request duration histograms with operation-specific buckets
- Traffic: Request and embedding counters
- Errors: Error counters with type labels
- Saturation: Active request gauges

All duration metrics are in seconds (Prometheus convention).
"""

from prometheus_client import Counter, Gauge, Histogram

from src.common.metrics import BucketConfig, OperationType

# =============================================================================
# Latency Metrics (Histograms)
# =============================================================================

# Full request duration for Embed, EmbedBatch, and HealthCheck methods
request_duration = Histogram(
    "embedding_service_request_duration_seconds",
    "Total duration of Embedding Service requests",
    ["method"],
    buckets=BucketConfig.get(OperationType.FAST),
)

# Backend embedding generation (actual model call)
backend_duration = Histogram(
    "embedding_service_backend_duration_seconds",
    "Duration of backend embedding generation",
    ["model"],
    buckets=BucketConfig.get(OperationType.FAST),
)

# Batch size distribution
batch_size = Histogram(
    "embedding_service_batch_size",
    "Distribution of batch sizes for EmbedBatch requests",
    buckets=(1, 2, 5, 10, 25, 50, 100, 250, 500, 1000),
)

# =============================================================================
# Traffic Metrics (Counters)
# =============================================================================

# Total requests with status
requests_total = Counter(
    "embedding_service_requests_total",
    "Total number of Embedding Service requests",
    ["method", "status"],
)

# Total embeddings generated
embeddings_total = Counter(
    "embedding_service_embeddings_total",
    "Total number of embeddings generated",
    ["model"],
)

# =============================================================================
# Error Metrics (Counters)
# =============================================================================

# Errors with type classification
errors_total = Counter(
    "embedding_service_errors_total",
    "Total number of Embedding Service errors",
    ["method", "error_type"],
)

# =============================================================================
# Saturation Metrics (Gauges)
# =============================================================================

# Currently active requests
active_requests = Gauge(
    "embedding_service_active_requests",
    "Number of currently active requests",
    ["method"],
)
