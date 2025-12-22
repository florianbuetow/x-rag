"""Unit tests for Search UI."""

from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import pytest
from fastapi.testclient import TestClient

from src.proto_gen import common_pb2, search_pb2
from src.search_ui.config import SearchUIConfig
from src.search_ui.grpc_clients import SearchServiceClient
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
        assert config.mode == "hybrid"

    def test_mode_validation(self):
        """Test search mode validation."""
        with pytest.raises(ValueError, match="Invalid mode"):
            SearchUIConfig(mode="invalid")

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SearchUIConfig(
            port=9000,
            search_service_addr="localhost:50052",
            search_service_timeout=60.0,
            cors_enabled=False,
            max_query_length=500,
            top_k=10,
            mode="vector",
        )
        assert config.port == 9000
        assert config.search_service_addr == "localhost:50052"
        assert config.search_service_timeout == 60.0
        assert config.cors_enabled is False
        assert config.max_query_length == 500
        assert config.top_k == 10
        assert config.mode == "vector"

    def test_valid_modes(self):
        """Test all valid search modes."""
        for mode in ["vector", "bm25", "hybrid"]:
            config = SearchUIConfig(mode=mode)
            assert config.mode == mode


class TestSearchUIModels:
    """Test Pydantic models."""

    def test_search_request_validation(self):
        """Test SearchRequest validation."""
        # Valid request
        request = SearchRequest(
            query="test query",
            namespace="test-ns",
            top_k=5,
            mode="hybrid",
        )
        assert request.query == "test query"
        assert request.top_k == 5

        # Invalid query (too short)
        with pytest.raises(ValueError):
            SearchRequest(query="", namespace="test-ns")

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

    def test_search_request_defaults(self):
        """Test SearchRequest default values."""
        request = SearchRequest(query="test query")
        assert request.namespace == "test-ns"
        assert request.top_k == 5
        assert request.mode == "hybrid"

    def test_search_request_modes(self):
        """Test SearchRequest with different modes."""
        for mode in ["vector", "bm25", "hybrid"]:
            request = SearchRequest(query="test", mode=mode)
            assert request.mode == mode

    def test_search_request_invalid_mode(self):
        """Test SearchRequest with invalid mode."""
        # Note: mode validation happens at config level, not model level
        # The model accepts any string for mode
        request = SearchRequest(query="test", mode="invalid")
        assert request.mode == "invalid"  # Model doesn't validate mode

    def test_search_request_boundary_top_k(self):
        """Test SearchRequest top_k boundaries."""
        # Minimum valid
        request = SearchRequest(query="test", top_k=1)
        assert request.top_k == 1

        # Maximum valid
        request = SearchRequest(query="test", top_k=50)
        assert request.top_k == 50

        # Below minimum
        with pytest.raises(ValueError):
            SearchRequest(query="test", top_k=0)

        # Above maximum
        with pytest.raises(ValueError):
            SearchRequest(query="test", top_k=51)

    def test_search_request_query_length(self):
        """Test SearchRequest query length validation."""
        # Valid short query
        request = SearchRequest(query="a")
        assert request.query == "a"

        # Valid long query
        long_query = "a" * 1000
        request = SearchRequest(query=long_query)
        assert request.query == long_query

        # Too long
        with pytest.raises(ValueError):
            SearchRequest(query="a" * 1001)

    def test_search_request_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValueError):
            SearchRequest(query="test", invalid_field="value")  # type: ignore[call-arg]

    def test_source_validation(self):
        """Test Source model validation."""
        source = Source(
            id="test-id",
            content="test content",
            score=0.85,
            metadata={"key": "value"},
        )
        assert source.id == "test-id"
        assert source.score == 0.85

    def test_search_response_empty_sources(self):
        """Test SearchResponse with no sources."""
        response = SearchResponse(
            answer="No results found",
            sources=[],
            metadata={},
        )
        assert len(response.sources) == 0
        assert response.answer == "No results found"

    def test_search_response_multiple_sources(self):
        """Test SearchResponse with multiple sources."""
        response = SearchResponse(
            answer="Answer from multiple sources",
            sources=[
                Source(id="1", content="Content 1", score=0.9, metadata={}),
                Source(id="2", content="Content 2", score=0.8, metadata={}),
                Source(id="3", content="Content 3", score=0.7, metadata={}),
            ],
            metadata={},
        )
        assert len(response.sources) == 3
        assert response.sources[0].score > response.sources[1].score
        assert response.sources[1].score > response.sources[2].score


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
        with (
            patch("src.search_ui.main.search_client", mock_search_client),
            patch("src.search_ui.main.health_checker") as mock_health,
        ):
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
                "namespace": "test-ns",
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
            json={"namespace": "test-ns"},
        )
        assert response.status_code == 422  # Validation error

    def test_search_endpoint_client_not_initialized(self, app_client):
        """Test search when client is not initialized."""
        with patch("src.search_ui.main.search_client", None):
            response = app_client.post(
                "/api/search",
                json={"query": "test", "namespace": "test-ns"},
            )
            # Returns 503 Service Unavailable when client not initialized
            assert response.status_code == 503
            assert "not initialized" in response.json()["detail"]

    def test_search_endpoint_grpc_error(self, app_client, mock_search_client):
        """Test search when gRPC call fails."""
        # Simulate gRPC error
        mock_error = MagicMock()
        mock_error.code = MagicMock(return_value=grpc.StatusCode.UNAVAILABLE)
        mock_error.details = MagicMock(return_value="Service unavailable")
        mock_search_client.search.side_effect = mock_error

        response = app_client.post(
            "/api/search",
            json={"query": "test", "namespace": "test-ns"},
        )
        assert response.status_code == 500

    def test_search_endpoint_with_different_modes(self, app_client, mock_search_client):
        """Test search with different modes."""
        from src.proto_gen import search_pb2

        for mode in ["vector", "bm25", "hybrid"]:
            mock_grpc_response = search_pb2.SearchResponse(
                answer=f"Answer for {mode}",
                sources=[],
                metadata={"mode": mode},
            )
            mock_search_client.search.return_value = mock_grpc_response

            response = app_client.post(
                "/api/search",
                json={"query": "test", "mode": mode},
            )
            assert response.status_code == 200
            assert response.json()["metadata"]["mode"] == mode

    def test_health_endpoint_unhealthy(self, app_client):
        """Test health endpoint when service is unhealthy."""
        with patch("src.search_ui.main.health_checker") as mock_health:
            mock_health.check_all = AsyncMock(
                return_value={
                    "status": "UNHEALTHY",
                    "dependencies": {"search_service": "UNHEALTHY"},
                    "message": "Search service unavailable",
                }
            )
            response = app_client.get("/health")
            assert response.status_code == 503

    def test_health_endpoint_checker_not_initialized(self, app_client):
        """Test health endpoint when checker is not initialized."""
        with patch("src.search_ui.main.health_checker", None):
            response = app_client.get("/health")
            assert response.status_code == 503

    def test_readiness_endpoint_unhealthy(self, app_client):
        """Test readiness endpoint when service is unhealthy."""
        with patch("src.search_ui.main.health_checker") as mock_health:
            mock_health.check_all = AsyncMock(
                return_value={
                    "status": "UNHEALTHY",
                    "dependencies": {"search_service": "UNHEALTHY"},
                }
            )
            response = app_client.get("/health/ready")
            assert response.status_code == 503

    def test_search_endpoint_empty_sources(self, app_client, mock_search_client):
        """Test search with no sources returned."""
        from src.proto_gen import search_pb2

        mock_grpc_response = search_pb2.SearchResponse(
            answer="No results found",
            sources=[],
            metadata={},
        )
        mock_search_client.search.return_value = mock_grpc_response

        response = app_client.post(
            "/api/search",
            json={"query": "test"},
        )
        assert response.status_code == 200
        assert len(response.json()["sources"]) == 0


