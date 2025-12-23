"""Tests for configuration validation."""

import pytest
from pydantic import ValidationError

from src.common.config import (
    KafkaConfig,
    MinIOConfig,
    OpenAIConfig,
    RedisConfig,
    ServiceConfig,
    WeaviateConfig,
    get_env_or_error,
    require_env_file,
)
from src.core.errors import ConfigurationError
from src.indexer.config import IndexerConfig
from src.ingestion_api.config import IngestionAPIConfig
from src.search_service.config import SearchServiceConfig


def test_service_config_defaults():
    """Test ServiceConfig requires all fields."""
    config = ServiceConfig(
        service_name="test-service",
        log_level="INFO",
        port=8080,
        environment="test",
    )
    assert config.service_name == "test-service"
    assert config.log_level == "INFO"
    assert config.port == 8080
    assert config.environment == "test"


def test_service_config_log_level_validation():
    """Test ServiceConfig validates log levels."""
    # Valid log level
    config = ServiceConfig(
        service_name="test",
        log_level="debug",
        port=8080,
        environment="test",
    )
    assert config.log_level == "DEBUG"

    # Invalid log level
    with pytest.raises(ValidationError):
        ServiceConfig(
            service_name="test",
            log_level="INVALID",
            port=8080,
            environment="test",
        )


def test_weaviate_config():
    """Test WeaviateConfig validation."""
    # Valid URL
    config = WeaviateConfig(
        weaviate_url="http://localhost:8080",
        weaviate_timeout_init=30,
        weaviate_timeout_query=30,
        weaviate_timeout_insert=60,
        weaviate_collection="TestCollection",
    )
    assert config.weaviate_url == "http://localhost:8080"
    assert config.weaviate_timeout_query == 30

    # URL normalization (removes trailing slash)
    config = WeaviateConfig(
        weaviate_url="http://localhost:8080/",
        weaviate_timeout_init=30,
        weaviate_timeout_query=30,
        weaviate_timeout_insert=60,
        weaviate_collection="TestCollection",
    )
    assert config.weaviate_url == "http://localhost:8080"

    # Invalid URL
    with pytest.raises(ValidationError):
        WeaviateConfig(
            weaviate_url="invalid-url",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=60,
            weaviate_collection="TestCollection",
        )


def test_redis_config():
    """Test RedisConfig validation."""
    # Valid URL
    config = RedisConfig(
        redis_url="redis://localhost:6379",
        cache_ttl=3600,
        enable_cache=True,
    )
    assert config.redis_url == "redis://localhost:6379"
    assert config.cache_ttl == 3600
    assert config.enable_cache is True

    # Invalid URL
    with pytest.raises(ValidationError):
        RedisConfig(
            redis_url="http://wrong-protocol",
            cache_ttl=3600,
            enable_cache=True,
        )


def test_openai_config():
    """Test OpenAIConfig validation."""
    # Valid API key (any non-empty string)
    config = OpenAIConfig(
        openai_api_key="sk-test-key-123",
        openai_model="gpt-4",
        openai_max_tokens=1000,
        openai_temperature=0.7,
        openai_max_retries=3,
        openai_timeout=60,
    )
    assert config.openai_api_key == "sk-test-key-123"
    assert config.openai_model == "gpt-4"
    assert config.openai_max_tokens == 1000
    assert config.openai_temperature == 0.7

    # Invalid API key format (empty)
    with pytest.raises(ValidationError):
        OpenAIConfig(
            openai_api_key="",
            openai_model="gpt-4",
            openai_max_tokens=1000,
            openai_temperature=0.7,
            openai_max_retries=3,
            openai_timeout=60,
        )

    # Local LLM (any non-empty key is valid)
    config = OpenAIConfig(
        openai_api_key="local-key",
        openai_api_base="http://localhost:1234",
        openai_model="local-model",
        openai_max_tokens=1000,
        openai_temperature=0.7,
        openai_max_retries=3,
        openai_timeout=60,
    )
    assert config.openai_api_key == "local-key"
    assert config.openai_api_base == "http://localhost:1234"


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


