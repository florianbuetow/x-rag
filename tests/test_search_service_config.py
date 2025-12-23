"""Tests for Search Service configuration."""

import pytest
from pydantic import ValidationError

from src.search_service.config import SearchServiceConfig


def test_config_defaults() -> None:
    """Test that SearchServiceConfig requires all fields."""
    # All fields are required - no defaults
    with pytest.raises(ValidationError, match="Field required"):
        SearchServiceConfig()


def test_config_custom_values() -> None:
    """Test configuration with custom values."""
    config = SearchServiceConfig(
        service_name="custom-search",
        log_level="DEBUG",
        port=50099,
        environment="production",
        weaviate_url="http://custom-weaviate:8080",
        embedding_service_addr="custom-embedding:50051",
        embedding_service_timeout=60,
        datasets_config_path="custom/config.yaml",
        enable_reflection=False,
    )

    assert config.service_name == "custom-search"
    assert config.port == 50099
    assert config.weaviate_url == "http://custom-weaviate:8080"
    assert config.embedding_service_addr == "custom-embedding:50051"
    assert config.datasets_config_path == "custom/config.yaml"


def test_config_invalid_weaviate_url() -> None:
    """Test that invalid Weaviate URL fails validation."""
    with pytest.raises(ValidationError, match="Invalid Weaviate URL"):
        SearchServiceConfig(
            service_name="search-service",
            log_level="INFO",
            port=50052,
            environment="test",
            weaviate_url="invalid-url",
            embedding_service_addr="embedding-service:50051",
            embedding_service_timeout=30,
            datasets_config_path="config/datasets_config.yaml",
            enable_reflection=True,
        )


# Note: OpenAI config (api_key, model, temperature) is now per-dataset
# in datasets_config.yaml, not in SearchServiceConfig

# Note: Search config (top_k, mode, hybrid_alpha) is now
# per-dataset in datasets_config.yaml, not in SearchServiceConfig
