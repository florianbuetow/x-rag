"""Main entrypoint for Search Service.

Starts a gRPC server that provides RAG search capabilities using
Weaviate retrieval, embedding generation, and OpenAI answer generation.
"""

import asyncio
import logging
import signal
import sys
from types import FrameType

import grpc
from prometheus_client import start_http_server

from src.llm.openai_client import OpenAIClient
from src.pipelines.search_pipeline import SearchPipeline
from src.proto_gen import search_pb2_grpc
from src.retrievers.weaviate_retriever import WeaviateRetriever
from src.search_service.config import SearchServiceConfig
from src.search_service.grpc_clients import EmbeddingServiceClient
from src.search_service.server import SearchServicer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class SearchServiceRunner:
    """Runner for Search Service with graceful shutdown."""

    def __init__(self, config: SearchServiceConfig) -> None:
        """Initialize service runner.

        Args:
            config: Service configuration
        """
        self.config = config
        self.server: grpc.aio.Server | None = None
        self.shutdown_event = asyncio.Event()

        # Component references for cleanup
        self.retriever: WeaviateRetriever | None = None
        self.embedding_client: EmbeddingServiceClient | None = None
        self.llm_client: OpenAIClient | None = None
        self.pipeline: SearchPipeline | None = None

        # Configure logging level
        logging.getLogger().setLevel(config.log_level)

    async def start(self) -> None:
        """Start the gRPC server."""
        logger.info(f"Starting {self.config.service_name}...")

        # Start Prometheus metrics server
        metrics_port = 8080
        start_http_server(metrics_port)
        logger.info(f"Prometheus metrics available at http://0.0.0.0:{metrics_port}/metrics")

        # Initialize components
        logger.info("Initializing components...")

        # 1. Weaviate retriever
        logger.info(f"Connecting to Weaviate at {self.config.weaviate_url}")
        self.retriever = WeaviateRetriever(
            weaviate_url=self.config.weaviate_url,
            collection_name=self.config.weaviate_collection,
        )
        self.retriever.connect()

        # 2. Embedding Service client
        logger.info(f"Connecting to Embedding Service at {self.config.embedding_service_addr}")
        self.embedding_client = EmbeddingServiceClient(
            address=self.config.embedding_service_addr,
            timeout=self.config.embedding_service_timeout,
        )
        await self.embedding_client.connect()

        # 3. OpenAI LLM client
        logger.info(f"Initializing OpenAI client (model={self.config.openai_model})")
        self.llm_client = OpenAIClient(
            api_key=self.config.openai_api_key,
            model=self.config.openai_model,
            max_retries=self.config.openai_max_retries,
            timeout=self.config.openai_timeout,
        )

        # 4. Search pipeline
        logger.info("Creating search pipeline...")
        self.pipeline = SearchPipeline(
            retriever=self.retriever,
            embedding_client=self.embedding_client,
            llm_client=self.llm_client,
            redis_url=self.config.redis_url,
            cache_ttl=self.config.cache_ttl,
            enable_cache=self.config.enable_cache,
            max_context_length=self.config.max_context_length,
        )

        # Create servicer
        servicer = SearchServicer(pipeline=self.pipeline, config=self.config)

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
        search_pb2_grpc.add_SearchServiceServicer_to_server(servicer, self.server)  # type: ignore[no-untyped-call]

        # Enable reflection for debugging with grpcurl
        if self.config.enable_reflection:
            from grpc_reflection.v1alpha import reflection

            from src.proto_gen import search_pb2

            service_names = (
                search_pb2.DESCRIPTOR.services_by_name["SearchService"].full_name,
                reflection.SERVICE_NAME,
            )
            reflection.enable_server_reflection(service_names, self.server)
            logger.info("Server reflection enabled for debugging")

        # Start server
        listen_addr = f"[::]:{self.config.port}"
        self.server.add_insecure_port(listen_addr)
        await self.server.start()

        logger.info(f"✓ {self.config.service_name} listening on {listen_addr}")
        logger.info(f"Default search mode: {self.config.default_mode}")
        logger.info(f"Default top_k: {self.config.default_top_k}")
        logger.info(f"OpenAI model: {self.config.openai_model}")
        logger.info(f"Cache enabled: {self.config.enable_cache}")
        logger.info("Ready to serve requests")

        # Wait for shutdown signal
        await self.shutdown_event.wait()

    async def stop(self) -> None:
        """Stop the gRPC server gracefully."""
        logger.info("Shutting down server...")

        # Stop gRPC server
        if self.server:
            await self.server.stop(grace=5.0)

        # Close components
        if self.pipeline:
            await self.pipeline.close()

        if self.llm_client:
            await self.llm_client.close()

        if self.embedding_client:
            await self.embedding_client.close()

        if self.retriever:
            self.retriever.close()

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
        config = SearchServiceConfig()
        logger.info(f"Configuration loaded: {config.service_name} on port {config.port}")

        # Create and start service
        runner = SearchServiceRunner(config)

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