def test_get_env_or_error_raises_when_not_set(monkeypatch):
    """Test get_env_or_error raises ConfigurationError when env not set."""
    monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

    with pytest.raises(ConfigurationError):
        get_env_or_error("NONEXISTENT_VAR")


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


def test_base_config_from_env_validation_error(tmp_path, monkeypatch):
    """Test BaseConfig.from_env raises ConfigurationError on invalid config."""
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=INVALID_LEVEL\n")

    # Clear all environment variables that ServiceConfig might use
    for key in ["SERVICE_NAME", "LOG_LEVEL", "PORT", "ENVIRONMENT", "OTLP_ENDPOINT"]:
        monkeypatch.delenv(key, raising=False)

    # ServiceConfig requires service_name, so this should fail
    with pytest.raises(ConfigurationError) as exc_info:
        ServiceConfig.from_env(str(env_file))

    assert "Failed to load configuration" in str(exc_info.value)


def test_kafka_config_defaults():
    """Test KafkaConfig requires all fields."""
    config = KafkaConfig(
        kafka_bootstrap="kafka:9092",
        kafka_topic="document-changes",
    )

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
        OpenAIConfig(
            openai_api_key="",
            openai_model="gpt-4",
            openai_max_tokens=1000,
            openai_temperature=0.7,
            openai_max_retries=3,
            openai_timeout=60,
        )

    assert "not configured" in str(exc_info.value)


def test_weaviate_config_collection():
    """Test WeaviateConfig with collection."""
    config = WeaviateConfig(
        weaviate_url="http://localhost:8080",
        weaviate_timeout_init=30,
        weaviate_timeout_query=30,
        weaviate_timeout_insert=60,
        weaviate_collection="TestCollection",
    )
    assert config.weaviate_collection == "TestCollection"
    assert config.weaviate_timeout_query == 30


def test_redis_config_enable_cache():
    """Test RedisConfig with enable_cache."""
    config = RedisConfig(
        redis_url="redis://localhost:6379",
        cache_ttl=3600,
        enable_cache=True,
    )
    assert config.enable_cache is True
    assert config.cache_ttl == 3600


def test_kafka_config_validation():
    """Test KafkaConfig validation."""
    # Valid acks
    config = KafkaConfig(
        kafka_bootstrap="kafka:9092",
        kafka_topic="test-topic",
        kafka_acks="all",
    )
    assert config.kafka_acks == "all"

    # Invalid acks
    with pytest.raises(ValidationError):
        KafkaConfig(
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            kafka_acks="invalid",
        )

    # Valid auto_offset_reset
    config = KafkaConfig(
        kafka_bootstrap="kafka:9092",
        kafka_topic="test-topic",
        kafka_auto_offset_reset="latest",
    )
    assert config.kafka_auto_offset_reset == "latest"

    # Invalid auto_offset_reset
    with pytest.raises(ValidationError):
        KafkaConfig(
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            kafka_auto_offset_reset="invalid",
        )


def test_minio_config():
    """Test MinIOConfig validation."""
    # Valid endpoint
    config = MinIOConfig(
        minio_endpoint="minio:9000",
        minio_access_key="access",
        minio_secret_key="secret",
        minio_bucket="documents",
        minio_secure=False,
    )
    assert config.minio_endpoint == "http://minio:9000"
    assert config.minio_bucket == "documents"

    # Endpoint with http://
    config = MinIOConfig(
        minio_endpoint="http://minio:9000",
        minio_access_key="access",
        minio_secret_key="secret",
        minio_bucket="documents",
        minio_secure=False,
    )
    assert config.minio_endpoint == "http://minio:9000"


def test_service_config_validate_config():
    """Test ServiceConfig validate_config method."""
    config = ServiceConfig(
        service_name="test-service",
        log_level="INFO",
        port=8080,
        environment="test",
    )
    result = config.validate_config()

    assert result["valid"] is True
    assert len(result["errors"]) == 0
    assert isinstance(result["warnings"], list)


def test_service_config_get_config_dict():
    """Test ServiceConfig get_config_dict method."""
    config = ServiceConfig(
        service_name="test-service",
        log_level="INFO",
        port=9090,
        environment="test",
    )
    config_dict = config.get_config_dict()

    assert isinstance(config_dict, dict)
    assert config_dict["service_name"] == "test-service"
    assert config_dict["port"] == 9090


