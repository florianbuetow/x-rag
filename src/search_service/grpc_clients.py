"""gRPC client for Embedding Service (async version)."""

import logging
from types import TracebackType

import grpc
from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorClient

from src.proto_gen import common_pb2, embedding_pb2, embedding_pb2_grpc

logger = logging.getLogger(__name__)

# Instrument gRPC client for distributed tracing
_grpc_client_instrumentor = GrpcAioInstrumentorClient()  # type: ignore[no-untyped-call]
_grpc_client_instrumentor.instrument()


class EmbeddingServiceClient:
    """Async client for Embedding Service gRPC API.

    Provides async methods to generate embeddings for text via gRPC.
    Used by Search Service to embed queries before retrieval.
    """

    def __init__(self, address: str, timeout: float) -> None:
        """Initialize the Embedding Service client.

        Args:
            address: gRPC server address (host:port)
            timeout: Request timeout in seconds
        """
        self.address = address
        self.timeout = timeout
        self.channel: grpc.aio.Channel | None = None
        self.stub: embedding_pb2_grpc.EmbeddingServiceStub | None = None

    async def __aenter__(self) -> "EmbeddingServiceClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Establish async gRPC connection."""
        logger.info(f"Connecting to Embedding Service at {self.address}")
        self.channel = grpc.aio.insecure_channel(
            self.address,
            options=[
                ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
            ],
        )
        self.stub = embedding_pb2_grpc.EmbeddingServiceStub(self.channel)  # type: ignore[no-untyped-call]
        logger.info("✓ Connected to Embedding Service")

    async def close(self) -> None:
        """Close async gRPC connection."""
        if self.channel:
            logger.info("Closing Embedding Service connection")
            await self.channel.close()
            self.channel = None
            self.stub = None

    async def embed(self, text: str, model: str) -> list[float]:
        """Generate embedding for a single text (async).

        Args:
            text: Text to embed
            model: Model to use (e.g., "text-embedding-3-small")

        Returns:
            Embedding vector as list of floats

        Raises:
            grpc.RpcError: If the gRPC call fails
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = embedding_pb2.EmbedRequest(text=text, model=model)

        try:
            response = await self.stub.Embed(request, timeout=self.timeout)
            return list(response.embedding)
        except grpc.RpcError as e:
            logger.error(f"Embedding request failed: {e.code()} - {e.details()}")
            raise

    async def embed_batch(self, texts: list[str], model: str) -> list[list[float]]:
        """Generate embeddings for multiple texts (async).

        Args:
            texts: List of texts to embed
            model: Model to use

        Returns:
            List of embedding vectors

        Raises:
            grpc.RpcError: If the gRPC call fails
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = embedding_pb2.EmbedBatchRequest(texts=texts, model=model)

        try:
            response = await self.stub.EmbedBatch(request, timeout=self.timeout)
            return [list(emb.embedding) for emb in response.embeddings]
        except grpc.RpcError as e:
            logger.error(f"Batch embedding request failed: {e.code()} - {e.details()}")
            raise

    async def health_check(self) -> bool:
        """Check if Embedding Service is healthy (async).

        Returns:
            True if service is healthy, False otherwise
        """
        if not self.stub:
            return False

        try:
            request = common_pb2.HealthCheckRequest()
            response = await self.stub.HealthCheck(request, timeout=5.0)
            return bool(response.status == common_pb2.HealthCheckResponse.HEALTHY)
        except grpc.RpcError as e:
            logger.warning(f"Health check failed: {e.code()}")
            return False
