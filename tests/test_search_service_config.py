"""Tests for Search Service configuration."""

import pytest
from pydantic import ValidationError

from src.search_service.config import SearchServiceConfig


def test_config_defaults() -> None:
    """Test that configuration has sensible defaults."""
    config = SearchServiceConfig()

    assert config.service_name == "search-service"
    assert config.port == 50052
    assert config.weaviate_url == "http://weaviate:8080"
    assert config.embedding_service_addr == "embedding-service:50051"
    assert config.datasets_config_path == "config/datasets_config.yaml"
    assert config.enable_reflection is True


def test_config_custom_values() -> None:
    """Test configuration with custom values."""
    config = SearchServiceConfig(
        service_name="custom-search",
        port=50099,
        weaviate_url="http://custom-weaviate:8080",
        embedding_service_addr="custom-embedding:50051",
        datasets_config_path="custom/config.yaml",
    )

    assert config.service_name == "custom-search"
    assert config.port == 50099
    assert config.weaviate_url == "http://custom-weaviate:8080"
    assert config.embedding_service_addr == "custom-embedding:50051"
    assert config.datasets_config_path == "custom/config.yaml"


def test_config_invalid_weaviate_url() -> None:
    """Test that invalid Weaviate URL fails validation."""
    with pytest.raises(ValidationError, match="Invalid Weaviate URL"):
        SearchServiceConfig(weaviate_url="invalid-url")


# Note: OpenAI config (api_key, model, temperature) is now per-dataset
# in datasets_config.yaml, not in SearchServiceConfig

# Note: Search config (default_top_k, default_mode, hybrid_alpha) is now
# per-dataset in datasets_config.yaml, not in SearchServiceConfig
