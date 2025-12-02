"""Tests for health checking infrastructure."""

import pytest

from src.common.health import HealthChecker


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
