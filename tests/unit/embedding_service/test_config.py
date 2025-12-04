"""Unit tests for src/embedding_service/config.py.

Tests cover:
- EmbeddingServiceConfig initialization with required embedding_generator
- EmbeddingServiceConfig with custom values
- openai_api_key validation
- get_embedding_config for hash_based and openai generators
- Validation that embedding_generator is required (no fallback)
"""

import pytest
from pydantic import ValidationError

from src.embedding_service.config import EmbeddingServiceConfig
from src.llm.config import EmbeddingProvider


class TestEmbeddingServiceConfigRequired:
    """Tests that embedding_generator is required (no fallback)."""

    def test_embedding_generator_required(self):
        """Tests that embedding_generator must be explicitly set - no default fallback."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingServiceConfig()

        assert "embedding_generator" in str(exc_info.value)
        assert "Field required" in str(exc_info.value)


class TestEmbeddingServiceConfigDefaults:
    """Tests for EmbeddingServiceConfig default values (with required fields set)."""

    def test_defaults_with_hash_based(self):
        """Tests that other defaults are set correctly when embedding_generator is provided."""
        config = EmbeddingServiceConfig(embedding_generator="hash_based")

        assert config.service_name == "embedding-service"
        assert config.port == 50051
        assert config.embedding_generator == "hash_based"
        assert config.default_model == "hash-small"
        assert config.max_batch_size == 100
        assert config.enable_reflection is True
        assert config.max_workers == 10

    def test_hash_based_defaults(self):
        """Tests hash-based generator defaults."""
        config = EmbeddingServiceConfig(embedding_generator="hash_based")

        assert config.hash_based_dimension == 1536

    def test_openai_defaults(self):
        """Tests OpenAI-related defaults.

        Note: Some values may be overridden by environment variables.
        """
        config = EmbeddingServiceConfig(
            embedding_generator="openai",
            openai_api_key="sk-test",
        )

        # These may be set from env, just verify they're the right type
        assert config.openai_api_base is None or isinstance(config.openai_api_base, str)
        assert config.openai_embedding_model  # Just verify it's set
        assert config.openai_max_retries >= 1
        assert config.openai_timeout >= 1


class TestEmbeddingServiceConfigCustomValues:
    """Tests for EmbeddingServiceConfig with custom values."""

    def test_custom_port(self):
        """Tests custom port setting."""
        config = EmbeddingServiceConfig(embedding_generator="hash_based", port=50099)

        assert config.port == 50099

    def test_custom_service_name(self):
        """Tests custom service name."""
        config = EmbeddingServiceConfig(embedding_generator="hash_based", service_name="custom-embedding")

        assert config.service_name == "custom-embedding"

    def test_custom_max_batch_size(self):
        """Tests custom batch size."""
        config = EmbeddingServiceConfig(embedding_generator="hash_based", max_batch_size=50)

        assert config.max_batch_size == 50

    def test_custom_hash_dimension(self):
        """Tests custom hash-based dimension."""
        config = EmbeddingServiceConfig(embedding_generator="hash_based", hash_based_dimension=768)

        assert config.hash_based_dimension == 768

    def test_openai_generator_with_api_key(self):
        """Tests OpenAI generator configuration with API key."""
        config = EmbeddingServiceConfig(
            embedding_generator="openai",
            openai_api_key="sk-test123",
        )

        assert config.embedding_generator == "openai"
        assert config.openai_api_key == "sk-test123"


class TestEmbeddingServiceConfigValidation:
    """Tests for EmbeddingServiceConfig validation."""

    def test_openai_generator_requires_api_key(self):
        """Tests that OpenAI generator requires API key.

        Note: This test explicitly sets openai_api_key to None to ensure
        the validation error is raised, as environment variables may
        provide a default value.
        """
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingServiceConfig(embedding_generator="openai", openai_api_key=None)

        assert "OpenAI API key required" in str(exc_info.value)

    def test_hash_based_generator_no_api_key_required(self):
        """Tests that hash_based generator doesn't require API key.

        Note: API key may still be set from environment variables,
        but it's not required for hash_based generator.
        """
        # Should not raise even without API key
        config = EmbeddingServiceConfig(embedding_generator="hash_based")

        # Just verify it was created successfully
        assert config.embedding_generator == "hash_based"

    def test_any_nonempty_api_key_accepted(self):
        """Tests that any non-empty API key is accepted for local LLM servers."""
        config = EmbeddingServiceConfig(
            embedding_generator="openai",
            openai_api_key="any-key-works",
            openai_api_base="http://localhost:1234/v1",
        )

        assert config.openai_api_key == "any-key-works"


class TestEmbeddingServiceConfigGetEmbeddingConfig:
    """Tests for EmbeddingServiceConfig.get_embedding_config method."""

    def test_get_embedding_config_hash_based(self):
        """Tests get_embedding_config for hash_based generator."""
        config = EmbeddingServiceConfig(
            embedding_generator="hash_based",
            hash_based_dimension=768,
        )

        embedding_config = config.get_embedding_config()

        assert embedding_config.provider == EmbeddingProvider.HASH_BASED
        assert embedding_config.dimension == 768

    def test_get_embedding_config_openai(self):
        """Tests get_embedding_config for OpenAI generator."""
        config = EmbeddingServiceConfig(
            embedding_generator="openai",
            openai_api_key="sk-test123",
            openai_api_base=None,  # Explicitly set to None for OpenAI
            openai_embedding_model="text-embedding-3-large",
            openai_max_retries=5,
            openai_timeout=60,
        )

        embedding_config = config.get_embedding_config()

        assert embedding_config.provider == EmbeddingProvider.OPENAI
        assert embedding_config.api_key == "sk-test123"
        assert embedding_config.model == "text-embedding-3-large"
        assert embedding_config.max_retries == 5
        assert embedding_config.timeout == 60

    def test_get_embedding_config_local_provider(self):
        """Tests get_embedding_config with local provider (custom base URL)."""
        config = EmbeddingServiceConfig(
            embedding_generator="openai",
            openai_api_key="lm-studio",
            openai_api_base="http://localhost:1234/v1",
            openai_embedding_model="bge-large-en-v1.5",
        )

        embedding_config = config.get_embedding_config()

        assert embedding_config.provider == EmbeddingProvider.LOCAL
        assert embedding_config.base_url == "http://localhost:1234/v1"
        assert embedding_config.model == "bge-large-en-v1.5"

    def test_get_embedding_config_openai_without_base_url(self):
        """Tests that OpenAI provider is used when no base URL is set."""
        config = EmbeddingServiceConfig(
            embedding_generator="openai",
            openai_api_key="sk-test",
            openai_api_base=None,
        )

        embedding_config = config.get_embedding_config()

        assert embedding_config.provider == EmbeddingProvider.OPENAI
