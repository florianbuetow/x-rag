"""gRPC client for Embedding Service."""

import logging
from types import TracebackType
from typing import cast

import grpc
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient

from src.proto_gen import embedding_pb2, embedding_pb2_grpc

logger = logging.getLogger(__name__)

# Instrument gRPC client for distributed tracing
_grpc_client_instrumentor = GrpcInstrumentorClient()  # type: ignore[no-untyped-call]
_grpc_client_instrumentor.instrument()


class EmbeddingServiceClient:
    """Client for Embedding Service gRPC API.

    Provides methods to generate embeddings for text via gRPC.
    """

    def __init__(self, address: str, timeout: float) -> None:
        """Initialize the Embedding Service client.

        Args:
            address: gRPC server address (host:port)
            timeout: Request timeout in seconds
        """
        self.address = address
        self.timeout = timeout
        self.channel: grpc.Channel | None = None
        self.stub: embedding_pb2_grpc.EmbeddingServiceStub | None = None

    def __enter__(self) -> "EmbeddingServiceClient":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit."""
        self.close()

    def connect(self) -> None:
        """Establish gRPC connection."""
        logger.info(f"Connecting to Embedding Service at {self.address}")
        self.channel = grpc.insecure_channel(
            self.address,
            options=[
                ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
            ],
        )
        self.stub = embedding_pb2_grpc.EmbeddingServiceStub(self.channel)  # type: ignore[no-untyped-call]
        logger.info("Connected to Embedding Service")

    def close(self) -> None:
        """Close gRPC connection."""
        if self.channel:
            logger.info("Closing Embedding Service connection")
            self.channel.close()
            self.channel = None
            self.stub = None

    def embed(self, text: str, model: str) -> list[float]:
        """Generate embedding for a single text.

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
            response = self.stub.Embed(request, timeout=self.timeout)
            return list(response.embedding)
        except grpc.RpcError as e:
            logger.error(f"Embedding request failed: {e.code()} - {e.details()}")
            raise

    def embed_batch(self, texts: list[str], model: str) -> list[list[float]]:
        """Generate embeddings for multiple texts.

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
            response = self.stub.EmbedBatch(request, timeout=self.timeout)
            return [list(emb.embedding) for emb in response.embeddings]
        except grpc.RpcError as e:
            logger.error(f"Batch embedding request failed: {e.code()} - {e.details()}")
            raise

    def health_check(self) -> bool:
        """Check if Embedding Service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        if not self.stub:
            return False

        try:
            from src.proto_gen import common_pb2

            request = common_pb2.HealthCheckRequest()
            response = self.stub.HealthCheck(request, timeout=5.0)
            return cast(bool, response.status == common_pb2.HealthCheckResponse.HEALTHY)
        except grpc.RpcError as e:
            logger.warning(f"Health check failed: {e.code()}")
            return False
