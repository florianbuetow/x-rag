"""Unit tests for src/indexer/config.py.

Tests cover:
- IndexerConfig loading from environment
- Getter methods for composed configs (Kafka, MinIO)
- Cross-field validation
"""

import pytest

from src.indexer.config import IndexerConfig


class TestIndexerConfigGetters:
    """Tests for IndexerConfig getter methods."""

    @pytest.fixture
    def valid_config(self, monkeypatch):
        """Create a valid IndexerConfig for testing."""
        env_vars = {
            "SERVICE_NAME": "indexer-test",
            "PORT": "8080",
            "LOG_LEVEL": "INFO",
            "ENVIRONMENT": "test",
            "KAFKA_BOOTSTRAP": "localhost:9092",
            "KAFKA_TOPIC": "documents",
            "KAFKA_GROUP_ID": "indexer-group",
            "KAFKA_AUTO_OFFSET_RESET": "earliest",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_BUCKET": "documents",
            "MINIO_SECURE": "false",
            "WEAVIATE_URL": "http://localhost:8081",
            "WEAVIATE_TIMEOUT_INIT": "30",
            "WEAVIATE_TIMEOUT_QUERY": "60",
            "WEAVIATE_TIMEOUT_INSERT": "120",
            "EMBEDDING_SERVICE_ADDR": "localhost:50051",
            "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
            "BATCH_SIZE": "32",
            "HEALTH_PORT": "8081",
            "EMBEDDING_SERVICE_TIMEOUT": "30.0",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        return IndexerConfig()

    def test_get_kafka_config(self, valid_config):
        """Test get_kafka_config returns KafkaConfig with correct values."""
        kafka_config = valid_config.get_kafka_config()

        assert kafka_config.kafka_bootstrap == "localhost:9092"
        assert kafka_config.kafka_topic == "documents"
        assert kafka_config.kafka_group_id == "indexer-group"
        assert kafka_config.kafka_auto_offset_reset == "earliest"

    def test_get_minio_config(self, valid_config):
        """Test get_minio_config returns MinIOConfig with correct values."""
        minio_config = valid_config.get_minio_config()

        # MinIOConfig normalizes endpoint by adding http:// prefix
        assert minio_config.minio_endpoint == "http://localhost:9000"
        assert minio_config.minio_access_key == "minioadmin"
        assert minio_config.minio_secret_key == "minioadmin"
        assert minio_config.minio_bucket == "documents"
        assert minio_config.minio_secure is False


class TestIndexerConfigValidation:
    """Tests for IndexerConfig cross-field validation."""

    def test_validate_config_negative_batch_size(self, monkeypatch):
        """Test validation fails with negative batch_size."""
        env_vars = {
            "SERVICE_NAME": "indexer-test",
            "PORT": "8080",
            "LOG_LEVEL": "INFO",
            "ENVIRONMENT": "test",
            "KAFKA_BOOTSTRAP": "localhost:9092",
            "KAFKA_TOPIC": "documents",
            "KAFKA_GROUP_ID": "indexer-group",
            "KAFKA_AUTO_OFFSET_RESET": "earliest",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_BUCKET": "documents",
            "MINIO_SECURE": "false",
            "WEAVIATE_URL": "http://localhost:8081",
            "WEAVIATE_TIMEOUT_INIT": "30",
            "WEAVIATE_TIMEOUT_QUERY": "60",
            "WEAVIATE_TIMEOUT_INSERT": "120",
            "EMBEDDING_SERVICE_ADDR": "localhost:50051",
            "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
            "BATCH_SIZE": "-5",  # Invalid: negative
            "HEALTH_PORT": "8081",
            "EMBEDDING_SERVICE_TIMEOUT": "30.0",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        config = IndexerConfig()
        validation_result = config.validate_config()

        assert validation_result["valid"] is False
        assert any("batch_size must be positive" in err for err in validation_result["errors"])

    def test_validate_config_negative_timeout(self, monkeypatch):
        """Test validation fails with negative embedding_service_timeout."""
        env_vars = {
            "SERVICE_NAME": "indexer-test",
            "PORT": "8080",
            "LOG_LEVEL": "INFO",
            "ENVIRONMENT": "test",
            "KAFKA_BOOTSTRAP": "localhost:9092",
            "KAFKA_TOPIC": "documents",
            "KAFKA_GROUP_ID": "indexer-group",
            "KAFKA_AUTO_OFFSET_RESET": "earliest",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_BUCKET": "documents",
            "MINIO_SECURE": "false",
            "WEAVIATE_URL": "http://localhost:8081",
            "WEAVIATE_TIMEOUT_INIT": "30",
            "WEAVIATE_TIMEOUT_QUERY": "60",
            "WEAVIATE_TIMEOUT_INSERT": "120",
            "EMBEDDING_SERVICE_ADDR": "localhost:50051",
            "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
            "BATCH_SIZE": "32",
            "HEALTH_PORT": "8081",
            "EMBEDDING_SERVICE_TIMEOUT": "-10.0",  # Invalid: negative
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        config = IndexerConfig()
        validation_result = config.validate_config()

        assert validation_result["valid"] is False
        assert any("embedding_service_timeout must be positive" in err for err in validation_result["errors"])

    def test_validate_config_all_valid(self, monkeypatch):
        """Test validation passes with all valid values."""
        env_vars = {
            "SERVICE_NAME": "indexer-test",
            "PORT": "8080",
            "LOG_LEVEL": "INFO",
            "ENVIRONMENT": "test",
            "KAFKA_BOOTSTRAP": "localhost:9092",
            "KAFKA_TOPIC": "documents",
            "KAFKA_GROUP_ID": "indexer-group",
            "KAFKA_AUTO_OFFSET_RESET": "earliest",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_BUCKET": "documents",
            "MINIO_SECURE": "false",
            "WEAVIATE_URL": "http://localhost:8081",
            "WEAVIATE_TIMEOUT_INIT": "30",
            "WEAVIATE_TIMEOUT_QUERY": "60",
            "WEAVIATE_TIMEOUT_INSERT": "120",
            "EMBEDDING_SERVICE_ADDR": "localhost:50051",
            "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
            "BATCH_SIZE": "32",
            "HEALTH_PORT": "8081",
            "EMBEDDING_SERVICE_TIMEOUT": "30.0",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        config = IndexerConfig()
        validation_result = config.validate_config()

        assert validation_result["valid"] is True
        assert len(validation_result["errors"]) == 0
