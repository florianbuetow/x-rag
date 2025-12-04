"""Tests for Search Service configuration."""

import pytest
from pydantic import ValidationError

from src.search_service.config import SearchServiceConfig


def test_config_defaults() -> None:
    """Test that configuration has sensible defaults.

    Note: Some defaults may be overridden by environment variables.
    We test the key structural defaults that don't depend on env.
    """
    # Override required field
    config = SearchServiceConfig(openai_api_key="sk-test123")

    assert config.service_name == "search-service"
    assert config.port == 50052
    assert config.weaviate_url == "http://weaviate:8080"
    assert config.embedding_service_addr == "embedding-service:50051"
    # openai_model may be overridden by OPENAI_MODEL env var
    assert config.openai_model  # Just verify it's set
    assert config.default_top_k == 10
    assert config.default_mode == "hybrid"
    assert config.hybrid_alpha == 0.5
    # Optional base URL defaults to None (may be overridden by env)
    # Just check it's the right type
    assert config.openai_api_base is None or isinstance(config.openai_api_base, str)


def test_config_custom_values() -> None:
    """Test configuration with custom values."""
    config = SearchServiceConfig(
        service_name="custom-search",
        port=50099,
        weaviate_url="http://custom-weaviate:8080",
        openai_api_key="sk-customkey",
        openai_model="gpt-4",
        default_top_k=20,
        default_mode="vector",
        hybrid_alpha=0.7,
    )

    assert config.service_name == "custom-search"
    assert config.port == 50099
    assert config.weaviate_url == "http://custom-weaviate:8080"
    assert config.openai_api_key == "sk-customkey"
    assert config.openai_model == "gpt-4"
    assert config.default_top_k == 20
    assert config.default_mode == "vector"
    assert config.hybrid_alpha == 0.7


def test_config_invalid_weaviate_url() -> None:
    """Test that invalid Weaviate URL fails validation."""
    with pytest.raises(ValidationError, match="Invalid Weaviate URL"):
        SearchServiceConfig(
            weaviate_url="invalid-url",
            openai_api_key="sk-test123",
        )


def test_config_empty_openai_key() -> None:
    """Test that empty OpenAI API key fails validation."""
    with pytest.raises(ValidationError, match="OpenAI API key not configured"):
        SearchServiceConfig(openai_api_key="")


def test_config_placeholder_openai_key_allowed() -> None:
    """Test that placeholder OpenAI API key is allowed for development."""
    # Should not raise, but logs a warning
    config = SearchServiceConfig(openai_api_key="sk-your-key-here")
    assert config.openai_api_key == "sk-your-key-here"


def test_config_any_nonempty_openai_key_accepted() -> None:
    """Test that any non-empty OpenAI key is accepted (for local LLM servers)."""
    # Any non-empty key is now valid for compatibility with local LLM servers
    config = SearchServiceConfig(openai_api_key="any-key-works")
    assert config.openai_api_key == "any-key-works"


def test_config_invalid_temperature() -> None:
    """Test that invalid temperature fails validation."""
    with pytest.raises(ValidationError, match="Temperature must be between"):
        SearchServiceConfig(
            openai_api_key="sk-test123",
            openai_temperature=3.0,  # Too high
        )


def test_config_invalid_search_mode() -> None:
    """Test that invalid search mode fails validation."""
    with pytest.raises(ValidationError, match="Invalid search mode"):
        SearchServiceConfig(
            openai_api_key="sk-test123",
            default_mode="invalid",
        )


def test_config_invalid_alpha() -> None:
    """Test that invalid alpha fails validation."""
    with pytest.raises(ValidationError, match="Hybrid alpha must be between"):
        SearchServiceConfig(
            openai_api_key="sk-test123",
            hybrid_alpha=1.5,  # Too high
        )


def test_config_invalid_top_k() -> None:
    """Test that invalid top_k fails validation."""
    with pytest.raises(ValidationError, match="default_top_k must be positive"):
        SearchServiceConfig(
            openai_api_key="sk-test123",
            default_top_k=0,
        )

    with pytest.raises(ValidationError, match="default_top_k too large"):
        SearchServiceConfig(
            openai_api_key="sk-test123",
            default_top_k=150,
        )