class TestSearchServiceClient:
    """Test Search Service gRPC client."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)
        assert client.address == "localhost:50052"
        assert client.timeout == 30.0
        assert client.channel is None
        assert client.stub is None

    @pytest.mark.asyncio
    async def test_client_connect(self):
        """Test client connection."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_stub_class = MagicMock()
            with patch("src.search_ui.grpc_clients.search_pb2_grpc.SearchServiceStub", mock_stub_class):
                await client.connect()

                # Verify channel created with correct options
                mock_channel.assert_called_once()
                call_args = mock_channel.call_args
                assert call_args[0][0] == "localhost:50052"
                options = call_args[1]["options"]
                assert ("grpc.max_send_message_length", 100 * 1024 * 1024) in options
                assert ("grpc.max_receive_message_length", 100 * 1024 * 1024) in options

                # Verify stub created
                assert client.stub is not None

    @pytest.mark.asyncio
    async def test_client_close(self):
        """Test client close."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        # Mock channel
        mock_channel = AsyncMock()
        client.channel = mock_channel
        client.stub = MagicMock()

        await client.close()

        # Verify channel closed
        mock_channel.close.assert_called_once()
        assert client.channel is None
        assert client.stub is None

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client as async context manager."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        with (
            patch.object(client, "connect", new_callable=AsyncMock) as mock_connect,
            patch.object(client, "close", new_callable=AsyncMock) as mock_close,
        ):
            async with client as ctx_client:
                assert ctx_client is client
                mock_connect.assert_called_once()

            # Verify close called after exit
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search request."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        # Mock stub
        mock_stub = MagicMock()
        mock_response = search_pb2.SearchResponse(
            answer="Test answer",
            sources=[],
            metadata={},
        )
        mock_stub.Search = AsyncMock(return_value=mock_response)
        client.stub = mock_stub

        # Perform search
        response = await client.search(
            query="test query",
            namespace="test-ns",
            top_k=5,
            mode="hybrid",
            options=None,
        )

        # Verify response
        assert response == mock_response
        mock_stub.Search.assert_called_once()

        # Verify request parameters
        call_args = mock_stub.Search.call_args
        request = call_args[0][0]
        assert request.query == "test query"
        assert request.namespace == "test-ns"
        assert request.top_k == 5
        assert request.mode == "hybrid"

    @pytest.mark.asyncio
    async def test_search_with_options(self):
        """Test search with additional options."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        mock_stub = MagicMock()
        mock_stub.Search = AsyncMock(return_value=search_pb2.SearchResponse(answer="", sources=[], metadata={}))
        client.stub = mock_stub

        await client.search(
            query="test",
            namespace="test-ns",
            top_k=5,
            mode="hybrid",
            options={"cache": "true", "explain": "true"},
        )

        call_args = mock_stub.Search.call_args
        request = call_args[0][0]
        assert request.options["cache"] == "true"
        assert request.options["explain"] == "true"

    @pytest.mark.asyncio
    async def test_search_not_connected(self):
        """Test search when client not connected."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.search(query="test", namespace="test-ns", top_k=5, mode="hybrid", options=None)

    @pytest.mark.asyncio
    async def test_search_grpc_error(self):
        """Test search when gRPC error occurs."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        # Mock stub with error - create a real exception
        class MockRpcError(grpc.RpcError, Exception):
            def code(self):
                return grpc.StatusCode.UNAVAILABLE

            def details(self):
                return "Service unavailable"

        mock_stub = MagicMock()
        mock_stub.Search = AsyncMock(side_effect=MockRpcError())
        client.stub = mock_stub

        with pytest.raises(grpc.RpcError):
            await client.search(query="test", namespace="test-ns", top_k=5, mode="hybrid", options=None)

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        # Mock stub
        mock_stub = MagicMock()
        mock_response = common_pb2.HealthCheckResponse(status=common_pb2.HealthCheckResponse.HEALTHY)
        mock_stub.HealthCheck = AsyncMock(return_value=mock_response)
        client.stub = mock_stub

        # Perform health check
        result = await client.health_check()

        assert result is True
        mock_stub.HealthCheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """Test health check when service is unhealthy."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        mock_stub = MagicMock()
        mock_response = common_pb2.HealthCheckResponse(status=common_pb2.HealthCheckResponse.UNHEALTHY)
        mock_stub.HealthCheck = AsyncMock(return_value=mock_response)
        client.stub = mock_stub

        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when client not connected."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_grpc_error(self):
        """Test health check when gRPC error occurs."""
        client = SearchServiceClient(address="localhost:50052", timeout=30.0)

        # Create a real RpcError exception
        class MockRpcError(grpc.RpcError, Exception):
            def code(self):
                return grpc.StatusCode.UNAVAILABLE

        mock_stub = MagicMock()
        mock_stub.HealthCheck = AsyncMock(side_effect=MockRpcError())
        client.stub = mock_stub

        result = await client.health_check()
        assert result is False
