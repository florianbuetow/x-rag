"""Unit tests for src/llm/config.py.

Tests cover:
- LLMProvider enum
- EmbeddingProvider enum
- LLMConfig initialization and validation
- LLMConfig factory methods (for_openai, for_local)
- EmbeddingConfig initialization and validation
- EmbeddingConfig factory methods (for_openai, for_local, for_hash_based)
"""

import pytest
from pydantic import ValidationError

from src.llm.config import EmbeddingConfig, EmbeddingProvider, LLMConfig, LLMProvider


class TestLLMProvider:
    """Tests for LLMProvider enum."""

    def test_openai_provider_in_config(self):
        """Tests OPENAI provider can be used in config."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            model="gpt-4",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )
        assert config.provider == LLMProvider.OPENAI

    def test_local_provider_in_config(self):
        """Tests LOCAL provider can be used in config."""
        config = LLMConfig(
            provider=LLMProvider.LOCAL,
            api_key="test-key",
            model="local-model",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )
        assert config.provider == LLMProvider.LOCAL


class TestEmbeddingProvider:
    """Tests for EmbeddingProvider enum."""

    def test_openai_provider_in_config(self):
        """Tests OPENAI provider can be used in config."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            max_retries=3,
            timeout=60,
            dimension=1536,
        )
        assert config.provider == EmbeddingProvider.OPENAI

    def test_local_provider_in_config(self):
        """Tests LOCAL provider can be used in config."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.LOCAL,
            model="local-model",
            max_retries=3,
            timeout=60,
            dimension=1024,
        )
        assert config.provider == EmbeddingProvider.LOCAL

    def test_hash_based_provider_in_config(self):
        """Tests HASH_BASED provider can be used in config."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.HASH_BASED,
            model="hash-based",
            max_retries=0,
            timeout=10,
            dimension=384,
        )
        assert config.provider == EmbeddingProvider.HASH_BASED


