"""Unit tests for src/ingestion_api/config.py.

Tests cover:
- IngestionAPIConfig MinIO endpoint validation
- Getter methods for composed configs (Kafka, MinIO)
- Cross-field validation
"""

import pytest

from src.ingestion_api.config import IngestionAPIConfig


class TestIngestionAPIConfigGetters:
    """Tests for IngestionAPIConfig getter methods."""

    @pytest.fixture
    def valid_config(self, monkeypatch):
        """Create a valid IngestionAPIConfig for testing."""
        env_vars = {
            "SERVICE_NAME": "ingestion-api-test",
            "PORT": "8082",
            "LOG_LEVEL": "INFO",
            "ENVIRONMENT": "test",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_BUCKET": "documents",
            "MINIO_SECURE": "false",
            "KAFKA_BOOTSTRAP": "localhost:9092",
            "KAFKA_TOPIC": "documents",
            "KAFKA_ACKS": "1",
            "MAX_CONTENT_LENGTH": "10485760",
            "CORS_ENABLED": "true",
            "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        return IngestionAPIConfig()

    def test_get_kafka_config(self, valid_config):
        """Test get_kafka_config returns KafkaConfig with correct values."""
        kafka_config = valid_config.get_kafka_config()

        assert kafka_config.kafka_bootstrap == "localhost:9092"
        assert kafka_config.kafka_topic == "documents"
        assert kafka_config.kafka_acks == "1"

    def test_get_minio_config(self, valid_config):
        """Test get_minio_config returns MinIOConfig with correct values."""
        minio_config = valid_config.get_minio_config()

        # Endpoint is normalized by validator
        assert minio_config.minio_endpoint == "http://localhost:9000"
        assert minio_config.minio_access_key == "minioadmin"
        assert minio_config.minio_secret_key == "minioadmin"
        assert minio_config.minio_bucket == "documents"
        assert minio_config.minio_secure is False


class TestIngestionAPIConfigMinIOValidation:
    """Tests for IngestionAPIConfig MinIO endpoint validation."""

    def test_endpoint_with_http(self):
        """Tests that http:// prefix is preserved."""
        config = IngestionAPIConfig(minio_endpoint="http://localhost:9000")

        assert config.minio_endpoint == "http://localhost:9000"

    def test_endpoint_with_https(self):
        """Tests that https:// prefix is preserved."""
        config = IngestionAPIConfig(minio_endpoint="https://minio.example.com")

        assert config.minio_endpoint == "https://minio.example.com"

    def test_endpoint_without_scheme(self):
        """Tests that http:// is added when no scheme provided."""
        config = IngestionAPIConfig(minio_endpoint="minio:9000")

        assert config.minio_endpoint == "http://minio:9000"

    def test_endpoint_strips_trailing_slash(self):
        """Tests that trailing slash is stripped."""
        config = IngestionAPIConfig(minio_endpoint="http://minio:9000/")

        assert config.minio_endpoint == "http://minio:9000"


class TestIngestionAPIConfigValidation:
    """Tests for IngestionAPIConfig cross-field validation."""

    def test_validate_config_negative_max_content_length(self, monkeypatch):
        """Test validation fails with negative max_content_length."""
        env_vars = {
            "SERVICE_NAME": "ingestion-api-test",
            "PORT": "8082",
            "LOG_LEVEL": "INFO",
            "ENVIRONMENT": "test",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_BUCKET": "documents",
            "MINIO_SECURE": "false",
            "KAFKA_BOOTSTRAP": "localhost:9092",
            "KAFKA_TOPIC": "documents",
            "KAFKA_ACKS": "1",
            "MAX_CONTENT_LENGTH": "-100",  # Invalid: negative
            "CORS_ENABLED": "true",
            "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        config = IngestionAPIConfig()
        validation_result = config.validate_config()

        assert validation_result["valid"] is False
        assert any("max_content_length must be positive" in err for err in validation_result["errors"])

    def test_validate_config_all_valid(self, monkeypatch):
        """Test validation passes with all valid values."""
        env_vars = {
            "SERVICE_NAME": "ingestion-api-test",
            "PORT": "8082",
            "LOG_LEVEL": "INFO",
            "ENVIRONMENT": "test",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_BUCKET": "documents",
            "MINIO_SECURE": "false",
            "KAFKA_BOOTSTRAP": "localhost:9092",
            "KAFKA_TOPIC": "documents",
            "KAFKA_ACKS": "1",
            "MAX_CONTENT_LENGTH": "10485760",
            "CORS_ENABLED": "true",
            "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        config = IngestionAPIConfig()
        validation_result = config.validate_config()

        assert validation_result["valid"] is True
        assert len(validation_result["errors"]) == 0
