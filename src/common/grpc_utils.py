"""gRPC utilities for client and server management."""

import logging
from concurrent import futures
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Generator, Type

import grpc
from grpc_reflection.v1alpha import reflection

logger = logging.getLogger(__name__)


class GrpcClient:
    """Base gRPC client with connection management.

    Usage:
        with GrpcClient("localhost:50051", EmbeddingServiceStub) as client:
            response = client.stub.Embed(request)
    """

    def __init__(
        self,
        address: str,
        stub_class: Type[Any],
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize gRPC client.

        Args:
            address: Server address (e.g., "localhost:50051")
            stub_class: gRPC stub class
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.address = address
        self.stub_class = stub_class
        self.timeout = timeout
        self.max_retries = max_retries
        self.channel: grpc.Channel | None = None
        self.stub: Any = None

    def __enter__(self) -> "GrpcClient":
        """Open connection."""
        self.channel = grpc.insecure_channel(
            self.address,
            options=[
                ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
                ("grpc.keepalive_permit_without_calls", True),
                ("grpc.http2.max_pings_without_data", 0),
            ],
        )
        self.stub = self.stub_class(self.channel)
        logger.info(f"Connected to gRPC server at {self.address}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Close connection."""
        if self.channel:
            self.channel.close()
            logger.info(f"Disconnected from gRPC server at {self.address}")

    @contextmanager
    def call_with_retry(self, method_name: str) -> Generator[Any, None, None]:
        """Execute gRPC call with retry logic.

        Usage:
            with client.call_with_retry("Embed") as call:
                response = call(request)
        """
        for attempt in range(self.max_retries):
            try:
                yield getattr(self.stub, method_name)
                break
            except grpc.RpcError as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"gRPC call failed after {self.max_retries} attempts: {e.code()}: {e.details()}")
                    raise
                logger.warning(f"gRPC call failed (attempt {attempt + 1}/{self.max_retries}): {e.code()}: {e.details()}")


def create_grpc_server(
    port: int,
    max_workers: int = 10,
    enable_reflection: bool = True,
    service_names: list[str] | None = None,
) -> grpc.Server:
    """Create gRPC server with standard configuration.

    Args:
        port: Port to listen on
        max_workers: Maximum number of worker threads
        enable_reflection: Enable server reflection for debugging (grpcurl)
        service_names: List of service names for reflection

    Returns:
        Configured gRPC server
    """
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
            ("grpc.keepalive_time_ms", 10000),
            ("grpc.keepalive_timeout_ms", 5000),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.http2.max_pings_without_data", 0),
        ],
    )

    # Enable reflection for debugging with grpcurl
    if enable_reflection and service_names:
        reflection.enable_server_reflection(service_names, server)
        logger.info(f"Server reflection enabled for: {', '.join(service_names)}")

    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"gRPC server configured on port {port}")

    return server


def grpc_status_to_health(status: grpc.StatusCode) -> str:
    """Convert gRPC status code to health status string.

    Args:
        status: gRPC status code

    Returns:
        Health status: "HEALTHY", "DEGRADED", or "UNHEALTHY"
    """
    if status == grpc.StatusCode.OK:
        return "HEALTHY"
    elif status in (grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.RESOURCE_EXHAUSTED):
        return "DEGRADED"
    else:
        return "UNHEALTHY"