class TestLLMConfigDefaults:
    """Tests for LLMConfig requiring all fields."""

    def test_defaults(self):
        """Tests that all fields are required - no defaults."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            model="gpt-4o-mini",
            max_tokens=500,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )

        assert config.provider == LLMProvider.OPENAI
        assert config.api_key == "test-key"
        assert config.base_url is None
        assert config.model == "gpt-4o-mini"
        assert config.max_tokens == 500
        assert config.temperature == 0.7
        assert config.max_retries == 3
        assert config.timeout == 60


class TestLLMConfigValidation:
    """Tests for LLMConfig validation."""

    def test_empty_api_key_raises(self):
        """Tests that empty API key raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(
                provider=LLMProvider.OPENAI,
                api_key="",
                model="gpt-4",
                max_tokens=1000,
                temperature=0.7,
                max_retries=3,
                timeout=60,
            )

        assert "API key cannot be empty" in str(exc_info.value)

    def test_invalid_temperature_too_high(self):
        """Tests that temperature > 2.0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(
                provider=LLMProvider.OPENAI,
                api_key="test",
                model="gpt-4",
                max_tokens=1000,
                temperature=2.5,
                max_retries=3,
                timeout=60,
            )

        assert "Temperature must be between" in str(exc_info.value)

    def test_invalid_temperature_negative(self):
        """Tests that negative temperature raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(
                provider=LLMProvider.OPENAI,
                api_key="test",
                model="gpt-4",
                max_tokens=1000,
                temperature=-0.1,
                max_retries=3,
                timeout=60,
            )

        assert "Temperature must be between" in str(exc_info.value)

    def test_valid_temperature_boundary(self):
        """Tests that temperature at boundaries is valid."""
        config_low = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test",
            model="gpt-4",
            max_tokens=1000,
            temperature=0.0,
            max_retries=3,
            timeout=60,
        )
        config_high = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test",
            model="gpt-4",
            max_tokens=1000,
            temperature=2.0,
            max_retries=3,
            timeout=60,
        )

        assert config_low.temperature == 0.0
        assert config_high.temperature == 2.0

    def test_invalid_base_url(self):
        """Tests that invalid base URL raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(
                provider=LLMProvider.OPENAI,
                api_key="test",
                model="gpt-4",
                max_tokens=1000,
                temperature=0.7,
                max_retries=3,
                timeout=60,
                base_url="invalid-url",
            )

        assert "Invalid base URL" in str(exc_info.value)

    def test_base_url_strips_trailing_slash(self):
        """Tests that base URL trailing slash is stripped."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test",
            model="gpt-4",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
            base_url="http://localhost:1234/",
        )

        assert config.base_url == "http://localhost:1234"

    def test_empty_base_url_becomes_none(self):
        """Tests that empty string base URL becomes None."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test",
            model="gpt-4",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
            base_url="",
        )

        assert config.base_url is None


class TestLLMConfigFactoryMethods:
    """Tests for LLMConfig factory methods."""

    def test_for_openai(self):
        """Tests for_openai factory method."""
        config = LLMConfig.for_openai(
            api_key="sk-test123",
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )

        assert config.provider == LLMProvider.OPENAI
        assert config.api_key == "sk-test123"
        assert config.base_url is None
        assert config.model == "gpt-4o-mini"

    def test_for_openai_with_custom_model(self):
        """Tests for_openai with custom model."""
        config = LLMConfig.for_openai(
            api_key="sk-test",
            model="gpt-4",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )

        assert config.model == "gpt-4"

    def test_for_openai_with_kwargs(self):
        """Tests for_openai with additional kwargs."""
        config = LLMConfig.for_openai(
            api_key="sk-test",
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.5,
            max_retries=3,
            timeout=60,
        )

        assert config.max_tokens == 1000
        assert config.temperature == 0.5

    def test_for_local(self):
        """Tests for_local factory method."""
        config = LLMConfig.for_local(
            base_url="http://localhost:1234/v1",
            model="qwen2.5-7b",
            api_key="local",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )

        assert config.provider == LLMProvider.LOCAL
        assert config.base_url == "http://localhost:1234/v1"
        assert config.model == "qwen2.5-7b"
        assert config.api_key == "local"

    def test_for_local_with_custom_api_key(self):
        """Tests for_local with custom API key."""
        config = LLMConfig.for_local(
            base_url="http://localhost:1234/v1",
            model="model",
            api_key="custom-key",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )

        assert config.api_key == "custom-key"


class TestLLMConfigProperties:
    """Tests for LLMConfig properties."""

    def test_is_local_with_local_provider(self):
        """Tests is_local returns True for LOCAL provider."""
        config = LLMConfig.for_local(
            base_url="http://localhost:1234/v1",
            model="model",
            api_key="local",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )

        assert config.is_local is True

    def test_is_local_with_base_url(self):
        """Tests is_local returns True when base_url is set."""
        config = LLMConfig(
            api_key="test",
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
            base_url="http://localhost:1234/v1",
        )

        assert config.is_local is True

    def test_is_local_with_openai_no_base_url(self):
        """Tests is_local returns False for OpenAI without base_url."""
        config = LLMConfig.for_openai(
            api_key="sk-test",
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.7,
            max_retries=3,
            timeout=60,
        )

        assert config.is_local is False


class TestEmbeddingConfigDefaults:
    """Tests for EmbeddingConfig requiring all fields."""

    def test_defaults(self):
        """Tests that all fields are required - no defaults."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            max_retries=3,
            timeout=30,
            dimension=768,
        )

        assert config.provider == EmbeddingProvider.OPENAI
        assert config.model == "text-embedding-3-small"
        assert config.api_key is None
        assert config.base_url is None
        assert config.max_retries == 3
        assert config.timeout == 30
        assert config.dimension == 768


