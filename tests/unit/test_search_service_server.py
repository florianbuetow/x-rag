"""Tests for Search Service gRPC server implementation."""

import grpc
import pytest

from src.proto_gen import common_pb2, search_pb2
from src.search_service.server import SearchServicer
from tests.conftest import GrpcAbortException


class TestSearchServicerInit:
    """Tests for SearchServicer initialization."""

    def test_initialization_with_pipeline_and_config(
        self,
        mock_search_pipeline,
        search_service_config,
    ):
        """Servicer initializes with SearchPipeline and config."""
        servicer = SearchServicer(
            pipeline=mock_search_pipeline,
            config=search_service_config,
        )

        assert servicer.pipeline is mock_search_pipeline
        assert servicer.config is search_service_config

    def test_initialization_stores_config_values(
        self,
        mock_search_pipeline,
        search_service_config,
    ):
        """Servicer has access to configuration values."""
        servicer = SearchServicer(
            pipeline=mock_search_pipeline,
            config=search_service_config,
        )

        assert servicer.config.default_top_k == 10
        assert servicer.config.default_mode == "hybrid"
        assert servicer.config.hybrid_alpha == 0.5


class TestSearchMethod:
    """Tests for Search gRPC method."""

    @pytest.fixture
    def servicer(self, mock_search_pipeline, search_service_config):
        """Create a SearchServicer instance for testing."""
        return SearchServicer(
            pipeline=mock_search_pipeline,
            config=search_service_config,
        )

    @pytest.mark.asyncio
    async def test_search_empty_query_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Empty query returns INVALID_ARGUMENT error."""
        request = search_pb2.SearchRequest(query="")

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "Query cannot be empty" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_whitespace_query_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Whitespace-only query is treated as empty (passes validation but results may vary)."""
        # Note: Current implementation doesn't strip whitespace, so this test documents behavior
        request = search_pb2.SearchRequest(query="   ")

        # Whitespace is technically non-empty, so it passes validation
        # Setup pipeline to return a result
        servicer.pipeline.search.return_value = {
            "answer": "No results found.",
            "sources": [],
            "metadata": {
                "mode": "hybrid",
                "top_k": 10,
                "namespace": "default",
                "cache_hit": False,
                "num_sources": 0,
            },
        }

        await servicer.Search(request, mock_async_grpc_context)

        # Verify pipeline was called (whitespace query passes validation)
        servicer.pipeline.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_top_k_zero_uses_default(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """top_k=0 is treated as 'not specified' and uses config default.

        Note: This is due to `top_k = request.top_k or default` in server code.
        The value 0 is falsy, so it falls back to the default.
        """
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="test query",
            top_k=0,  # Falsy value, will use default
        )

        await servicer.Search(request, mock_async_grpc_context)

        # Verify default top_k was used
        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["top_k"] == 10  # Default from config

    @pytest.mark.asyncio
    async def test_search_invalid_top_k_negative_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Negative top_k returns INVALID_ARGUMENT error."""
        request = search_pb2.SearchRequest(
            query="test query",
            top_k=-5,
        )

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "top_k must be positive" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_invalid_top_k_exceeds_max_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """top_k > 100 returns INVALID_ARGUMENT error."""
        request = search_pb2.SearchRequest(
            query="test query",
            top_k=101,
        )

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "top_k too large" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_invalid_mode_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Invalid mode returns INVALID_ARGUMENT error."""
        request = search_pb2.SearchRequest(
            query="test query",
            mode="invalid_mode",
        )

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "Invalid mode" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_invalid_alpha_below_zero_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """alpha < 0 returns INVALID_ARGUMENT error."""
        request = search_pb2.SearchRequest(
            query="test query",
            mode="hybrid",
            options={"alpha": "-0.5"},
        )

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "alpha must be between 0.0 and 1.0" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_invalid_alpha_above_one_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """alpha > 1 returns INVALID_ARGUMENT error."""
        request = search_pb2.SearchRequest(
            query="test query",
            mode="hybrid",
            options={"alpha": "1.5"},
        )

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "alpha must be between 0.0 and 1.0" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_invalid_alpha_non_numeric_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Non-numeric alpha returns INVALID_ARGUMENT error."""
        request = search_pb2.SearchRequest(
            query="test query",
            mode="hybrid",
            options={"alpha": "not_a_number"},
        )

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "Invalid alpha value" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_successful_vector_mode(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """Successful search with vector mode returns answer and sources."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="What is machine learning?",
            mode="vector",
            top_k=10,
        )

        response = await servicer.Search(request, mock_async_grpc_context)

        # Verify pipeline was called with correct parameters
        servicer.pipeline.search.assert_called_once()
        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["query"] == "What is machine learning?"
        assert call_kwargs["mode"] == "vector"
        assert call_kwargs["top_k"] == 10

        # Verify response
        assert response.answer == sample_search_result["answer"]
        assert len(response.sources) == 2
        assert response.sources[0].id == "doc1"
        assert response.sources[0].score == pytest.approx(0.95, rel=1e-5)

    @pytest.mark.asyncio
    async def test_search_successful_bm25_mode(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """Successful search with bm25 mode."""
        sample_search_result["metadata"]["mode"] = "bm25"
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="machine learning",
            mode="bm25",
            top_k=5,
        )

        response = await servicer.Search(request, mock_async_grpc_context)

        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["mode"] == "bm25"
        assert response.metadata["mode"] == "bm25"

    @pytest.mark.asyncio
    async def test_search_successful_hybrid_mode_with_alpha(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """Successful search with hybrid mode and custom alpha."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="machine learning",
            mode="hybrid",
            options={"alpha": "0.7"},
        )

        await servicer.Search(request, mock_async_grpc_context)

        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["mode"] == "hybrid"
        assert call_kwargs["alpha"] == 0.7

    @pytest.mark.asyncio
    async def test_search_uses_default_top_k(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """When top_k not specified, uses config default."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="test query",
            # top_k not specified
        )

        await servicer.Search(request, mock_async_grpc_context)

        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["top_k"] == 10  # Default from config

    @pytest.mark.asyncio
    async def test_search_uses_default_mode(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """When mode not specified, uses config default."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="test query",
            # mode not specified
        )

        await servicer.Search(request, mock_async_grpc_context)

        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["mode"] == "hybrid"  # Default from config

    @pytest.mark.asyncio
    async def test_search_uses_default_namespace(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """When namespace not specified, uses 'default'."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="test query",
            # namespace not specified
        )

        await servicer.Search(request, mock_async_grpc_context)

        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["namespace"] == "default"

    @pytest.mark.asyncio
    async def test_search_with_custom_namespace(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """Search with custom namespace."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(
            query="test query",
            namespace="custom-namespace",
        )

        await servicer.Search(request, mock_async_grpc_context)

        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["namespace"] == "custom-namespace"

    @pytest.mark.asyncio
    async def test_search_response_metadata(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """Search response includes correct metadata."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(query="test query")

        response = await servicer.Search(request, mock_async_grpc_context)

        assert response.metadata["mode"] == "hybrid"
        assert response.metadata["top_k"] == "10"
        assert response.metadata["namespace"] == "default"
        assert response.metadata["cache_hit"] == "False"
        assert response.metadata["num_sources"] == "2"

    @pytest.mark.asyncio
    async def test_search_pipeline_exception_returns_internal_error(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Pipeline exception returns INTERNAL error."""
        servicer.pipeline.search.side_effect = RuntimeError("Pipeline failed")

        request = search_pb2.SearchRequest(query="test query")

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Search(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INTERNAL
        assert "Internal error" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_search_passes_openai_config(
        self,
        servicer,
        mock_async_grpc_context,
        sample_search_result,
    ):
        """Search passes OpenAI configuration to pipeline."""
        servicer.pipeline.search.return_value = sample_search_result

        request = search_pb2.SearchRequest(query="test query")

        await servicer.Search(request, mock_async_grpc_context)

        call_kwargs = servicer.pipeline.search.call_args[1]
        assert call_kwargs["openai_max_tokens"] == 500
        assert call_kwargs["openai_temperature"] == 0.7


class TestHealthCheckMethod:
    """Tests for HealthCheck gRPC method."""

    @pytest.fixture
    def servicer(self, mock_search_pipeline, search_service_config):
        """Create a SearchServicer instance for testing."""
        return SearchServicer(
            pipeline=mock_search_pipeline,
            config=search_service_config,
        )

    @pytest.fixture
    def servicer_dev_mode(self, mock_search_pipeline, search_service_config_dev_mode):
        """Create a SearchServicer with dev mode config."""
        return SearchServicer(
            pipeline=mock_search_pipeline,
            config=search_service_config_dev_mode,
        )

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """All dependencies healthy returns HEALTHY status."""
        # All mocks default to healthy (see conftest fixtures)
        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.HEALTHY
        assert response.dependencies["weaviate"] == "HEALTHY"
        assert response.dependencies["embedding_service"] == "HEALTHY"
        assert response.dependencies["openai"] == "HEALTHY"
        assert "healthy" in response.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_weaviate_unhealthy(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Weaviate unhealthy returns UNHEALTHY (critical)."""
        servicer.pipeline.retriever.health_check.return_value = False

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["weaviate"] == "UNHEALTHY"
        assert "unhealthy" in response.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_embedding_service_unhealthy(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Embedding service unhealthy returns UNHEALTHY (critical)."""
        servicer.pipeline.embedding_client.health_check.return_value = False

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["embedding_service"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_health_check_openai_unhealthy_with_real_key(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """OpenAI unhealthy with real key returns UNHEALTHY (critical)."""
        servicer.pipeline.llm_client.health_check.return_value = False

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        # OpenAI is critical when using a real key
        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["openai"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_health_check_openai_unhealthy_dev_mode(
        self,
        servicer_dev_mode,
        mock_async_grpc_context,
    ):
        """OpenAI unhealthy with placeholder key returns HEALTHY (dev mode)."""
        servicer_dev_mode.pipeline.llm_client.health_check.return_value = False

        request = common_pb2.HealthCheckRequest()

        response = await servicer_dev_mode.HealthCheck(request, mock_async_grpc_context)

        # OpenAI is non-critical with placeholder key
        assert response.status == common_pb2.HealthCheckResponse.HEALTHY
        assert response.dependencies["openai"] == "UNHEALTHY"
        assert "dev mode" in response.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_weaviate_exception(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Exception during Weaviate health check returns UNHEALTHY."""
        servicer.pipeline.retriever.health_check.side_effect = RuntimeError("Connection failed")

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["weaviate"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_health_check_embedding_service_exception(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Exception during Embedding Service health check returns UNHEALTHY."""
        servicer.pipeline.embedding_client.health_check.side_effect = RuntimeError("gRPC error")

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["embedding_service"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_health_check_openai_exception_dev_mode(
        self,
        servicer_dev_mode,
        mock_async_grpc_context,
    ):
        """Exception during OpenAI health check in dev mode returns HEALTHY."""
        servicer_dev_mode.pipeline.llm_client.health_check.side_effect = RuntimeError("API error")

        request = common_pb2.HealthCheckRequest()

        response = await servicer_dev_mode.HealthCheck(request, mock_async_grpc_context)

        # OpenAI exception with placeholder key doesn't affect overall status
        assert response.status == common_pb2.HealthCheckResponse.HEALTHY
        assert response.dependencies["openai"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_health_check_multiple_failures(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Multiple dependency failures still returns UNHEALTHY."""
        servicer.pipeline.retriever.health_check.return_value = False
        servicer.pipeline.embedding_client.health_check.return_value = False
        servicer.pipeline.llm_client.health_check.return_value = False

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["weaviate"] == "UNHEALTHY"
        assert response.dependencies["embedding_service"] == "UNHEALTHY"
        assert response.dependencies["openai"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_health_check_unexpected_exception(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Unexpected exception during health check returns UNHEALTHY."""

        # Force an exception by making health_check raise an unexpected error type
        def raise_unexpected():
            raise AttributeError("Unexpected attribute error")

        servicer.pipeline.retriever.health_check = raise_unexpected

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        # Should handle exception gracefully - weaviate will be unhealthy
        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["weaviate"] == "UNHEALTHY"
