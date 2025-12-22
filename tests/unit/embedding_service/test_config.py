"""Unit tests for src/embedding_service/config.py.

Tests cover:
- EmbeddingServiceConfig default values
- EmbeddingServiceConfig custom values
- Integration with ServiceConfig base class
"""

import pytest

from src.embedding_service.config import EmbeddingServiceConfig


class TestEmbeddingServiceConfigDefaults:
    """Tests for EmbeddingServiceConfig default values."""

    def test_default_service_name(self):
        """Tests default service name."""
        config = EmbeddingServiceConfig()
        assert config.service_name == "embedding-service"

    def test_default_port(self):
        """Tests default port."""
        config = EmbeddingServiceConfig()
        assert config.port == 50051

    def test_default_enable_reflection(self):
        """Tests default enable_reflection."""
        config = EmbeddingServiceConfig()
        assert config.enable_reflection is True

    def test_default_datasets_config_path(self):
        """Tests default datasets_config_path."""
        config = EmbeddingServiceConfig()
        assert config.datasets_config_path == "config/datasets_config.yaml"


class TestEmbeddingServiceConfigCustomValues:
    """Tests for EmbeddingServiceConfig with custom values."""

    def test_custom_port(self):
        """Tests custom port setting."""
        config = EmbeddingServiceConfig(port=50099)
        assert config.port == 50099

    def test_custom_service_name(self):
        """Tests custom service name."""
        config = EmbeddingServiceConfig(service_name="custom-embedding")
        assert config.service_name == "custom-embedding"

    def test_custom_enable_reflection(self):
        """Tests custom enable_reflection."""
        config = EmbeddingServiceConfig(enable_reflection=False)
        assert config.enable_reflection is False

    def test_custom_datasets_config_path(self):
        """Tests custom datasets_config_path."""
        config = EmbeddingServiceConfig(datasets_config_path="custom/path.yaml")
        assert config.datasets_config_path == "custom/path.yaml"

    def test_all_custom_values(self):
        """Tests setting all custom values."""
        config = EmbeddingServiceConfig(
            service_name="my-embedding-service",
            port=50123,
            enable_reflection=False,
            datasets_config_path="config/custom.yaml",
        )

        assert config.service_name == "my-embedding-service"
        assert config.port == 50123
        assert config.enable_reflection is False
        assert config.datasets_config_path == "config/custom.yaml"


class TestEmbeddingServiceConfigInheritance:
    """Tests for EmbeddingServiceConfig inheritance from ServiceConfig."""

    def test_inherits_from_service_config(self):
        """Config inherits from ServiceConfig base class."""
        from src.common.config import ServiceConfig

        config = EmbeddingServiceConfig()
        assert isinstance(config, ServiceConfig)

    def test_pydantic_validation(self):
        """Pydantic validation works for invalid types."""
        with pytest.raises(Exception):  # ValidationError
            EmbeddingServiceConfig(port="not_a_number")
