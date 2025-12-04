"""Unit tests for src/embedding_service/generators/factory.py.

Tests cover:
- EmbeddingGeneratorFactory.create_generator for hash_based type
- EmbeddingGeneratorFactory.create_generator for openai type
- EmbeddingGeneratorFactory.create_generator for unknown type
- EmbeddingGeneratorFactory.list_generators
"""

from unittest.mock import patch

import pytest

from src.embedding_service.generators.factory import EmbeddingGeneratorFactory
from src.embedding_service.generators.hash_based_generator import HashBasedEmbeddingGenerator


class TestEmbeddingGeneratorFactoryCreateGenerator:
    """Tests for EmbeddingGeneratorFactory.create_generator method."""

    def test_create_hash_based_generator(self):
        """Tests that create_generator creates HashBasedEmbeddingGenerator."""
        generator = EmbeddingGeneratorFactory.create_generator("hash_based")

        assert isinstance(generator, HashBasedEmbeddingGenerator)

    def test_create_hash_based_generator_with_custom_dimension(self):
        """Tests that create_generator passes dimension to HashBasedEmbeddingGenerator."""
        generator = EmbeddingGeneratorFactory.create_generator("hash_based", default_dimension=768)

        assert isinstance(generator, HashBasedEmbeddingGenerator)
        assert generator.default_dimension == 768

    def test_create_hash_based_generator_default_dimension(self):
        """Tests that create_generator uses default dimension for HashBasedEmbeddingGenerator."""
        generator = EmbeddingGeneratorFactory.create_generator("hash_based")

        assert generator.default_dimension == 1536

    @patch("src.embedding_service.generators.factory.OpenAIEmbeddingGenerator")
    def test_create_openai_generator(self, mock_openai_generator):
        """Tests that create_generator creates OpenAIEmbeddingGenerator."""
        mock_instance = mock_openai_generator.return_value

        generator = EmbeddingGeneratorFactory.create_generator("openai", api_key="test-key")

        mock_openai_generator.assert_called_once_with(api_key="test-key", max_retries=3, timeout=30)
        assert generator == mock_instance

    @patch("src.embedding_service.generators.factory.OpenAIEmbeddingGenerator")
    def test_create_openai_generator_with_custom_retries(self, mock_openai_generator):
        """Tests that create_generator passes max_retries to OpenAIEmbeddingGenerator."""
        EmbeddingGeneratorFactory.create_generator("openai", api_key="test-key", max_retries=5)

        mock_openai_generator.assert_called_once_with(api_key="test-key", max_retries=5, timeout=30)

    @patch("src.embedding_service.generators.factory.OpenAIEmbeddingGenerator")
    def test_create_openai_generator_with_custom_timeout(self, mock_openai_generator):
        """Tests that create_generator passes timeout to OpenAIEmbeddingGenerator."""
        EmbeddingGeneratorFactory.create_generator("openai", api_key="test-key", timeout=60)

        mock_openai_generator.assert_called_once_with(api_key="test-key", max_retries=3, timeout=60)

    def test_create_openai_generator_without_api_key_raises(self):
        """Tests that create_generator raises ValueError when api_key missing for OpenAI."""
        with pytest.raises(ValueError) as exc_info:
            EmbeddingGeneratorFactory.create_generator("openai")

        assert "api_key" in str(exc_info.value)

    def test_create_unknown_generator_raises(self):
        """Tests that create_generator raises ValueError for unknown type."""
        with pytest.raises(ValueError) as exc_info:
            EmbeddingGeneratorFactory.create_generator("unknown_type")  # type: ignore[arg-type]

        assert "unknown_type" in str(exc_info.value).lower()
        assert "hash_based" in str(exc_info.value).lower()
        assert "openai" in str(exc_info.value).lower()


class TestEmbeddingGeneratorFactoryListGenerators:
    """Tests for EmbeddingGeneratorFactory.list_generators method."""

    def test_list_generators_returns_supported_types(self):
        """Tests that list_generators returns all supported types."""
        generators = EmbeddingGeneratorFactory.list_generators()

        assert "hash_based" in generators
        assert "openai" in generators

    def test_list_generators_returns_list(self):
        """Tests that list_generators returns a list."""
        generators = EmbeddingGeneratorFactory.list_generators()

        assert isinstance(generators, list)

    def test_list_generators_returns_correct_count(self):
        """Tests that list_generators returns expected number of types."""
        generators = EmbeddingGeneratorFactory.list_generators()

        assert len(generators) == 2
