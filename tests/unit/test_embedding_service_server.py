"""Tests for Embedding Service gRPC server implementation."""

import grpc
import pytest

from src.core.errors import ServiceUnavailableError
from src.embedding_service.server import EmbeddingServicer
from src.proto_gen import common_pb2, embedding_pb2
from tests.conftest import GrpcAbortException


class TestEmbeddingServicerInit:
    """Tests for EmbeddingServicer initialization."""

    def test_initialization_with_generator(self, mock_embedding_generator):
        """Servicer initializes with EmbeddingGenerator."""
        servicer = EmbeddingServicer(
            generator=mock_embedding_generator,
            default_model="text-embedding-3-small",
        )

        assert servicer.generator is mock_embedding_generator
        assert servicer.default_model == "text-embedding-3-small"

    def test_initialization_with_default_model(self, mock_embedding_generator):
        """Servicer uses default model parameter."""
        servicer = EmbeddingServicer(
            generator=mock_embedding_generator,
            default_model="custom-model",
        )

        assert servicer.default_model == "custom-model"

    def test_initialization_creates_health_checker(self, mock_embedding_generator):
        """Servicer creates HealthChecker on init."""
        servicer = EmbeddingServicer(generator=mock_embedding_generator)

        assert servicer.health_checker is not None


class TestEmbedMethod:
    """Tests for Embed gRPC method."""

    @pytest.fixture
    def servicer(self, mock_embedding_generator):
        """Create an EmbeddingServicer instance for testing."""
        return EmbeddingServicer(
            generator=mock_embedding_generator,
            default_model="text-embedding-3-small",
        )

    @pytest.mark.asyncio
    async def test_embed_empty_text_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Empty text returns INVALID_ARGUMENT error."""
        request = embedding_pb2.EmbedRequest(text="")

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Embed(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "Text cannot be empty" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_embed_uses_request_model(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Uses model from request when specified."""
        servicer.generator.embed.return_value = [0.1, 0.2, 0.3]
        servicer.generator.get_dimension.return_value = 3

        request = embedding_pb2.EmbedRequest(
            text="test text",
            model="custom-model",
        )

        response = await servicer.Embed(request, mock_async_grpc_context)

        servicer.generator.embed.assert_called_once_with(
            "test text",
            "custom-model",
        )
        assert response.model == "custom-model"

    @pytest.mark.asyncio
    async def test_embed_uses_default_model(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Uses default model when not specified in request."""
        servicer.generator.embed.return_value = [0.1, 0.2, 0.3]
        servicer.generator.get_dimension.return_value = 3

        request = embedding_pb2.EmbedRequest(text="test text")

        response = await servicer.Embed(request, mock_async_grpc_context)

        servicer.generator.embed.assert_called_once_with(
            "test text",
            "text-embedding-3-small",
        )
        assert response.model == "text-embedding-3-small"

    @pytest.mark.asyncio
    async def test_embed_successful_generation(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Successful embedding returns vector and dimension."""
        expected_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        servicer.generator.embed.return_value = expected_embedding
        servicer.generator.get_dimension.return_value = 5

        request = embedding_pb2.EmbedRequest(text="test text")

        response = await servicer.Embed(request, mock_async_grpc_context)

        assert list(response.embedding) == pytest.approx(expected_embedding, rel=1e-5)
        assert response.dimension == 5
        assert response.model == "text-embedding-3-small"

    @pytest.mark.asyncio
    async def test_embed_with_options(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Embed passes options to generator."""
        servicer.generator.embed.return_value = [0.1, 0.2, 0.3]
        servicer.generator.get_dimension.return_value = 3

        request = embedding_pb2.EmbedRequest(
            text="test text",
            options={"dimensions": "256"},
        )

        await servicer.Embed(request, mock_async_grpc_context)

        servicer.generator.embed.assert_called_once_with(
            "test text",
            "text-embedding-3-small",
            dimensions="256",
        )

    @pytest.mark.asyncio
    async def test_embed_service_unavailable_error(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """ServiceUnavailableError returns UNAVAILABLE."""
        servicer.generator.embed.side_effect = ServiceUnavailableError("API rate limited")

        request = embedding_pb2.EmbedRequest(text="test text")

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Embed(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.UNAVAILABLE
        assert "API rate limited" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_embed_value_error(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """ValueError returns INVALID_ARGUMENT."""
        servicer.generator.embed.side_effect = ValueError("Invalid model name")

        request = embedding_pb2.EmbedRequest(text="test text")

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Embed(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "Invalid model name" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_embed_generic_exception(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Generic exception returns INTERNAL error."""
        servicer.generator.embed.side_effect = RuntimeError("Unexpected error")

        request = embedding_pb2.EmbedRequest(text="test text")

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.Embed(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INTERNAL
        assert "Internal error" in exc_info.value.details()


class TestEmbedBatchMethod:
    """Tests for EmbedBatch gRPC method."""

    @pytest.fixture
    def servicer(self, mock_embedding_generator):
        """Create an EmbeddingServicer instance for testing."""
        return EmbeddingServicer(
            generator=mock_embedding_generator,
            default_model="text-embedding-3-small",
        )

    @pytest.mark.asyncio
    async def test_embed_batch_empty_texts_aborts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Empty texts list returns INVALID_ARGUMENT error."""
        request = embedding_pb2.EmbedBatchRequest(texts=[])

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.EmbedBatch(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        assert "Texts list cannot be empty" in exc_info.value.details()

    @pytest.mark.asyncio
    async def test_embed_batch_single_text(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Single text in batch works correctly."""
        servicer.generator.embed_batch.return_value = [[0.1, 0.2, 0.3]]
        servicer.generator.get_dimension.return_value = 3

        request = embedding_pb2.EmbedBatchRequest(texts=["single text"])

        response = await servicer.EmbedBatch(request, mock_async_grpc_context)

        assert len(response.embeddings) == 1
        assert list(response.embeddings[0].embedding) == pytest.approx([0.1, 0.2, 0.3], rel=1e-5)

    @pytest.mark.asyncio
    async def test_embed_batch_multiple_texts(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Multiple texts return multiple embeddings."""
        servicer.generator.embed_batch.return_value = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ]
        servicer.generator.get_dimension.return_value = 3

        request = embedding_pb2.EmbedBatchRequest(texts=["text1", "text2", "text3"])

        response = await servicer.EmbedBatch(request, mock_async_grpc_context)

        assert len(response.embeddings) == 3
        assert list(response.embeddings[0].embedding) == pytest.approx([0.1, 0.2, 0.3], rel=1e-5)
        assert list(response.embeddings[1].embedding) == pytest.approx([0.4, 0.5, 0.6], rel=1e-5)
        assert list(response.embeddings[2].embedding) == pytest.approx([0.7, 0.8, 0.9], rel=1e-5)

    @pytest.mark.asyncio
    async def test_embed_batch_uses_request_model(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Uses model from request for all texts."""
        servicer.generator.embed_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
        servicer.generator.get_dimension.return_value = 2

        request = embedding_pb2.EmbedBatchRequest(
            texts=["text1", "text2"],
            model="custom-model",
        )

        response = await servicer.EmbedBatch(request, mock_async_grpc_context)

        servicer.generator.embed_batch.assert_called_once_with(
            ["text1", "text2"],
            "custom-model",
        )
        assert all(emb.model == "custom-model" for emb in response.embeddings)

    @pytest.mark.asyncio
    async def test_embed_batch_uses_default_model(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Uses default model when not specified."""
        servicer.generator.embed_batch.return_value = [[0.1, 0.2]]
        servicer.generator.get_dimension.return_value = 2

        request = embedding_pb2.EmbedBatchRequest(texts=["text"])

        await servicer.EmbedBatch(request, mock_async_grpc_context)

        servicer.generator.embed_batch.assert_called_once_with(
            ["text"],
            "text-embedding-3-small",
        )

    @pytest.mark.asyncio
    async def test_embed_batch_with_options(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """EmbedBatch passes options to generator."""
        servicer.generator.embed_batch.return_value = [[0.1, 0.2]]
        servicer.generator.get_dimension.return_value = 2

        request = embedding_pb2.EmbedBatchRequest(
            texts=["text"],
            options={"dimensions": "256"},
        )

        await servicer.EmbedBatch(request, mock_async_grpc_context)

        servicer.generator.embed_batch.assert_called_once_with(
            ["text"],
            "text-embedding-3-small",
            dimensions="256",
        )

    @pytest.mark.asyncio
    async def test_embed_batch_service_unavailable_error(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """ServiceUnavailableError returns UNAVAILABLE."""
        servicer.generator.embed_batch.side_effect = ServiceUnavailableError("Rate limited")

        request = embedding_pb2.EmbedBatchRequest(texts=["text"])

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.EmbedBatch(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_embed_batch_value_error(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """ValueError returns INVALID_ARGUMENT."""
        servicer.generator.embed_batch.side_effect = ValueError("Too many texts")

        request = embedding_pb2.EmbedBatchRequest(texts=["text"])

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.EmbedBatch(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    @pytest.mark.asyncio
    async def test_embed_batch_generic_exception(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Generic exception returns INTERNAL error."""
        servicer.generator.embed_batch.side_effect = RuntimeError("Unexpected")

        request = embedding_pb2.EmbedBatchRequest(texts=["text"])

        with pytest.raises(GrpcAbortException) as exc_info:
            await servicer.EmbedBatch(request, mock_async_grpc_context)

        assert exc_info.value.code() == grpc.StatusCode.INTERNAL


class TestHealthCheckMethod:
    """Tests for HealthCheck gRPC method."""

    @pytest.fixture
    def servicer(self, mock_embedding_generator):
        """Create an EmbeddingServicer instance for testing."""
        return EmbeddingServicer(
            generator=mock_embedding_generator,
            default_model="text-embedding-3-small",
        )

    @pytest.mark.asyncio
    async def test_health_check_healthy_generator(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Healthy generator returns HEALTHY status."""
        servicer.generator.get_dimension.return_value = 1536

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.HEALTHY
        assert response.dependencies["generator"] == "HEALTHY"
        assert "healthy" in response.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_generator(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Generator exception returns UNHEALTHY status."""
        servicer.generator.get_dimension.side_effect = RuntimeError("API error")

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["generator"] == "UNHEALTHY"
        assert "not available" in response.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_includes_model_info(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Health check verifies the default model."""
        servicer.generator.get_dimension.return_value = 1536

        request = common_pb2.HealthCheckRequest()

        await servicer.HealthCheck(request, mock_async_grpc_context)

        # Verify get_dimension was called with default model
        servicer.generator.get_dimension.assert_called_with("text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_health_check_unexpected_exception(
        self,
        servicer,
        mock_async_grpc_context,
    ):
        """Unexpected exception during health check returns UNHEALTHY."""
        # Make generator None to force an unexpected exception path
        servicer.generator = None

        request = common_pb2.HealthCheckRequest()

        response = await servicer.HealthCheck(request, mock_async_grpc_context)

        # When generator is None, get_dimension raises AttributeError
        # which is caught and treated as backend unhealthy
        assert response.status == common_pb2.HealthCheckResponse.UNHEALTHY
        assert response.dependencies["generator"] == "UNHEALTHY"
