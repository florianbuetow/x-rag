"""gRPC client for Search Service."""

import logging
from types import TracebackType

import grpc

from src.proto_gen import common_pb2, search_pb2, search_pb2_grpc

logger = logging.getLogger(__name__)


class SearchServiceClient:
    """Async client for Search Service gRPC API.

    Provides async methods to perform RAG searches via gRPC.
    Used by Search UI to forward search requests to the Search Service.
    """

    def __init__(self, address: str, timeout: float) -> None:
        """Initialize the Search Service client.

        Args:
            address: gRPC server address (host:port)
            timeout: Request timeout in seconds
        """
        self.address = address
        self.timeout = timeout
        self.channel: grpc.aio.Channel | None = None
        self.stub: search_pb2_grpc.SearchServiceStub | None = None

    async def __aenter__(self) -> "SearchServiceClient":
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
        logger.info(f"Connecting to Search Service at {self.address}")
        self.channel = grpc.aio.insecure_channel(
            self.address,
            options=[
                ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
            ],
        )
        self.stub = search_pb2_grpc.SearchServiceStub(self.channel)  # type: ignore[no-untyped-call]
        logger.info("✓ Connected to Search Service")

    async def close(self) -> None:
        """Close async gRPC connection."""
        if self.channel:
            logger.info("Closing Search Service connection")
            await self.channel.close()
            self.channel = None
            self.stub = None

    async def search(
        self,
        query: str,
        namespace: str,
        top_k: int,
        mode: str,
        options: dict[str, str] | None,
    ) -> search_pb2.SearchResponse:
        """Perform RAG search (async).

        Args:
            query: Search query
            namespace: Search namespace
            top_k: Number of results to return
            mode: Search mode (vector, bm25, or hybrid)
            options: Additional search options

        Returns:
            SearchResponse protobuf message

        Raises:
            grpc.RpcError: If the gRPC call fails
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = search_pb2.SearchRequest(
            query=query,
            namespace=namespace,
            top_k=top_k,
            mode=mode,
            options=options or {},
        )

        try:
            response: search_pb2.SearchResponse = await self.stub.Search(request, timeout=self.timeout)
            return response
        except grpc.RpcError as e:
            logger.error(f"Search request failed: {e.code()} - {e.details()}")
            raise

    async def health_check(self) -> bool:
        """Check if Search Service is healthy (async).

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