def test_indexer_config_getters():
    """Test IndexerConfig getter methods."""
    config = IndexerConfig(
        service_name="test-indexer",
        log_level="INFO",
        port=8080,
        environment="test",
        kafka_bootstrap="localhost:9092",
        kafka_topic="test-topic",
        kafka_group_id="test-group",
        kafka_auto_offset_reset="earliest",
        minio_endpoint="minio:9000",
        minio_access_key="access",
        minio_secret_key="secret",
        minio_bucket="documents",
        minio_secure=False,
        weaviate_url="http://weaviate:8080",
        weaviate_timeout_init=30,
        weaviate_timeout_query=30,
        weaviate_timeout_insert=60,
        embedding_service_addr="localhost:50051",
        embedding_service_timeout=30.0,
        datasets_config_path="config/datasets_config.yaml",
        batch_size=10,
        health_port=8081,
    )

    # Test Kafka config getter
    kafka_config = config.get_kafka_config()
    assert isinstance(kafka_config, KafkaConfig)
    assert kafka_config.kafka_bootstrap == "localhost:9092"
    assert kafka_config.kafka_topic == "test-topic"

    # Test MinIO config getter
    minio_config = config.get_minio_config()
    assert isinstance(minio_config, MinIOConfig)
    assert minio_config.minio_endpoint == "http://minio:9000"

    # Weaviate config is now per-dataset in datasets_config.yaml, not in IndexerConfig


def test_indexer_config_validation():
    """Test IndexerConfig validation."""
    config = IndexerConfig(
        service_name="test-indexer",
        log_level="INFO",
        port=8080,
        environment="test",
        kafka_bootstrap="localhost:9092",
        kafka_topic="test-topic",
        kafka_group_id="test-group",
        kafka_auto_offset_reset="earliest",
        minio_endpoint="minio:9000",
        minio_access_key="access",
        minio_secret_key="secret",
        minio_bucket="documents",
        minio_secure=False,
        weaviate_url="http://weaviate:8080",
        weaviate_timeout_init=30,
        weaviate_timeout_query=30,
        weaviate_timeout_insert=60,
        embedding_service_addr="localhost:50051",
        embedding_service_timeout=30.0,
        datasets_config_path="config/datasets_config.yaml",
        batch_size=10,
        health_port=8081,
    )
    result = config.validate_config()
    assert result["valid"] is True

    # Chunking config (chunk_size, chunk_overlap) is now per-dataset in datasets_config.yaml


def test_ingestion_api_config_getters():
    """Test IngestionAPIConfig getter methods."""
    config = IngestionAPIConfig(
        service_name="test-ingestion",
        log_level="INFO",
        port=8082,
        environment="test",
        kafka_bootstrap="localhost:9092",
        kafka_topic="test-topic",
        kafka_acks="1",
        minio_endpoint="minio:9000",
        minio_access_key="access",
        minio_secret_key="secret",
        minio_bucket="documents",
        minio_secure=False,
        max_content_length=10485760,
        cors_enabled=True,
        datasets_config_path="config/datasets_config.yaml",
    )

    # Test Kafka config getter
    kafka_config = config.get_kafka_config()
    assert isinstance(kafka_config, KafkaConfig)
    assert kafka_config.kafka_bootstrap == "localhost:9092"

    # Test MinIO config getter
    minio_config = config.get_minio_config()
    assert isinstance(minio_config, MinIOConfig)
    assert minio_config.minio_endpoint == "http://minio:9000"


def test_search_service_config_getters():
    """Test SearchServiceConfig getter methods."""
    config = SearchServiceConfig(
        service_name="test-search",
        log_level="INFO",
        port=50052,
        environment="test",
        enable_reflection=True,
        weaviate_url="http://weaviate:8080",
        embedding_service_addr="localhost:50051",
        embedding_service_timeout=30,
        datasets_config_path="config/datasets_config.yaml",
    )

    # Weaviate, LLM, and OpenAI configs are now per-dataset in datasets_config.yaml
    # SearchServiceConfig is now just infrastructure settings
    assert config.service_name == "test-search"
    assert config.datasets_config_path == "config/datasets_config.yaml"
