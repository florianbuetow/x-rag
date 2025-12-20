"""OpenTelemetry metrics export for services.

Provides OTLP metric export to Grafana Alloy alongside existing
Prometheus metrics. Both systems receive the same metrics.

Usage:
    from src.common.otel_metrics import init_otel_metrics, get_meter

    # Initialize once at service startup
    init_otel_metrics("search-service", "0.1.0")

    # Get meter for creating metrics
    meter = get_meter("search-service")
    counter = meter.create_counter("requests_total")
"""

import logging
import os

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource

logger = logging.getLogger(__name__)

_initialized = False


def init_otel_metrics(
    service_name: str,
    service_version: str,
) -> None:
    """Initialize OpenTelemetry metrics with OTLP export to Grafana Alloy.

    This function should be called once at service startup. It configures
    the OpenTelemetry SDK to export metrics via OTLP gRPC to Grafana Alloy.

    Environment variables:
        OTEL_EXPORTER_OTLP_ENDPOINT: Alloy endpoint (default: http://xrag-alloy:4317)
        OTEL_METRICS_ENABLED: Set to "false" to disable (default: true)

    Args:
        service_name: Name of the service for resource attribution
        service_version: Version of the service
    """
    global _initialized

    if _initialized:
        logger.warning("OTel metrics already initialized, skipping")
        return

    enabled = os.getenv("OTEL_METRICS_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("OTel metrics disabled via OTEL_METRICS_ENABLED=false")
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://xrag-alloy:4317")
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
    _initialized = True

    logger.info(
        "OTel metrics initialized: service=%s, endpoint=%s",
        service_name,
        endpoint,
    )


def get_meter(name: str) -> metrics.Meter:
    """Get a meter for creating metrics.

    Args:
        name: Name of the meter (typically the service or module name)

    Returns:
        OpenTelemetry Meter instance
    """
    return metrics.get_meter(name)


def shutdown_otel_metrics() -> None:
    """Shutdown the OpenTelemetry metrics provider.

    Call this during graceful shutdown to flush pending metrics.
    """
    global _initialized

    if not _initialized:
        return

    provider = metrics.get_meter_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
        logger.info("OTel metrics shutdown complete")

    _initialized = False
