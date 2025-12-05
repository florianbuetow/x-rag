"""Prometheus metrics for Search Service.

Defines metrics following the four golden signals for the Search Service:
- Latency: Request duration histograms with operation-specific buckets
- Traffic: Request counters
- Errors: Error counters with type labels
- Saturation: Active request gauges

All duration metrics are in seconds (Prometheus convention).
"""

from prometheus_client import Counter, Gauge, Histogram

from src.common.metrics import BucketConfig, OperationType

# =============================================================================
# Latency Metrics (Histograms)
# =============================================================================

# Full request duration for Search and HealthCheck methods
request_duration = Histogram(
    "search_service_request_duration_seconds",
    "Total duration of Search Service requests",
    ["method"],
    buckets=BucketConfig.get(OperationType.SLOW),
)

# Query embedding generation (calling Embedding Service)
embedding_duration = Histogram(
    "search_service_embedding_duration_seconds",
    "Duration of query embedding generation",
    buckets=BucketConfig.get(OperationType.FAST),
)

# Document retrieval from Weaviate
retrieval_duration = Histogram(
    "search_service_retrieval_duration_seconds",
    "Duration of document retrieval from Weaviate",
    ["mode"],  # vector, bm25, hybrid
    buckets=BucketConfig.get(OperationType.MEDIUM),
)

# LLM answer generation
llm_generation_duration = Histogram(
    "search_service_llm_generation_duration_seconds",
    "Duration of LLM answer generation",
    buckets=BucketConfig.get(OperationType.SLOW),
)

# =============================================================================
# Traffic Metrics (Counters)
# =============================================================================

# Total requests with status
requests_total = Counter(
    "search_service_requests_total",
    "Total number of Search Service requests",
    ["method", "status"],
)

# =============================================================================
# Error Metrics (Counters)
# =============================================================================

# Errors with type classification
errors_total = Counter(
    "search_service_errors_total",
    "Total number of Search Service errors",
    ["method", "error_type"],
)

# =============================================================================
# Saturation Metrics (Gauges)
# =============================================================================

# Currently active requests
active_requests = Gauge(
    "search_service_active_requests",
    "Number of currently active requests",
    ["method"],
)
