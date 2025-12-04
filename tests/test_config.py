"""Tests for configuration validation."""

import pytest
from pydantic import ValidationError

from src.common.config import (
    KafkaConfig,
    OpenAIConfig,
    RedisConfig,
    ServiceConfig,
    WeaviateConfig,
    get_env_or_error,
    require_env_file,
)
from src.core.errors import ConfigurationError


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


def test_require_env_file_missing_with_example(tmp_path):
    """Test require_env_file provides copy hint when example exists."""
    env_file = tmp_path / ".env"
    example_file = tmp_path / ".env.example"
    example_file.write_text("TEST=example-value")

    with pytest.raises(ConfigurationError) as exc_info:
        require_env_file(str(env_file))

    error_msg = str(exc_info.value)
    assert "not found" in error_msg
    assert "cp" in error_msg
    assert ".env.example" in error_msg


def test_require_env_file_missing_without_example(tmp_path):
    """Test require_env_file error message without example file."""
    env_file = tmp_path / ".env"

    with pytest.raises(ConfigurationError) as exc_info:
        require_env_file(str(env_file))

    error_msg = str(exc_info.value)
    assert "not found" in error_msg
    assert "Create" in error_msg


def test_get_env_or_error_returns_value(monkeypatch):
    """Test get_env_or_error returns environment variable."""
    monkeypatch.setenv("TEST_VAR", "test-value")

    result = get_env_or_error("TEST_VAR")

    assert result == "test-value"


def test_get_env_or_error_returns_default(monkeypatch):
    """Test get_env_or_error returns default when env not set."""
    monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

    result = get_env_or_error("NONEXISTENT_VAR", default="default-value")

    assert result == "default-value"


def test_get_env_or_error_raises_when_missing(monkeypatch):
    """Test get_env_or_error raises ConfigurationError when missing."""
    monkeypatch.delenv("MISSING_VAR", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        get_env_or_error("MISSING_VAR")

    assert "MISSING_VAR" in str(exc_info.value)
    assert "not set" in str(exc_info.value)


def test_base_config_from_env(tmp_path):
    """Test BaseConfig.from_env loads from env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("SERVICE_NAME=test-from-env\n")

    config = ServiceConfig.from_env(str(env_file))

    # Just verify it doesn't raise - actual value depends on environment
    assert config is not None


def test_base_config_from_env_validation_error(tmp_path):
    """Test BaseConfig.from_env raises ConfigurationError on invalid config."""
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=INVALID_LEVEL\n")

    # ServiceConfig requires service_name, so this should fail
    with pytest.raises(ConfigurationError) as exc_info:
        ServiceConfig.from_env(str(env_file))

    assert "Failed to load configuration" in str(exc_info.value)


def test_kafka_config_defaults():
    """Test KafkaConfig with default values."""
    config = KafkaConfig()

    assert config.kafka_bootstrap == "kafka:9092"
    assert config.kafka_topic == "document-changes"


def test_kafka_config_custom_values():
    """Test KafkaConfig with custom values."""
    config = KafkaConfig(
        kafka_bootstrap="localhost:29092",
        kafka_topic="custom-topic",
    )

    assert config.kafka_bootstrap == "localhost:29092"
    assert config.kafka_topic == "custom-topic"


def test_openai_config_empty_key():
    """Test OpenAIConfig rejects empty API key."""
    with pytest.raises(ValidationError) as exc_info:
        OpenAIConfig(openai_api_key="")

    assert "not configured" in str(exc_info.value)
