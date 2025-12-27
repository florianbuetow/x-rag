"""Unit tests for src/embedding_service/generators/openai_generator.py.

Tests cover:
- OpenAIEmbeddingGenerator initialization
- embed method (success, error handling)
- embed_batch method (success, empty input, error handling)
- get_dimension method
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError, RateLimitError

from src.core.errors import ServiceUnavailableError
from src.embedding_service.generators.openai_generator import OpenAIEmbeddingGenerator


class TestOpenAIEmbeddingGeneratorInit:
    """Tests for OpenAIEmbeddingGenerator initialization."""

    @patch("src.embedding_service.generators.openai_generator.AsyncOpenAI")
    def test_init_creates_client(self, mock_async_openai):
        """Tests that __init__ creates AsyncOpenAI client."""
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        generator = OpenAIEmbeddingGenerator(
            api_key="test-key",
            max_retries=3,
            timeout=30,
            base_url=None,
        )

        # Verify AsyncOpenAI was instantiated with correct parameters
        mock_async_openai.assert_called_once_with(
            api_key="test-key",
            max_retries=3,
            timeout=30,
            base_url=None,
        )
        # Verify the client was properly assigned
        assert generator.client is mock_client

    @patch("src.embedding_service.generators.openai_generator.AsyncOpenAI")
    def test_init_with_custom_retries(self, mock_async_openai):
        """Tests that __init__ respects max_retries parameter."""
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        generator = OpenAIEmbeddingGenerator(
            api_key="test-key",
            max_retries=5,
            timeout=30,
            base_url=None,
        )

        # Verify AsyncOpenAI was instantiated with correct max_retries
        mock_async_openai.assert_called_once_with(
            api_key="test-key",
            max_retries=5,
            timeout=30,
            base_url=None,
        )
        # Verify the client was properly assigned
        assert generator.client is mock_client

    @patch("src.embedding_service.generators.openai_generator.AsyncOpenAI")
    def test_init_with_custom_timeout(self, mock_async_openai):
        """Tests that __init__ respects timeout parameter."""
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        generator = OpenAIEmbeddingGenerator(
            api_key="test-key",
            max_retries=3,
            timeout=60,
            base_url=None,
        )

        # Verify AsyncOpenAI was instantiated with correct timeout
        mock_async_openai.assert_called_once_with(
            api_key="test-key",
            max_retries=3,
            timeout=60,
            base_url=None,
        )
        # Verify the client was properly assigned
        assert generator.client is mock_client

    @patch("src.embedding_service.generators.openai_generator.AsyncOpenAI")
    def test_init_stores_max_retries(self, mock_async_openai):
        """Tests that __init__ stores max_retries as attribute."""
        generator = OpenAIEmbeddingGenerator(
            api_key="test-key",
            max_retries=7,
            timeout=30,
            base_url=None,
        )

        assert generator.max_retries == 7


class TestOpenAIEmbeddingGeneratorEmbed:
    """Tests for OpenAIEmbeddingGenerator.embed method."""

    @pytest.fixture
    def generator(self):
        """Create generator with mocked client."""
        with patch("src.embedding_service.generators.openai_generator.AsyncOpenAI") as mock_async_openai:
            mock_client = MagicMock()
            mock_async_openai.return_value = mock_client
            gen = OpenAIEmbeddingGenerator(
                api_key="test-key",
                max_retries=3,
                timeout=30,
                base_url=None,
            )
            gen.client = mock_client
            yield gen

    @pytest.mark.asyncio
    async def test_embed_returns_embedding(self, generator):
        """Tests that embed returns embedding vector."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        generator.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await generator.embed("test text", model="text-embedding-3-small")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_calls_api_with_correct_params(self, generator):
        """Tests that embed calls API with correct parameters."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1])]
        generator.client.embeddings.create = AsyncMock(return_value=mock_response)

        await generator.embed("test text", model="text-embedding-3-small")

        generator.client.embeddings.create.assert_called_once()
        call_kwargs = generator.client.embeddings.create.call_args[1]
        assert call_kwargs["input"] == "test text"
        assert call_kwargs["model"] == "text-embedding-3-small"

    @pytest.mark.asyncio
    async def test_embed_raises_service_unavailable_on_rate_limit(self, generator):
        """Tests that embed raises ServiceUnavailableError on rate limit."""
        generator.client.embeddings.create = AsyncMock(
            side_effect=RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )
        )

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await generator.embed("test", model="text-embedding-3-small")

        assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_raises_service_unavailable_on_api_error(self, generator):
        """Tests that embed raises ServiceUnavailableError on API error."""
        generator.client.embeddings.create = AsyncMock(
            side_effect=APIError(
                message="API Error",
                request=MagicMock(),
                body=None,
            )
        )

        with pytest.raises(ServiceUnavailableError):
            await generator.embed("test", model="text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_embed_raises_service_unavailable_on_unexpected_error(self, generator):
        """Tests that embed raises ServiceUnavailableError on unexpected error."""
        generator.client.embeddings.create = AsyncMock(side_effect=Exception("Unexpected error"))

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await generator.embed("test", model="text-embedding-3-small")

        assert "failed" in str(exc_info.value).lower()


class TestOpenAIEmbeddingGeneratorEmbedBatch:
    """Tests for OpenAIEmbeddingGenerator.embed_batch method."""

    @pytest.fixture
    def generator(self):
        """Create generator with mocked client."""
        with patch("src.embedding_service.generators.openai_generator.AsyncOpenAI") as mock_async_openai:
            mock_client = MagicMock()
            mock_async_openai.return_value = mock_client
            gen = OpenAIEmbeddingGenerator(
                api_key="test-key",
                max_retries=3,
                timeout=30,
                base_url=None,
            )
            gen.client = mock_client
            yield gen

    @pytest.mark.asyncio
    async def test_embed_batch_returns_embeddings(self, generator):
        """Tests that embed_batch returns list of embeddings."""
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]
        generator.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await generator.embed_batch(["text1", "text2"], model="text-embedding-3-small")

        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_embed_batch_returns_empty_for_empty_input(self, generator):
        """Tests that embed_batch returns empty list for empty input."""
        result = await generator.embed_batch([], model="text-embedding-3-small")

        assert result == []
        # Should not call API for empty input
        generator.client.embeddings.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_batch_calls_api_with_list(self, generator):
        """Tests that embed_batch passes list of texts to API."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1])]
        generator.client.embeddings.create = AsyncMock(return_value=mock_response)

        await generator.embed_batch(["a", "b", "c"], model="text-embedding-3-small")

        call_kwargs = generator.client.embeddings.create.call_args[1]
        assert call_kwargs["input"] == ["a", "b", "c"]
        assert call_kwargs["model"] == "text-embedding-3-small"

    @pytest.mark.asyncio
    async def test_embed_batch_raises_service_unavailable_on_rate_limit(self, generator):
        """Tests that embed_batch raises ServiceUnavailableError on rate limit."""
        generator.client.embeddings.create = AsyncMock(
            side_effect=RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )
        )

        with pytest.raises(ServiceUnavailableError):
            await generator.embed_batch(["test"], model="text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_embed_batch_raises_service_unavailable_on_api_error(self, generator):
        """Tests that embed_batch raises ServiceUnavailableError on API error."""
        generator.client.embeddings.create = AsyncMock(
            side_effect=APIError(
                message="API Error",
                request=MagicMock(),
                body=None,
            )
        )

        with pytest.raises(ServiceUnavailableError):
            await generator.embed_batch(["test"], model="text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_embed_batch_raises_service_unavailable_on_unexpected_error(self, generator):
        """Tests that embed_batch raises ServiceUnavailableError on unexpected error."""
        generator.client.embeddings.create = AsyncMock(side_effect=Exception("Unexpected"))

        with pytest.raises(ServiceUnavailableError):
            await generator.embed_batch(["test"], model="text-embedding-3-small")


class TestOpenAIEmbeddingGeneratorGetDimension:
    """Tests for OpenAIEmbeddingGenerator.get_dimension method."""

    @pytest.fixture
    def generator(self):
        """Create generator with mocked client."""
        with patch("src.embedding_service.generators.openai_generator.AsyncOpenAI"):
            yield OpenAIEmbeddingGenerator(
                api_key="test-key",
                max_retries=3,
                timeout=30,
                base_url=None,
            )

    def test_get_dimension_text_embedding_3_small(self, generator):
        """Tests dimension for text-embedding-3-small."""
        assert generator.get_dimension("text-embedding-3-small") == 1536

    def test_get_dimension_text_embedding_3_large(self, generator):
        """Tests dimension for text-embedding-3-large."""
        assert generator.get_dimension("text-embedding-3-large") == 3072

    def test_get_dimension_text_embedding_ada_002(self, generator):
        """Tests dimension for text-embedding-ada-002."""
        assert generator.get_dimension("text-embedding-ada-002") == 1536

    def test_get_dimension_unknown_model_raises(self, generator):
        """Tests that get_dimension raises ValueError for unknown model."""
        with pytest.raises(ValueError) as exc_info:
            generator.get_dimension("unknown-model")

        assert "unknown-model" in str(exc_info.value).lower()
        assert "text-embedding-3-small" in str(exc_info.value)

    def test_model_dimensions_constant(self, generator):
        """Tests that MODEL_DIMENSIONS contains expected models."""
        expected_models = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]

        for model in expected_models:
            assert model in generator.MODEL_DIMENSIONS
