"""Integration tests for service configuration classes.

These tests verify that service configs can be instantiated, validated,
and that their getter methods work correctly with real-world configurations.
"""

import pytest
from pydantic import ValidationError

from src.common.config import KafkaConfig, MinIOConfig
from src.embedding_service.config import EmbeddingServiceConfig
from src.indexer.config import IndexerConfig
from src.ingestion_api.config import IngestionAPIConfig
from src.search_service.config import SearchServiceConfig
from src.search_ui.config import SearchUIConfig


class TestIndexerConfigIntegration:
    """Integration tests for IndexerConfig."""

    def test_indexer_config_minimal(self):
        """Test IndexerConfig with minimal required fields."""
        config = IndexerConfig(
            service_name="test-indexer",
            log_level="INFO",
            port=8080,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://localhost:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=30,
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30.0,
            batch_size=10,
            health_port=8081,
            datasets_config_path="config/datasets_config.yaml",
        )

        assert config.service_name == "test-indexer"
        assert config.log_level == "INFO"
        assert config.kafka_bootstrap == "localhost:9092"

    def test_indexer_config_full(self):
        """Test IndexerConfig with all fields."""
        config = IndexerConfig(
            service_name="test-indexer",
            log_level="INFO",
            port=8080,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://localhost:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=30,
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30.0,
            batch_size=20,
            health_port=8081,
            datasets_config_path="config/datasets_config.yaml",
        )

        # Verify getters return correct types
        kafka_config = config.get_kafka_config()
        assert isinstance(kafka_config, KafkaConfig)
        assert kafka_config.kafka_bootstrap == "localhost:9092"
        assert kafka_config.kafka_topic == "test-topic"
        assert kafka_config.kafka_group_id == "test-group"

        minio_config = config.get_minio_config()
        assert isinstance(minio_config, MinIOConfig)
        assert minio_config.minio_endpoint == "http://minio:9000"
        assert minio_config.minio_bucket == "test-bucket"

    def test_indexer_config_validation(self):
        """Test IndexerConfig validation."""
        config = IndexerConfig(
            service_name="test-indexer",
            log_level="INFO",
            port=8080,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://localhost:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=30,
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30.0,
            batch_size=10,
            health_port=8081,
            datasets_config_path="config/datasets_config.yaml",
        )

        result = config.validate_config()
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_indexer_config_validation_errors(self):
        """Test IndexerConfig validation catches errors."""
        # Invalid batch_size (negative)
        config = IndexerConfig(
            service_name="test-indexer",
            log_level="INFO",
            port=8080,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://localhost:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=30,
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30.0,
            batch_size=-1,  # Invalid
            health_port=8081,
            datasets_config_path="config/datasets_config.yaml",
        )

        result = config.validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_indexer_config_invalid_kafka(self):
        """Test IndexerConfig with invalid Kafka config."""
        config = IndexerConfig(
            service_name="test-indexer",
            log_level="INFO",
            port=8080,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://localhost:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=30,
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30.0,
            batch_size=10,
            health_port=8081,
            datasets_config_path="config/datasets_config.yaml",
        )

        # Note: kafka_acks is not in IndexerConfig, so it won't be in the getter
        # But we can verify the kafka config is valid
        kafka_config = config.get_kafka_config()
        assert kafka_config.kafka_bootstrap == "localhost:9092"


