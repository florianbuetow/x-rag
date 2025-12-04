"""Tests for health checking infrastructure."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.health import (
    HealthChecker,
    check_grpc_service,
    check_kafka,
    check_redis,
    check_weaviate,
)


@pytest.mark.asyncio
async def test_health_checker_no_dependencies():
    """Test HealthChecker with no dependencies."""
    checker = HealthChecker()
    result = await checker.check_all()

    assert result["status"] == "HEALTHY"
    assert result["dependencies"] == {}
    assert "No dependencies" in result["message"]


@pytest.mark.asyncio
async def test_health_checker_all_healthy():
    """Test HealthChecker with all healthy dependencies."""
    checker = HealthChecker()

    async def check_service1():
        return True

    async def check_service2():
        return True

    checker.add_dependency("service1", check_service1, critical=True)
    checker.add_dependency("service2", check_service2, critical=False)

    result = await checker.check_all()

    assert result["status"] == "HEALTHY"
    assert result["dependencies"]["service1"] == "HEALTHY"
    assert result["dependencies"]["service2"] == "HEALTHY"
    assert "All dependencies healthy" in result["message"]


@pytest.mark.asyncio
async def test_health_checker_critical_failure():
    """Test HealthChecker with critical dependency failure."""
    checker = HealthChecker()

    async def check_healthy():
        return True

    async def check_failed():
        return False

    checker.add_dependency("healthy_service", check_healthy, critical=False)
    checker.add_dependency("critical_service", check_failed, critical=True)

    result = await checker.check_all()

    assert result["status"] == "UNHEALTHY"
    assert result["dependencies"]["healthy_service"] == "HEALTHY"
    assert result["dependencies"]["critical_service"] == "UNHEALTHY"
    assert "Critical dependencies failed" in result["message"]
    assert "critical_service" in result["message"]


@pytest.mark.asyncio
async def test_health_checker_non_critical_failure():
    """Test HealthChecker with non-critical dependency failure."""
    checker = HealthChecker()

    async def check_healthy():
        return True

    async def check_failed():
        return False

    checker.add_dependency("critical_service", check_healthy, critical=True)
    checker.add_dependency("cache_service", check_failed, critical=False)

    result = await checker.check_all()

    assert result["status"] == "DEGRADED"
    assert result["dependencies"]["critical_service"] == "HEALTHY"
    assert result["dependencies"]["cache_service"] == "UNHEALTHY"
    assert "Non-critical dependencies failed" in result["message"]
    assert "cache_service" in result["message"]


@pytest.mark.asyncio
async def test_health_checker_exception_handling():
    """Test HealthChecker handles exceptions in check functions."""
    checker = HealthChecker()

    async def check_raises():
        raise RuntimeError("Service check failed")

    checker.add_dependency("problematic_service", check_raises, critical=True)

    result = await checker.check_all()

    assert result["status"] == "UNHEALTHY"
    assert result["dependencies"]["problematic_service"] == "UNHEALTHY"


@pytest.mark.asyncio
async def test_to_grpc_response():
    """Test conversion to gRPC HealthCheckResponse."""
    from src.proto_gen.common_pb2 import HealthCheckResponse

    checker = HealthChecker()

    async def check_ok():
        return True

    checker.add_dependency("service", check_ok, critical=True)

    health_data = await checker.check_all()
    grpc_response = checker.to_grpc_response(health_data)

    assert grpc_response.status == HealthCheckResponse.HEALTHY
    assert grpc_response.dependencies["service"] == "HEALTHY"
    assert grpc_response.message == health_data["message"]


@pytest.mark.asyncio
async def test_to_grpc_response_degraded():
    """Test conversion to gRPC HealthCheckResponse for DEGRADED status."""
    from src.proto_gen.common_pb2 import HealthCheckResponse

    checker = HealthChecker()

    async def check_ok():
        return True

    async def check_fail():
        return False

    checker.add_dependency("critical", check_ok, critical=True)
    checker.add_dependency("non_critical", check_fail, critical=False)

    health_data = await checker.check_all()
    grpc_response = checker.to_grpc_response(health_data)

    assert grpc_response.status == HealthCheckResponse.DEGRADED


@pytest.mark.asyncio
async def test_to_grpc_response_unhealthy():
    """Test conversion to gRPC HealthCheckResponse for UNHEALTHY status."""
    from src.proto_gen.common_pb2 import HealthCheckResponse

    checker = HealthChecker()

    async def check_fail():
        return False

    checker.add_dependency("critical", check_fail, critical=True)

    health_data = await checker.check_all()
    grpc_response = checker.to_grpc_response(health_data)

    assert grpc_response.status == HealthCheckResponse.UNHEALTHY


@pytest.mark.asyncio
async def test_to_grpc_response_unknown_status():
    """Test conversion to gRPC HealthCheckResponse for unknown status."""
    from src.proto_gen.common_pb2 import HealthCheckResponse

    checker = HealthChecker()

    # Manually create health data with unknown status
    health_data = {
        "status": "INVALID_STATUS",
        "dependencies": {},
        "message": "Test",
    }
    grpc_response = checker.to_grpc_response(health_data)

    assert grpc_response.status == HealthCheckResponse.UNKNOWN


# Tests for check_weaviate function


@pytest.mark.asyncio
async def test_check_weaviate_healthy():
    """Test check_weaviate returns True when Weaviate is ready."""
    with patch("src.common.health.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await check_weaviate("http://weaviate:8080")

        assert result is True
        mock_client.get.assert_called_once_with("http://weaviate:8080/v1/.well-known/ready")


@pytest.mark.asyncio
async def test_check_weaviate_unhealthy():
    """Test check_weaviate returns False when Weaviate is not ready."""
    with patch("src.common.health.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await check_weaviate("http://weaviate:8080")

        assert result is False


@pytest.mark.asyncio
async def test_check_weaviate_exception():
    """Test check_weaviate returns False on exception."""
    with patch("src.common.health.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await check_weaviate("http://weaviate:8080")

        assert result is False


# Tests for check_redis function


@pytest.mark.asyncio
async def test_check_redis_healthy():
    """Test check_redis returns True when Redis is responding."""
    with patch("src.common.health.Redis") as mock_redis_class:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis_class.from_url.return_value = mock_redis

        result = await check_redis("redis://redis:6379")

        assert result is True
        mock_redis_class.from_url.assert_called_once_with("redis://redis:6379", socket_connect_timeout=5)
        mock_redis.ping.assert_called_once()
        mock_redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_check_redis_exception():
    """Test check_redis returns False on exception."""
    with patch("src.common.health.Redis") as mock_redis_class:
        mock_redis_class.from_url.side_effect = Exception("Connection refused")

        result = await check_redis("redis://redis:6379")

        assert result is False


# Tests for check_kafka function


@pytest.mark.asyncio
async def test_check_kafka_healthy():
    """Test check_kafka returns True when Kafka is accessible."""
    mock_reader = MagicMock()
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("src.common.health.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        result = await check_kafka("kafka:9092")

        assert result is True
        mock_open.assert_called_once_with("kafka", 9092)
        mock_writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_check_kafka_exception():
    """Test check_kafka returns False on exception."""
    with patch("src.common.health.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
        mock_open.side_effect = Exception("Connection refused")

        result = await check_kafka("kafka:9092")

        assert result is False


# Tests for check_grpc_service function


@pytest.mark.asyncio
async def test_check_grpc_service_healthy():
    """Test check_grpc_service returns True when gRPC service is healthy."""
    from src.proto_gen.common_pb2 import HealthCheckResponse

    mock_stub = MagicMock()
    mock_response = MagicMock()
    mock_response.status = HealthCheckResponse.HEALTHY
    mock_stub.HealthCheck = AsyncMock(return_value=mock_response)

    mock_stub_class = MagicMock(return_value=mock_stub)

    mock_channel = MagicMock()
    mock_channel.close = AsyncMock()

    with patch("src.common.health.grpc.aio.insecure_channel", return_value=mock_channel):
        result = await check_grpc_service("embedding-service:50051", mock_stub_class)

        assert result is True
        mock_stub_class.assert_called_once_with(mock_channel)
        mock_channel.close.assert_called_once()


@pytest.mark.asyncio
async def test_check_grpc_service_unhealthy():
    """Test check_grpc_service returns False when gRPC service is unhealthy."""
    from src.proto_gen.common_pb2 import HealthCheckResponse

    mock_stub = MagicMock()
    mock_response = MagicMock()
    mock_response.status = HealthCheckResponse.UNHEALTHY
    mock_stub.HealthCheck = AsyncMock(return_value=mock_response)

    mock_stub_class = MagicMock(return_value=mock_stub)

    mock_channel = MagicMock()
    mock_channel.close = AsyncMock()

    with patch("src.common.health.grpc.aio.insecure_channel", return_value=mock_channel):
        result = await check_grpc_service("embedding-service:50051", mock_stub_class)

        assert result is False


@pytest.mark.asyncio
async def test_check_grpc_service_exception():
    """Test check_grpc_service returns False on exception."""
    mock_stub_class = MagicMock(side_effect=Exception("Connection failed"))

    with patch("src.common.health.grpc.aio.insecure_channel"):
        result = await check_grpc_service("embedding-service:50051", mock_stub_class)

        assert result is False


@pytest.mark.asyncio
async def test_check_all_with_exception_result():
    """Test check_all handles exception results from asyncio.gather."""
    checker = HealthChecker()

    async def check_raises():
        raise RuntimeError("Check failed")

    async def check_ok():
        return True

    checker.add_dependency("failing", check_raises, critical=True)
    checker.add_dependency("healthy", check_ok, critical=False)

    result = await checker.check_all()

    assert result["status"] == "UNHEALTHY"
    assert result["dependencies"]["failing"] == "UNHEALTHY"
    assert result["dependencies"]["healthy"] == "HEALTHY"
