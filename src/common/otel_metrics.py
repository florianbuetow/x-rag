"""OpenTelemetry metrics for X-RAG services.

Provides OTLP metric export to Grafana Alloy. All metrics are created using
OpenTelemetry SDK and exported via OTLP protocol.

Usage:
    from src.common.otel_metrics import init_otel_metrics, get_meter

    # Initialize once at service startup
    init_otel_metrics("search-service", "0.1.0")

    # Get meter for creating metrics
    meter = get_meter()
    counter = meter.create_counter("requests_total")
"""

import logging
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from enum import Enum

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource

logger = logging.getLogger(__name__)

_initialized = False
_meter: metrics.Meter | None = None
_service_name: str = "unknown"


class OperationType(Enum):
    """Operation types for histogram bucket selection."""

    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    BATCH = "batch"


# Histogram bucket configurations (in seconds)
# These match the original BucketConfig from the prometheus_client implementation
HISTOGRAM_BUCKETS: dict[OperationType, tuple[float, ...]] = {
    # Fast operations: < 100ms target (embedding lookups, cache hits)
    OperationType.FAST: (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5),
    # Medium operations: < 500ms target (Weaviate queries, text processing)
    OperationType.MEDIUM: (0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 2.0),
    # Slow operations: < 30s target (LLM generation, full search pipeline)
    OperationType.SLOW: (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 20.0, 30.0),
    # Batch operations: < 5s target (Kafka consume, batch inserts)
    OperationType.BATCH: (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0),
}


def get_buckets(operation_type: OperationType) -> tuple[float, ...]:
    """Get histogram buckets for an operation type.

    Args:
        operation_type: The type of operation

    Returns:
        Tuple of bucket boundaries in seconds
    """
    return HISTOGRAM_BUCKETS[operation_type]


def init_otel_metrics(
    service_name: str,
    service_version: str,
) -> None:
    """Initialize OpenTelemetry metrics with OTLP export to Grafana Alloy.

    This function should be called once at service startup. It configures
    the OpenTelemetry SDK to export metrics via OTLP gRPC to Grafana Alloy.

    Environment variables:
        OTEL_EXPORTER_OTLP_ENDPOINT: Alloy endpoint (default: http://alloy.monitoring.svc.cluster.local:4317)
        OTEL_METRICS_ENABLED: Set to "false" to disable (default: true)

    Args:
        service_name: Name of the service for resource attribution
        service_version: Version of the service
    """
    global _initialized, _meter, _service_name

    if _initialized:
        logger.warning("OTel metrics already initialized, skipping")
        return

    _service_name = service_name

    enabled = os.getenv("OTEL_METRICS_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("OTel metrics disabled via OTEL_METRICS_ENABLED=false")
        # Still create a meter for no-op metrics
        _meter = metrics.get_meter(service_name)
        _initialized = True
        return

    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://alloy.monitoring.svc.cluster.local:4317",
    )
    # Strip protocol prefix for gRPC endpoint
    if endpoint.startswith("http://"):
        endpoint = endpoint[7:]
    elif endpoint.startswith("https://"):
        endpoint = endpoint[8:]

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
        }
    )

    exporter = OTLPMetricExporter(
        endpoint=endpoint,
        insecure=True,
    )

    reader = PeriodicExportingMetricReader(
        exporter,
        export_interval_millis=15000,
    )

    provider = MeterProvider(
        resource=resource,
        metric_readers=[reader],
    )

    metrics.set_meter_provider(provider)
    _meter = metrics.get_meter(service_name, service_version)
    _initialized = True

    logger.info(
        "OTel metrics initialized: service=%s, endpoint=%s",
        service_name,
        endpoint,
    )


def get_meter() -> metrics.Meter:
    """Get the initialized meter for creating metrics.

    Returns:
        OpenTelemetry Meter instance

    Raises:
        RuntimeError: If metrics have not been initialized
    """
    global _meter
    if _meter is None:
        # Return a no-op meter if not initialized
        _meter = metrics.get_meter(_service_name)
    return _meter


def shutdown_otel_metrics() -> None:
    """Shutdown the OpenTelemetry metrics provider.

    Call this during graceful shutdown to flush pending metrics.
    """
    global _initialized, _meter

    if not _initialized:
        return

    provider = metrics.get_meter_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
        logger.info("OTel metrics shutdown complete")

    _initialized = False
    _meter = None


@contextmanager
def track_latency(
    histogram: Histogram,
    attributes: dict[str, str],
) -> Generator[None, None, None]:
    """Context manager to track operation latency with a histogram.

    Measures the duration of the code block and records it to the histogram.
    Uses time.perf_counter() for high-precision timing.

    Args:
        histogram: OpenTelemetry Histogram to record the duration
        attributes: Optional dictionary of attributes/labels

    Yields:
        None - use as context manager

    Example:
        with track_latency(request_duration, {"method": "Search"}):
            # code to measure
            result = do_search()
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        histogram.record(duration, attributes)
