"""Main entrypoint for Indexer service.

Consumes document events from Kafka, processes them (chunking, embedding),
and stores them in Weaviate for retrieval.
"""

import asyncio
import contextlib
import logging
import os
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from types import FrameType
from typing import cast

from opentelemetry import context, trace

from src.common.metrics import track_latency
from src.common.otel_metrics import init_otel_metrics, shutdown_otel_metrics
from src.common.tracing import init_tracing, shutdown_tracing
from src.indexer.config import IndexerConfig
from src.indexer.consumer import DocumentEventConsumer
from src.indexer.metrics import (
    dec_active_documents,
    get_processing_duration,
    inc_active_documents,
    inc_chunks_created_total,
    inc_documents_processed_total,
    inc_errors_total,
)
from src.indexer.processor import DocumentIndexer


class HealthHTTPServer(HTTPServer):
    """HTTPServer subclass with consumer attribute for health checks."""

    consumer: DocumentEventConsumer | None


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks."""

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health/live":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "alive"}')
        elif self.path == "/health/ready":
            # Check if consumer is healthy (synchronous check)
            if hasattr(self.server, "consumer") and self.server.consumer:
                # Use synchronous health check to avoid event loop issues
                is_healthy = self._check_ready_sync()
                if is_healthy:
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "ready"}')
                else:
                    self.send_response(503)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "not ready"}')
            else:
                self.send_response(503)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "not ready"}')
        else:
            self.send_response(404)
            self.end_headers()

    def _check_ready_sync(self) -> bool:
        """Check readiness synchronously.

        Returns:
            True if consumer is running and connected
        """
        try:
            # Cast to HealthHTTPServer to access consumer attribute
            health_server = cast(HealthHTTPServer, self.server)
            consumer = health_server.consumer
            # Simple check: is consumer running?
            return consumer._running if consumer else False
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return False

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass


class IndexerService:
    """Indexer service orchestrator."""

    def __init__(self, config: IndexerConfig) -> None:
        """Initialize the indexer service.

        Args:
            config: Service configuration
        """
        self.config = config
        self.consumer: DocumentEventConsumer | None = None
        self.indexer: DocumentIndexer | None = None
        self.health_server: HealthHTTPServer | None = None
        self.shutdown_event = asyncio.Event()

        # Configure logging level
        logging.getLogger().setLevel(config.log_level)

    def start_health_server(self) -> None:
        """Start the health check HTTP server."""
        # Bind to 0.0.0.0 for Kubernetes probes - network isolation handled by K8s
        self.health_server = HealthHTTPServer(("0.0.0.0", self.config.health_port), HealthCheckHandler)  # nosec B104
        self.health_server.consumer = self.consumer

        def serve() -> None:
            logger.info(f"Health check server listening on port {self.config.health_port}")
            if self.health_server is not None:
                self.health_server.serve_forever()

        health_thread = Thread(target=serve, daemon=True)
        health_thread.start()

    def stop_health_server(self) -> None:
        """Stop the health check HTTP server."""
        if self.health_server:
            logger.info("Stopping health check server...")
            self.health_server.shutdown()

    async def run(self) -> None:
        """Run the indexer service."""
        logger.info(f"Starting {self.config.service_name}...")

        # Initialize distributed tracing
        init_tracing(
            service_name=self.config.service_name,
            otlp_endpoint=self.config.otlp_endpoint,
            environment=self.config.environment,
        )

        # Initialize OpenTelemetry metrics export to Grafana Alloy
        init_otel_metrics(
            service_name=self.config.service_name,
            service_version=os.getenv("SERVICE_VERSION", "0.1.0"),
        )

        # Start health check server FIRST for K8s probes
        self.start_health_server()

        # Initialize consumer
        self.consumer = DocumentEventConsumer(
            bootstrap_servers=self.config.kafka_bootstrap,
            topic=self.config.kafka_topic,
            group_id=self.config.kafka_group_id,
            auto_offset_reset=self.config.kafka_auto_offset_reset,
        )

        # Update health server with consumer reference
        if self.health_server:
            self.health_server.consumer = self.consumer

        # Initialize indexer
        self.indexer = DocumentIndexer(self.config)

        # Start consumer
        await self.consumer.start()

        logger.info(f"✓ {self.config.service_name} ready")
        logger.info("Waiting for events...")

        # Process events
        try:
            async for event, trace_ctx in self.consumer.consume():
                namespace = event["namespace"] if "namespace" in event else "default"
                inc_active_documents()

                # Attach trace context from Kafka message to link with producer span
                ctx = trace_ctx if trace_ctx else context.get_current()
                tracer = trace.get_tracer(__name__)

                with tracer.start_as_current_span(
                    "indexer.process_document",
                    context=ctx,
                    kind=trace.SpanKind.CONSUMER,
                ) as span:
                    span.set_attribute("messaging.system", "kafka")
                    span.set_attribute("messaging.operation", "consume")
                    doc_id = event["document_id"] if "document_id" in event else "unknown"
                    span.set_attribute("document.id", doc_id)
                    span.set_attribute("document.namespace", namespace)

                    with track_latency(get_processing_duration(), {"namespace": namespace}):
                        try:
                            result = await self.indexer.process_event(event)
                            inc_documents_processed_total(status="success", namespace=namespace)
                            # Record chunks created if available
                            if result and "chunks_created" in result:
                                inc_chunks_created_total(namespace=namespace, count=result["chunks_created"])
                                span.set_attribute("document.chunks_created", result["chunks_created"])
                        except Exception as e:
                            logger.error(f"Failed to process event: {e}", exc_info=True)
                            inc_documents_processed_total(status="error", namespace=namespace)
                            inc_errors_total(stage="processing", error_type=type(e).__name__)
                            span.record_exception(e)
                        finally:
                            dec_active_documents()

        except asyncio.CancelledError:
            logger.info("Indexer task cancelled")
        except Exception as e:
            logger.error(f"Fatal error in indexer: {e}", exc_info=True)
            raise

    async def shutdown(self) -> None:
        """Shutdown the service gracefully."""
        logger.info("Shutting down indexer service...")

        # Shutdown OTel metrics and tracing
        shutdown_otel_metrics()
        shutdown_tracing()

        if self.consumer:
            await self.consumer.stop()

        if self.indexer:
            self.indexer.close()

        self.stop_health_server()

        logger.info("✓ Shutdown complete")

    def signal_handler(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()


async def main() -> None:
    """Main entry point."""
    try:
        # Load configuration
        config = IndexerConfig()
        logger.info(f"Configuration loaded: {config.service_name}")

        # Create service
        service = IndexerService(config)

        # Register signal handlers
        signal.signal(signal.SIGTERM, service.signal_handler)
        signal.signal(signal.SIGINT, service.signal_handler)

        # Run service
        run_task = asyncio.create_task(service.run())

        # Wait for shutdown signal
        await service.shutdown_event.wait()

        # Cancel run task
        run_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run_task

        # Shutdown
        await service.shutdown()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
