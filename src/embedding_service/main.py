"""Main entrypoint for Embedding Service.

Starts a gRPC server that provides text embedding generation using
configurable generators (OpenAI, local models, etc.).
"""

import asyncio
import logging
import os
import signal
import sys
from types import FrameType

import grpc
from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorServer

from src.common.otel_metrics import init_otel_metrics, shutdown_otel_metrics
from src.common.tracing import init_tracing, shutdown_tracing
from src.embedding_service.config import EmbeddingServiceConfig
from src.embedding_service.server import EmbeddingServicer
from src.proto_gen import embedding_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class EmbeddingServiceRunner:
    """Runner for Embedding Service with graceful shutdown."""

    def __init__(self, config: EmbeddingServiceConfig) -> None:
        """Initialize service runner.

        Args:
            config: Service configuration
        """
        self.config = config
        self.server: grpc.aio.Server | None = None
        self.shutdown_event = asyncio.Event()

        # Configure logging level
        logging.getLogger().setLevel(config.log_level)

    async def start(self) -> None:
        """Start the gRPC server."""
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

        # Instrument gRPC server for distributed tracing
        GrpcAioInstrumentorServer().instrument()  # type: ignore[no-untyped-call]

        # Create servicer (namespace-aware, loads generators on-demand)
        servicer = EmbeddingServicer(datasets_config_path=self.config.datasets_config_path)

        # Create gRPC server
        self.server = grpc.aio.server(
            options=[
                ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
                ("grpc.keepalive_permit_without_calls", True),
                ("grpc.http2.max_pings_without_data", 0),
            ],
        )

        # Add servicer to server
        embedding_pb2_grpc.add_EmbeddingServiceServicer_to_server(servicer, self.server)  # type: ignore[no-untyped-call]

        # Enable reflection for debugging with grpcurl
        if self.config.enable_reflection:
            from grpc_reflection.v1alpha import reflection

            from src.proto_gen import embedding_pb2

            service_names = (
                embedding_pb2.DESCRIPTOR.services_by_name["EmbeddingService"].full_name,
                reflection.SERVICE_NAME,
            )
            reflection.enable_server_reflection(service_names, self.server)
            logger.info("Server reflection enabled for debugging")

        # Start server
        listen_addr = f"[::]:{self.config.port}"
        self.server.add_insecure_port(listen_addr)
        await self.server.start()

        logger.info(f"✓ {self.config.service_name} listening on {listen_addr}")
        logger.info("Namespace-aware embedding service ready to serve requests")

        # Wait for shutdown signal
        await self.shutdown_event.wait()

    async def stop(self) -> None:
        """Stop the gRPC server gracefully."""
        logger.info("Shutting down server...")

        # Shutdown OTel metrics and tracing
        shutdown_otel_metrics()
        shutdown_tracing()

        if self.server:
            await self.server.stop(grace=5.0)
            logger.info("Server stopped")

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
        config = EmbeddingServiceConfig()
        logger.info(f"Configuration loaded: {config.service_name} on port {config.port}")

        # Create and start service
        runner = EmbeddingServiceRunner(config)

        # Register signal handlers
        signal.signal(signal.SIGTERM, runner.signal_handler)
        signal.signal(signal.SIGINT, runner.signal_handler)

        # Start server
        await runner.start()

        # Stop server on shutdown
        await runner.stop()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
