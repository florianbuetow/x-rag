"""Unit tests for Search UI."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.search_ui.config import SearchUIConfig
from src.search_ui.models import SearchRequest, SearchResponse, Source


class TestSearchUIConfig:
    """Test Search UI configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SearchUIConfig()
        assert config.service_name == "search-ui"
        assert config.port == 8080
        assert config.search_service_addr == "search-service:50052"
        assert config.cors_enabled is True
        assert config.default_mode == "hybrid"

    def test_mode_validation(self):
        """Test search mode validation."""
        with pytest.raises(ValueError, match="Invalid mode"):
            SearchUIConfig(default_mode="invalid")


class TestSearchUIModels:
    """Test Pydantic models."""

    def test_search_request_validation(self):
        """Test SearchRequest validation."""
        # Valid request
        request = SearchRequest(
            query="test query",
            namespace="default",
            top_k=5,
            mode="hybrid",
        )
        assert request.query == "test query"
        assert request.top_k == 5

        # Invalid query (too short)
        with pytest.raises(ValueError):
            SearchRequest(query="", namespace="default")

        # Invalid top_k (too large)
        with pytest.raises(ValueError):
            SearchRequest(query="test", top_k=100)

    def test_search_response_structure(self):
        """Test SearchResponse structure."""
        response = SearchResponse(
            answer="This is an answer",
            sources=[
                Source(
                    id="chunk-1",
                    content="Source content",
                    score=0.95,
                    metadata={"title": "Doc 1"},
                ),
            ],
            metadata={"cache_hit": "false"},
        )
        assert response.answer == "This is an answer"
        assert len(response.sources) == 1
        assert response.sources[0].score == 0.95


class TestSearchUIEndpoints:
    """Test FastAPI endpoints."""

    @pytest.fixture
    def mock_search_client(self):
        """Mock Search Service client."""
        client = MagicMock()
        client.search = AsyncMock()
        client.health_check = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def app_client(self, mock_search_client):
        """Create test client with mocked dependencies."""
        with patch("src.search_ui.main.search_client", mock_search_client):
            with patch("src.search_ui.main.health_checker") as mock_health:
                mock_health.check_all = AsyncMock(
                    return_value={
                        "status": "HEALTHY",
                        "dependencies": {"search_service": "HEALTHY"},
                        "message": "All dependencies healthy",
                    },
                )
                from src.search_ui.main import app

                yield TestClient(app)

    def test_root_endpoint(self, app_client):
        """Test root endpoint returns HTML."""
        response = app_client.get("/")
        assert response.status_code == 200
        assert "X-RAG Search" in response.text

    def test_health_endpoints(self, app_client):
        """Test health check endpoints."""
        # Liveness probe
        response = app_client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

        # Readiness probe
        response = app_client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "HEALTHY"

    def test_search_endpoint_success(self, app_client, mock_search_client):
        """Test successful search request."""
        # Mock gRPC response
        from src.proto_gen import search_pb2

        mock_grpc_response = search_pb2.SearchResponse(
            answer="Python is a programming language",
            sources=[
                search_pb2.Source(
                    id="chunk-1",
                    content="Python is high-level",
                    score=0.95,
                    metadata={"title": "Python Intro"},
                ),
            ],
            metadata={"latency_ms": "150"},
        )
        mock_search_client.search.return_value = mock_grpc_response

        # Send request
        response = app_client.post(
            "/api/search",
            json={
                "query": "What is Python?",
                "namespace": "default",
                "top_k": 5,
                "mode": "hybrid",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Python is a programming language"
        assert len(data["sources"]) == 1
        assert abs(data["sources"][0]["score"] - 0.95) < 0.01  # Float precision tolerance

    def test_search_endpoint_validation(self, app_client):
        """Test search request validation."""
        # Invalid request (missing query)
        response = app_client.post(
            "/api/search",
            json={"namespace": "default"},
        )
        assert response.status_code == 422  # Validation error
