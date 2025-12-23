"""OpenTelemetry tracing configuration for X-RAG services.

Provides utilities for initializing distributed tracing with OpenTelemetry
and exporting traces to Grafana Tempo via OTLP protocol.

This module provides:
- init_tracing: Initialize OpenTelemetry TracerProvider with OTLP export
- get_tracer: Get a tracer instance for manual span creation
- shutdown_tracing: Gracefully shutdown tracing on application exit

Usage:
    from src.common.tracing import init_tracing, get_tracer, shutdown_tracing

    # Initialize once at startup
    init_tracing(service_name="search-service")

    # Get tracer for manual spans
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation"):
        do_work()

    # Shutdown on exit
    shutdown_tracing()
"""

import logging
import os
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Global singleton for TracerProvider
_tracer_provider: TracerProvider | None = None
_httpx_instrumented = False
_openai_instrumented = False


def init_tracing(
    service_name: str,
    otlp_endpoint: str | None,
    environment: str,
) -> TracerProvider | None:
    """Initialize OpenTelemetry tracing.

    Configures the global TracerProvider with OTLP export to Tempo.
    Should be called once at service startup.

    Args:
        service_name: Name of this service (appears in traces)
        otlp_endpoint: Tempo/collector endpoint (required, no default)
        environment: Deployment environment tag (development, staging, production)

    Environment variables:
        OTEL_METRICS_ENABLED: Set to "false" to disable tracing (default: true)

    Returns:
        Configured TracerProvider, or None if tracing is disabled

    Raises:
        RuntimeError: If tracing is already initialized
    """
    global _tracer_provider

    enabled = os.getenv("OTEL_METRICS_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("Tracing disabled via OTEL_METRICS_ENABLED=false")
        return None

    if _tracer_provider is not None:
        logger.warning("Tracing already initialized, returning existing provider")
        return _tracer_provider

    # otlp_endpoint is required - no fallbacks
    if otlp_endpoint is None:
        raise ValueError("otlp_endpoint parameter is required for tracing initialization")
    endpoint = otlp_endpoint

    # Create resource with service metadata
    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            "service.namespace": "rag-platform",
            "deployment.environment": environment,
            "service.version": os.getenv("SERVICE_VERSION", "0.1.0"),
        }
    )

    # Initialize provider
    _tracer_provider = TracerProvider(resource=resource)

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=True,  # Set False and configure TLS for production
    )

    # Use batch processor for efficiency (non-blocking export)
    span_processor = BatchSpanProcessor(
        otlp_exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
    )
    _tracer_provider.add_span_processor(span_processor)

    # Set as global provider
    trace.set_tracer_provider(_tracer_provider)

    # Configure context propagation (W3C Trace Context + Baggage)
    set_global_textmap(
        CompositePropagator(
            [
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
            ]
        )
    )

    # Instrument HTTP clients (httpx) for trace propagation
    global _httpx_instrumented
    if not _httpx_instrumented:
        HTTPXClientInstrumentor().instrument()
        _httpx_instrumented = True
        logger.debug("HTTPX client instrumented for tracing")

    # Instrument OpenAI client for LLM call tracing
    global _openai_instrumented
    if not _openai_instrumented:
        OpenAIInstrumentor().instrument()
        _openai_instrumented = True
        logger.debug("OpenAI client instrumented for tracing")

    logger.info(f"Tracing initialized for {service_name}, exporting to {endpoint}")

    return _tracer_provider


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance for creating manual spans.

    Args:
        name: Tracer name, typically __name__ of the module

    Returns:
        OpenTelemetry Tracer instance
    """
    return trace.get_tracer(name)


def shutdown_tracing() -> None:
    """Gracefully shutdown tracing.

    Flushes any pending spans and releases resources.
    Should be called on application shutdown.
    """
    global _tracer_provider

    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None
        logger.info("Tracing shutdown complete")


def get_current_trace_id() -> str | None:
    """Get the current trace ID as a hex string.

    Useful for including trace IDs in API responses for debugging.

    Returns:
        Trace ID as 32-character hex string, or None if no active span
    """
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()

    if span_context.is_valid:
        return format(span_context.trace_id, "032x")

    return None


def is_tracing_enabled() -> bool:
    """Check if tracing has been initialized.

    Returns:
        True if tracing is initialized, False otherwise
    """
    return _tracer_provider is not None