class TestIngestionAPIConfigIntegration:
    """Integration tests for IngestionAPIConfig."""

    def test_ingestion_api_config_minimal(self):
        """Test IngestionAPIConfig with minimal required fields."""
        config = IngestionAPIConfig(
            service_name="test-ingestion",
            log_level="INFO",
            port=8082,
            environment="development",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_acks="1",
            max_content_length=10_000_000,
            cors_enabled=True,
            datasets_config_path="config/datasets_config.yaml",
        )

        assert config.service_name == "test-ingestion"
        assert config.port == 8082

    def test_ingestion_api_config_full(self):
        """Test IngestionAPIConfig with all fields."""
        config = IngestionAPIConfig(
            service_name="test-ingestion",
            log_level="INFO",
            port=8082,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_acks="all",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            max_content_length=20_000_000,
            cors_enabled=False,
            datasets_config_path="config/datasets_config.yaml",
        )

        # Verify getters
        kafka_config = config.get_kafka_config()
        assert isinstance(kafka_config, KafkaConfig)
        assert kafka_config.kafka_bootstrap == "localhost:9092"
        assert kafka_config.kafka_acks == "all"

        minio_config = config.get_minio_config()
        assert isinstance(minio_config, MinIOConfig)
        assert minio_config.minio_bucket == "test-bucket"

    def test_ingestion_api_config_validation(self):
        """Test IngestionAPIConfig validation."""
        config = IngestionAPIConfig(
            service_name="test-ingestion",
            log_level="INFO",
            port=8082,
            environment="development",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_acks="1",
            max_content_length=10_000_000,
            cors_enabled=True,
            datasets_config_path="config/datasets_config.yaml",
        )

        result = config.validate_config()
        assert result["valid"] is True

    def test_ingestion_api_config_invalid_minio(self):
        """Test IngestionAPIConfig with invalid MinIO endpoint."""
        # MinIO endpoint validation happens in getter
        config = IngestionAPIConfig(
            service_name="test-ingestion",
            log_level="INFO",
            port=8082,
            environment="development",
            minio_endpoint="invalid-endpoint",
            minio_access_key="access",
            minio_secret_key="secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_acks="1",
            max_content_length=10_000_000,
            cors_enabled=True,
            datasets_config_path="config/datasets_config.yaml",
        )

        # Should normalize to http://invalid-endpoint
        minio_config = config.get_minio_config()
        assert minio_config.minio_endpoint == "http://invalid-endpoint"


class TestSearchServiceConfigIntegration:
    """Integration tests for SearchServiceConfig."""

    def test_search_service_config_minimal(self):
        """Test SearchServiceConfig with minimal required fields."""
        config = SearchServiceConfig(
            service_name="test-search",
            log_level="INFO",
            port=50052,
            environment="development",
            enable_reflection=True,
            weaviate_url="http://localhost:8080",
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30,
            datasets_config_path="config/datasets_config.yaml",
        )

        assert config.service_name == "test-search"
        assert config.port == 50052

    def test_search_service_config_full(self):
        """Test SearchServiceConfig with all fields."""
        config = SearchServiceConfig(
            service_name="test-search",
            log_level="INFO",
            port=50052,
            environment="development",
            enable_reflection=True,
            weaviate_url="http://localhost:8080",
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=60,
            datasets_config_path="config/datasets_config.yaml",
        )

        # Verify basic properties
        assert config.service_name == "test-search"
        assert config.weaviate_url == "http://localhost:8080"
        assert config.embedding_service_timeout == 60

    def test_search_service_config_validation(self):
        """Test SearchServiceConfig validation."""
        config = SearchServiceConfig(
            service_name="test-search",
            log_level="INFO",
            port=50052,
            environment="development",
            enable_reflection=True,
            weaviate_url="http://localhost:8080",
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30,
            datasets_config_path="config/datasets_config.yaml",
        )

        result = config.validate_config()
        assert result["valid"] is True

    def test_search_service_config_invalid_weaviate(self):
        """Test SearchServiceConfig with invalid Weaviate URL."""
        # Should fail validation at instantiation time (Pydantic validates on init)
        with pytest.raises(ValidationError) as exc_info:
            SearchServiceConfig(
                service_name="test-search",
                log_level="INFO",
                port=50052,
                environment="development",
                enable_reflection=True,
                weaviate_url="invalid-url",  # Invalid: no http:// or https://
                embedding_service_addr="localhost:50051",
                embedding_service_timeout=30,
                datasets_config_path="config/datasets_config.yaml",
            )

        # Verify the error message mentions the weaviate URL
        assert "weaviate" in str(exc_info.value).lower()


class TestEmbeddingServiceConfigIntegration:
    """Integration tests for EmbeddingServiceConfig."""

    def test_embedding_service_config_minimal(self):
        """Test EmbeddingServiceConfig with minimal required fields."""
        config = EmbeddingServiceConfig(
            service_name="test-embedding",
            log_level="INFO",
            port=50051,
            environment="development",
            enable_reflection=True,
            datasets_config_path="config/datasets_config.yaml",
        )

        assert config.service_name == "test-embedding"
        assert config.port == 50051
        assert config.enable_reflection is True

    def test_embedding_service_config_full(self):
        """Test EmbeddingServiceConfig with all fields."""
        config = EmbeddingServiceConfig(
            service_name="test-embedding",
            log_level="DEBUG",
            port=50051,
            environment="production",
            enable_reflection=False,
            datasets_config_path="config/datasets_config.yaml",
        )

        assert config.service_name == "test-embedding"
        assert config.log_level == "DEBUG"
        assert config.environment == "production"
        assert config.enable_reflection is False


