"""Health checking infrastructure for services.

Provides utilities for aggregating health checks from multiple dependencies
and converting to gRPC HealthCheckResponse format.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

import grpc
import httpx
from redis import Redis

from src.proto_gen.common_pb2 import HealthCheckResponse

logger = logging.getLogger(__name__)


class HealthChecker:
    """Aggregate health checker for services.

    Manages health checks for multiple dependencies and computes
    overall service health status.

    Example:
        checker = HealthChecker()
        checker.add_dependency("weaviate", check_weaviate, critical=True)
        checker.add_dependency("redis", check_redis, critical=False)
        status = await checker.check_all()
    """

    def __init__(self) -> None:
        """Initialize health checker."""
        self._checks: dict[str, tuple[Callable[[], Awaitable[bool]], bool]] = {}

    def add_dependency(
        self,
        name: str,
        check_func: Callable[[], Awaitable[bool]],
        critical: bool = True,
    ) -> None:
        """Add a dependency to check.

        Args:
            name: Dependency name (e.g., "weaviate", "redis")
            check_func: Async function that returns True if healthy
            critical: If True, service is unhealthy when this fails
        """
        self._checks[name] = (check_func, critical)
        logger.debug(f"Added health check for {name} (critical={critical})")

    async def check_all(self) -> dict[str, Any]:
        """Run all health checks in parallel.

        Returns:
            Dictionary with:
                - status: "HEALTHY", "DEGRADED", or "UNHEALTHY"
                - dependencies: Dict mapping dependency names to status
                - message: Human-readable status message
        """
        if not self._checks:
            return {
                "status": "HEALTHY",
                "dependencies": {},
                "message": "No dependencies configured",
            }

        # Run all checks in parallel
        results = await asyncio.gather(
            *[self._check_dependency(name, func) for name, (func, _) in self._checks.items()],
            return_exceptions=True,
        )

        # Build dependency status map
        dependencies = {}
        critical_failed = []
        non_critical_failed = []

        for (name, (_, critical)), result in zip(self._checks.items(), results, strict=True):
            if isinstance(result, Exception):
                status = "UNHEALTHY"
                logger.warning(f"Health check failed for {name}: {result}")
            elif result:
                status = "HEALTHY"
            else:
                status = "UNHEALTHY"

            dependencies[name] = status

            if status == "UNHEALTHY":
                if critical:
                    critical_failed.append(name)
                else:
                    non_critical_failed.append(name)

        # Determine overall status
        if critical_failed:
            overall_status = "UNHEALTHY"
            message = f"Critical dependencies failed: {', '.join(critical_failed)}"
        elif non_critical_failed:
            overall_status = "DEGRADED"
            message = f"Non-critical dependencies failed: {', '.join(non_critical_failed)}"
        else:
            overall_status = "HEALTHY"
            message = "All dependencies healthy"

        return {
            "status": overall_status,
            "dependencies": dependencies,
            "message": message,
        }

    async def _check_dependency(self, name: str, func: Callable[[], Awaitable[bool]]) -> bool:
        """Check a single dependency.

        Args:
            name: Dependency name
            func: Check function

        Returns:
            True if healthy, False otherwise
        """
        try:
            return await func()
        except Exception as e:
            logger.error(f"Exception during health check for {name}: {e}")
            return False

    def to_grpc_response(self, health_data: dict[str, Any]) -> HealthCheckResponse:
        """Convert health data to gRPC HealthCheckResponse.

        Args:
            health_data: Dict from check_all()

        Returns:
            gRPC HealthCheckResponse message
        """
        status_map = {
            "HEALTHY": HealthCheckResponse.HEALTHY,
            "DEGRADED": HealthCheckResponse.DEGRADED,
            "UNHEALTHY": HealthCheckResponse.UNHEALTHY,
        }

        return HealthCheckResponse(
            status=status_map.get(health_data["status"], HealthCheckResponse.UNKNOWN),
            dependencies=health_data["dependencies"],
            message=health_data["message"],
        )


# Reusable health check functions


async def check_weaviate(url: str) -> bool:
    """Check if Weaviate is ready.

    Args:
        url: Weaviate URL (e.g., "http://weaviate:8080")

    Returns:
        True if ready, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/v1/.well-known/ready")
            return response.status_code == 200
    except Exception as e:
        logger.debug(f"Weaviate health check failed: {e}")
        return False


async def check_redis(url: str) -> bool:
    """Check if Redis is responding.

    Args:
        url: Redis URL (e.g., "redis://redis:6379")

    Returns:
        True if responding, False otherwise
    """
    try:
        # Redis client is sync, run in executor
        loop = asyncio.get_event_loop()
        redis_client = Redis.from_url(url, socket_connect_timeout=5)

        def ping() -> bool:
            return cast(bool, redis_client.ping())

        result = await loop.run_in_executor(None, ping)
        redis_client.close()
        return result
    except Exception as e:
        logger.debug(f"Redis health check failed: {e}")
        return False


async def check_kafka(bootstrap_servers: str) -> bool:
    """Check if Kafka is accessible.

    Args:
        bootstrap_servers: Kafka bootstrap servers (e.g., "kafka:9092")

    Returns:
        True if accessible, False otherwise
    """
    try:
        # Simple TCP connection check
        host, port = bootstrap_servers.split(":")
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout=5.0)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        logger.debug(f"Kafka health check failed: {e}")
        return False


async def check_grpc_service(address: str, stub_class: type[Any]) -> bool:
    """Check if a gRPC service is responding.

    Args:
        address: Service address (e.g., "embedding-service:50051")
        stub_class: gRPC stub class with HealthCheck method

    Returns:
        True if responding, False otherwise
    """
    try:
        channel = grpc.aio.insecure_channel(address)
        stub = stub_class(channel)

        # Import here to avoid circular dependency
        from src.proto_gen.common_pb2 import HealthCheckRequest

        response = await asyncio.wait_for(stub.HealthCheck(HealthCheckRequest()), timeout=5.0)
        await channel.close()
        return cast(bool, response.status == HealthCheckResponse.HEALTHY)
    except Exception as e:
        logger.debug(f"gRPC service health check failed for {address}: {e}")
        return False