class TestEmbeddingConfigValidation:
    """Tests for EmbeddingConfig validation."""

    def test_invalid_base_url(self):
        """Tests that invalid base URL raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(
                provider=EmbeddingProvider.OPENAI,
                model="text-embedding-3-small",
                max_retries=3,
                timeout=60,
                dimension=1536,
                base_url="invalid-url",
            )

        assert "Invalid base URL" in str(exc_info.value)

    def test_base_url_strips_trailing_slash(self):
        """Tests that base URL trailing slash is stripped."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            max_retries=3,
            timeout=60,
            dimension=1536,
            base_url="http://localhost:1234/",
        )

        assert config.base_url == "http://localhost:1234"

    def test_empty_base_url_becomes_none(self):
        """Tests that empty string base URL becomes None."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            max_retries=3,
            timeout=60,
            dimension=1536,
            base_url="",
        )

        assert config.base_url is None


class TestEmbeddingConfigFactoryMethods:
    """Tests for EmbeddingConfig factory methods."""

    def test_for_openai(self):
        """Tests for_openai factory method."""
        config = EmbeddingConfig.for_openai(
            api_key="sk-test123",
            model="text-embedding-3-small",
            max_retries=3,
            timeout=60,
            dimension=1536,
        )

        assert config.provider == EmbeddingProvider.OPENAI
        assert config.api_key == "sk-test123"
        assert config.base_url is None
        assert config.model == "text-embedding-3-small"

    def test_for_openai_with_custom_model(self):
        """Tests for_openai with custom model."""
        config = EmbeddingConfig.for_openai(
            api_key="sk-test",
            model="text-embedding-3-large",
            max_retries=3,
            timeout=60,
            dimension=3072,
        )

        assert config.model == "text-embedding-3-large"

    def test_for_local(self):
        """Tests for_local factory method."""
        config = EmbeddingConfig.for_local(
            base_url="http://localhost:1234/v1",
            model="bge-large-en-v1.5",
            api_key="local",
            max_retries=3,
            timeout=60,
            dimension=1024,
        )

        assert config.provider == EmbeddingProvider.LOCAL
        assert config.base_url == "http://localhost:1234/v1"
        assert config.model == "bge-large-en-v1.5"
        assert config.api_key == "local"

    def test_for_hash_based(self):
        """Tests for_hash_based factory method."""
        config = EmbeddingConfig.for_hash_based(
            dimension=768,
            max_retries=0,
            timeout=10,
        )

        assert config.provider == EmbeddingProvider.HASH_BASED
        assert config.model == "hash-based"
        assert config.dimension == 768

    def test_for_hash_based_with_custom_dimension(self):
        """Tests for_hash_based with custom dimension."""
        config = EmbeddingConfig.for_hash_based(
            dimension=1536,
            max_retries=0,
            timeout=10,
        )

        assert config.dimension == 1536


class TestEmbeddingConfigProperties:
    """Tests for EmbeddingConfig properties."""

    def test_is_local_with_local_provider(self):
        """Tests is_local returns True for LOCAL provider."""
        config = EmbeddingConfig.for_local(
            base_url="http://localhost:1234/v1",
            model="model",
            api_key="local",
            max_retries=3,
            timeout=60,
            dimension=1024,
        )

        assert config.is_local is True

    def test_is_local_with_hash_based(self):
        """Tests is_local returns True for HASH_BASED provider."""
        config = EmbeddingConfig.for_hash_based(
            dimension=768,
            max_retries=0,
            timeout=10,
        )

        assert config.is_local is True

    def test_is_local_with_openai(self):
        """Tests is_local returns False for OpenAI provider."""
        config = EmbeddingConfig.for_openai(
            api_key="sk-test",
            model="text-embedding-3-small",
            max_retries=3,
            timeout=60,
            dimension=1536,
        )

        assert config.is_local is False

    def test_requires_api_key_openai(self):
        """Tests requires_api_key returns True for OpenAI."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            max_retries=3,
            timeout=60,
            dimension=1536,
        )

        assert config.requires_api_key is True

    def test_requires_api_key_local(self):
        """Tests requires_api_key returns True for LOCAL."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.LOCAL,
            model="local-model",
            max_retries=3,
            timeout=60,
            dimension=1024,
        )

        assert config.requires_api_key is True

    def test_requires_api_key_hash_based(self):
        """Tests requires_api_key returns False for HASH_BASED."""
        config = EmbeddingConfig.for_hash_based(
            dimension=768,
            max_retries=0,
            timeout=10,
        )

        assert config.requires_api_key is False
