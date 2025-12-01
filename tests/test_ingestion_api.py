"""Tests for Ingestion API."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create test FastAPI app."""
    from src.ingestion_api.main import app

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "ingestion-api"
    assert data["version"] == "0.1.0"
    assert data["status"] == "operational"


def test_liveness(client):
    """Test liveness probe."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


# Note: Full integration tests for /ingest and /health/ready require
# MinIO and Kafka to be running. These will be added in E2E tests.
# For now, we test the endpoints that don't require dependencies.