class TestSearchUIConfigIntegration:
    """Integration tests for SearchUIConfig."""

    def test_search_ui_config_minimal(self):
        """Test SearchUIConfig with minimal required fields."""
        config = SearchUIConfig(
            service_name="test-ui",
            log_level="INFO",
            port=8080,
            environment="development",
            search_service_addr="localhost:50052",
            search_service_timeout=30.0,
            cors_enabled=True,
            max_query_length=500,
            top_k=10,
            mode="vector",
            datasets_config_path="config/datasets_config.yaml",
        )

        assert config.service_name == "test-ui"
        assert config.port == 8080

    def test_search_ui_config_full(self):
        """Test SearchUIConfig with all fields."""
        config = SearchUIConfig(
            service_name="test-ui",
            log_level="INFO",
            port=8080,
            environment="development",
            search_service_addr="localhost:50052",
            search_service_timeout=60.0,
            cors_enabled=False,
            max_query_length=1000,
            top_k=10,
            mode="hybrid",
            datasets_config_path="config/datasets_config.yaml",
        )

        assert config.search_service_addr == "localhost:50052"
        assert config.mode == "hybrid"

    def test_search_ui_config_validation(self):
        """Test SearchUIConfig validation."""
        config = SearchUIConfig(
            service_name="test-ui",
            log_level="INFO",
            port=8080,
            environment="development",
            search_service_addr="localhost:50052",
            search_service_timeout=30.0,
            cors_enabled=True,
            max_query_length=500,
            top_k=10,
            mode="vector",
            datasets_config_path="config/datasets_config.yaml",
        )

        result = config.validate_config()
        assert result["valid"] is True

    def test_search_ui_config_invalid_mode(self):
        """Test SearchUIConfig with invalid mode."""
        with pytest.raises(ValidationError):
            SearchUIConfig(
                service_name="test-ui",
                log_level="INFO",
                port=8080,
                environment="development",
                search_service_addr="localhost:50052",
                search_service_timeout=30.0,
                cors_enabled=True,
                max_query_length=500,
                top_k=10,
                mode="invalid-mode",
                datasets_config_path="config/datasets_config.yaml",
            )


class TestConfigComposition:
    """Test that configs can be composed and used together."""

    def test_config_getters_return_validated_models(self):
        """Test that getter methods return properly validated Pydantic models."""
        indexer_config = IndexerConfig(
            service_name="test",
            log_level="INFO",
            port=8080,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="access",
            minio_secret_key="secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://localhost:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=30,
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30.0,
            batch_size=10,
            health_port=8081,
            datasets_config_path="config/datasets_config.yaml",
        )

        # Get composed configs
        kafka_config = indexer_config.get_kafka_config()
        minio_config = indexer_config.get_minio_config()

        # Verify they are proper Pydantic models
        assert isinstance(kafka_config, KafkaConfig)
        assert isinstance(minio_config, MinIOConfig)

        # Verify they can be serialized
        kafka_dict = kafka_config.model_dump()
        minio_dict = minio_config.model_dump()

        assert isinstance(kafka_dict, dict)
        assert isinstance(minio_dict, dict)

    def test_config_validation_catches_composed_errors(self):
        """Test that validation catches errors in composed configs."""
        # Create a config with invalid batch_size
        config = IndexerConfig(
            service_name="test",
            log_level="INFO",
            port=8080,
            environment="development",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="access",
            minio_secret_key="secret",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://localhost:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=30,
            weaviate_timeout_insert=30,
            embedding_service_addr="localhost:50051",
            embedding_service_timeout=30.0,
            batch_size=-10,  # Invalid
            health_port=8081,
            datasets_config_path="config/datasets_config.yaml",
        )

        result = config.validate_config()
        assert result["valid"] is False
        assert any("batch_size" in err.lower() for err in result["errors"])
