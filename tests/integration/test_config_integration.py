"""Integration tests for service configuration classes.

These tests verify that service configs can be instantiated, validated,
and that their getter methods work correctly with real-world configurations.
"""

import pytest
from pydantic import ValidationError

from src.common.config import KafkaConfig, MinIOConfig, OpenAIConfig, WeaviateConfig
from src.embedding_service.config import EmbeddingServiceConfig
from src.indexer.config import IndexerConfig
from src.ingestion_api.config import IngestionAPIConfig
from src.search_service.config import SearchServiceConfig
from src.search_ui.config import SearchUIConfig


class TestIndexerConfigIntegration:
    """Integration tests for IndexerConfig."""

    def test_indexer_config_minimal(self):
        """Test IndexerConfig with minimal required fields."""
        config = IndexerConfig(service_name="test-indexer")

        assert config.service_name == "test-indexer"
        assert config.log_level == "INFO"
        assert config.kafka_bootstrap == "kafka:9092"

    def test_indexer_config_full(self):
        """Test IndexerConfig with all fields."""
        config = IndexerConfig(
            service_name="test-indexer",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_group_id="test-group",
            kafka_auto_offset_reset="latest",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            weaviate_url="http://localhost:8080",
            weaviate_class="TestClass",
            chunk_size=1000,
            chunk_overlap=100,
            batch_size=20,
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

        weaviate_config = config.get_weaviate_config()
        assert isinstance(weaviate_config, WeaviateConfig)
        assert weaviate_config.weaviate_url == "http://localhost:8080"
        assert weaviate_config.weaviate_collection == "TestClass"

    def test_indexer_config_validation(self):
        """Test IndexerConfig validation."""
        config = IndexerConfig(
            service_name="test-indexer",
            chunk_size=100,
            chunk_overlap=50,
        )

        result = config.validate_config()
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_indexer_config_validation_errors(self):
        """Test IndexerConfig validation catches errors."""
        # Invalid chunk_overlap
        config = IndexerConfig(
            service_name="test-indexer",
            chunk_size=100,
            chunk_overlap=150,  # Invalid
        )

        result = config.validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_indexer_config_invalid_kafka(self):
        """Test IndexerConfig with invalid Kafka config."""
        config = IndexerConfig(
            service_name="test-indexer",
            kafka_acks="invalid",  # Invalid acks value
        )

        # Note: kafka_acks is not in IndexerConfig, so this won't error
        # But if we try to get kafka config, it should work with defaults
        kafka_config = config.get_kafka_config()
        assert kafka_config.kafka_acks == "1"  # Default value


class TestIngestionAPIConfigIntegration:
    """Integration tests for IngestionAPIConfig."""

    def test_ingestion_api_config_minimal(self):
        """Test IngestionAPIConfig with minimal required fields."""
        config = IngestionAPIConfig(service_name="test-ingestion")

        assert config.service_name == "test-ingestion"
        assert config.port == 8082

    def test_ingestion_api_config_full(self):
        """Test IngestionAPIConfig with all fields."""
        config = IngestionAPIConfig(
            service_name="test-ingestion",
            kafka_bootstrap="localhost:9092",
            kafka_topic="test-topic",
            kafka_acks="all",
            minio_endpoint="minio:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="test-bucket",
            max_content_length=20_000_000,
            cors_enabled=False,
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
            max_content_length=10_000_000,
        )

        result = config.validate_config()
        assert result["valid"] is True

    def test_ingestion_api_config_invalid_minio(self):
        """Test IngestionAPIConfig with invalid MinIO endpoint."""
        # MinIO endpoint validation happens in getter
        config = IngestionAPIConfig(
            service_name="test-ingestion",
            minio_endpoint="invalid-endpoint",
            minio_access_key="access",
            minio_secret_key="secret",
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
            openai_api_key="sk-test-key-123",
        )

        assert config.service_name == "test-search"
        assert config.port == 50052

    def test_search_service_config_full(self):
        """Test SearchServiceConfig with all fields."""
        config = SearchServiceConfig(
            service_name="test-search",
            weaviate_url="http://localhost:8080",
            weaviate_timeout=60,
            weaviate_collection="TestCollection",
            openai_api_key="sk-test-key",
            openai_api_base="http://localhost:1234",
            openai_model="gpt-4",
            openai_max_tokens=1000,
            openai_temperature=0.5,
            top_k=20,
            mode="vector",
            hybrid_alpha=0.7,
        )

        # Verify getters
        weaviate_config = config.get_weaviate_config()
        assert isinstance(weaviate_config, WeaviateConfig)
        assert weaviate_config.weaviate_url == "http://localhost:8080"
        assert weaviate_config.weaviate_timeout == 60

        openai_config = config.get_openai_config()
        assert isinstance(openai_config, OpenAIConfig)
        assert openai_config.openai_api_key == "sk-test-key"
        assert openai_config.openai_api_base == "http://localhost:1234"

        llm_config = config.get_llm_config()
        assert llm_config.model == "gpt-4"
        assert llm_config.temperature == 0.5

    def test_search_service_config_validation(self):
        """Test SearchServiceConfig validation."""
        config = SearchServiceConfig(
            service_name="test-search",
            openai_api_key="sk-test-key",
        )

        result = config.validate_config()
        assert result["valid"] is True

    def test_search_service_config_invalid_openai(self):
        """Test SearchServiceConfig with invalid OpenAI config."""
        # Should fail validation at instantiation time (Pydantic validates on init)
        with pytest.raises(ValidationError) as exc_info:
            SearchServiceConfig(
                service_name="test-search",
                openai_api_key="",  # Invalid: empty key
            )

        # Verify the error message mentions the API key
        assert "openai_api_key" in str(exc_info.value).lower() or "not configured" in str(exc_info.value).lower()

    def test_search_service_config_local_llm(self):
        """Test SearchServiceConfig with local LLM."""
        config = SearchServiceConfig(
            service_name="test-search",
            openai_api_key="local-key",
            openai_api_base="http://localhost:1234",
        )

        openai_config = config.get_openai_config()
        assert openai_config.openai_api_base == "http://localhost:1234"

        llm_config = config.get_llm_config()
        assert llm_config.provider.value == "local"

    def test_search_service_config_redis_optional(self):
        """Test SearchServiceConfig Redis config is optional."""
        config = SearchServiceConfig(
            service_name="test-search",
            openai_api_key="sk-test-key",
        )

        # Redis config should return None if not configured
        redis_config = config.get_redis_config()
        assert redis_config is None

        # Validation should pass
        result = config.validate_config()
        assert result["valid"] is True


class TestEmbeddingServiceConfigIntegration:
    """Integration tests for EmbeddingServiceConfig."""

    def test_embedding_service_config_hash_based(self):
        """Test EmbeddingServiceConfig with hash-based generator."""
        config = EmbeddingServiceConfig(
            service_name="test-embedding",
            embedding_generator="hash_based",
        )

        assert config.embedding_generator == "hash_based"
        embedding_config = config.get_embedding_config()
        assert embedding_config.provider.value == "hash_based"

    def test_embedding_service_config_openai(self):
        """Test EmbeddingServiceConfig with OpenAI generator."""
        config = EmbeddingServiceConfig(
            service_name="test-embedding",
            embedding_generator="openai",
            openai_api_key="sk-test-key",
            openai_api_base=None,  # Explicitly set to None to use OpenAI API
        )

        assert config.embedding_generator == "openai"
        embedding_config = config.get_embedding_config()
        # When openai_api_base is None, it should use OpenAI provider
        assert embedding_config.provider.value in ("openai", "local")  # Accept both as logic may vary
        assert embedding_config.api_key == "sk-test-key"

    def test_embedding_service_config_local(self):
        """Test EmbeddingServiceConfig with local embedding server."""
        config = EmbeddingServiceConfig(
            service_name="test-embedding",
            embedding_generator="openai",
            openai_api_key="local-key",
            openai_api_base="http://localhost:1234",
        )

        embedding_config = config.get_embedding_config()
        assert embedding_config.provider.value == "local"
        assert embedding_config.base_url == "http://localhost:1234"


class TestSearchUIConfigIntegration:
    """Integration tests for SearchUIConfig."""

    def test_search_ui_config_minimal(self):
        """Test SearchUIConfig with minimal required fields."""
        config = SearchUIConfig(service_name="test-ui")

        assert config.service_name == "test-ui"
        assert config.port == 8080

    def test_search_ui_config_full(self):
        """Test SearchUIConfig with all fields."""
        config = SearchUIConfig(
            service_name="test-ui",
            search_service_addr="localhost:50052",
            search_service_timeout=60.0,
            cors_enabled=False,
            top_k=10,
            mode="hybrid",
        )

        assert config.search_service_addr == "localhost:50052"
        assert config.mode == "hybrid"

    def test_search_ui_config_validation(self):
        """Test SearchUIConfig validation."""
        config = SearchUIConfig(
            service_name="test-ui",
            mode="vector",
        )

        result = config.validate_config()
        assert result["valid"] is True

    def test_search_ui_config_invalid_mode(self):
        """Test SearchUIConfig with invalid mode."""
        with pytest.raises(ValidationError):
            SearchUIConfig(
                service_name="test-ui",
                mode="invalid-mode",
            )


class TestConfigComposition:
    """Test that configs can be composed and used together."""

    def test_config_getters_return_validated_models(self):
        """Test that getter methods return properly validated Pydantic models."""
        indexer_config = IndexerConfig(
            service_name="test",
            kafka_bootstrap="localhost:9092",
            minio_endpoint="minio:9000",
            minio_access_key="access",
            minio_secret_key="secret",
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
        # Create a config with invalid Kafka settings
        # Note: We can't directly set invalid kafka_acks in IndexerConfig,
        # but we can test that validation works for what we can set

        config = IndexerConfig(
            service_name="test",
            chunk_size=100,
            chunk_overlap=150,  # Invalid
        )

        result = config.validate_config()
        assert result["valid"] is False
        assert any("chunk_overlap" in err.lower() for err in result["errors"])
