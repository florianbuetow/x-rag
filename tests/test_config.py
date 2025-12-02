"""Tests for configuration validation."""

import pytest
from pydantic import ValidationError

from src.common.config import (
    ConfigurationError,
    OpenAIConfig,
    RedisConfig,
    ServiceConfig,
    WeaviateConfig,
    require_env_file,
)


def test_service_config_defaults():
    """Test ServiceConfig with default values."""
    config = ServiceConfig(service_name="test-service")
    assert config.service_name == "test-service"
    assert config.log_level == "INFO"
    assert config.port == 8080


def test_service_config_log_level_validation():
    """Test ServiceConfig validates log levels."""
    # Valid log level
    config = ServiceConfig(service_name="test", log_level="debug")
    assert config.log_level == "DEBUG"

    # Invalid log level
    with pytest.raises(ValidationError):
        ServiceConfig(service_name="test", log_level="INVALID")


def test_weaviate_config():
    """Test WeaviateConfig validation."""
    # Valid URL
    config = WeaviateConfig(weaviate_url="http://localhost:8080")
    assert config.weaviate_url == "http://localhost:8080"
    assert config.weaviate_timeout == 30

    # URL normalization (removes trailing slash)
    config = WeaviateConfig(weaviate_url="http://localhost:8080/")
    assert config.weaviate_url == "http://localhost:8080"

    # Invalid URL
    with pytest.raises(ValidationError):
        WeaviateConfig(weaviate_url="invalid-url")


def test_redis_config():
    """Test RedisConfig validation."""
    # Valid URL
    config = RedisConfig(redis_url="redis://localhost:6379")
    assert config.redis_url == "redis://localhost:6379"
    assert config.cache_ttl == 3600

    # Invalid URL
    with pytest.raises(ValidationError):
        RedisConfig(redis_url="http://wrong-protocol")


def test_openai_config():
    """Test OpenAIConfig validation."""
    # Valid API key
    config = OpenAIConfig(openai_api_key="sk-test-key-123")
    assert config.openai_api_key == "sk-test-key-123"
    assert config.openai_embedding_model == "text-embedding-3-small"

    # Invalid API key format
    with pytest.raises(ValidationError):
        OpenAIConfig(openai_api_key="invalid-key")

    # Placeholder API key
    with pytest.raises(ValidationError):
        OpenAIConfig(openai_api_key="sk-your-key-here")


def test_require_env_file_missing(tmp_path):
    """Test require_env_file raises error when file missing."""
    env_file = tmp_path / ".env"

    with pytest.raises(ConfigurationError) as exc_info:
        require_env_file(str(env_file))

    assert "not found" in str(exc_info.value)


def test_require_env_file_exists(tmp_path):
    """Test require_env_file succeeds when file exists."""
    env_file = tmp_path / ".env"
    env_file.write_text("TEST=value")

    # Should not raise
    require_env_file(str(env_file))
