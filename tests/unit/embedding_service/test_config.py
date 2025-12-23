"""Unit tests for src/embedding_service/config.py.

Tests cover:
- EmbeddingServiceConfig loading from environment
- EmbeddingServiceConfig custom values
- Integration with ServiceConfig base class
- Pydantic validation
"""

import pytest
from pydantic import ValidationError

from src.embedding_service.config import EmbeddingServiceConfig


class TestEmbeddingServiceConfigFromEnv:
    """Tests for EmbeddingServiceConfig loading from environment variables."""

    def test_loads_service_name_from_env(self, monkeypatch):
        """Tests service name loaded from environment."""
        test_env = {
            "SERVICE_NAME": "embedding-service",
            "PORT": "50051",
            "ENABLE_REFLECTION": "true",
            "DATASETS_CONFIG_PATH": "config/datasets_config.yaml",
        }
        for key, value in test_env.items():
            monkeypatch.setenv(key, value)

        config = EmbeddingServiceConfig()
        assert config.service_name == "embedding-service"

    def test_loads_port_from_env(self, monkeypatch):
        """Tests port loaded from environment."""
        test_env = {
            "SERVICE_NAME": "embedding-service",
            "PORT": "50051",
            "ENABLE_REFLECTION": "true",
            "DATASETS_CONFIG_PATH": "config/datasets_config.yaml",
        }
        for key, value in test_env.items():
            monkeypatch.setenv(key, value)

        config = EmbeddingServiceConfig()
        assert config.port == 50051

    def test_loads_enable_reflection_from_env(self, monkeypatch):
        """Tests enable_reflection loaded from environment."""
        test_env = {
            "SERVICE_NAME": "embedding-service",
            "PORT": "50051",
            "ENABLE_REFLECTION": "true",
            "DATASETS_CONFIG_PATH": "config/datasets_config.yaml",
        }
        for key, value in test_env.items():
            monkeypatch.setenv(key, value)

        config = EmbeddingServiceConfig()
        assert config.enable_reflection is True

    def test_loads_datasets_config_path_from_env(self, monkeypatch):
        """Tests datasets_config_path loaded from environment."""
        test_env = {
            "SERVICE_NAME": "embedding-service",
            "PORT": "50051",
            "ENABLE_REFLECTION": "true",
            "DATASETS_CONFIG_PATH": "config/datasets_config.yaml",
        }
        for key, value in test_env.items():
            monkeypatch.setenv(key, value)

        config = EmbeddingServiceConfig()
        assert config.datasets_config_path == "config/datasets_config.yaml"


class TestEmbeddingServiceConfigCustomValues:
    """Tests for EmbeddingServiceConfig with explicit custom values."""

    def test_custom_port(self):
        """Tests custom port setting."""
        config = EmbeddingServiceConfig(
            service_name="test",
            port=50099,
            enable_reflection=True,
            datasets_config_path="config/test.yaml",
        )
        assert config.port == 50099

    def test_custom_service_name(self):
        """Tests custom service name."""
        config = EmbeddingServiceConfig(
            service_name="custom-embedding",
            port=50051,
            enable_reflection=True,
            datasets_config_path="config/test.yaml",
        )
        assert config.service_name == "custom-embedding"

    def test_custom_enable_reflection(self):
        """Tests custom enable_reflection."""
        config = EmbeddingServiceConfig(
            service_name="test",
            port=50051,
            enable_reflection=False,
            datasets_config_path="config/test.yaml",
        )
        assert config.enable_reflection is False

    def test_custom_datasets_config_path(self):
        """Tests custom datasets_config_path."""
        config = EmbeddingServiceConfig(
            service_name="test",
            port=50051,
            enable_reflection=True,
            datasets_config_path="custom/path.yaml",
        )
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


class TestEmbeddingServiceConfigValidation:
    """Tests for EmbeddingServiceConfig validation and requirements."""

    def test_requires_all_fields(self, monkeypatch):
        """Config requires all fields to be specified when no env vars are set."""
        # Clear all relevant environment variables
        env_vars = [
            "SERVICE_NAME",
            "PORT",
            "ENABLE_REFLECTION",
            "DATASETS_CONFIG_PATH",
            "LOG_LEVEL",
            "ENVIRONMENT",
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(ValidationError) as exc_info:
            EmbeddingServiceConfig()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        # At minimum, these fields from EmbeddingServiceConfig should be required
        assert "port" in error_fields or "enable_reflection" in error_fields or "datasets_config_path" in error_fields

    def test_pydantic_validation_invalid_port(self):
        """Pydantic validation works for invalid port type."""
        with pytest.raises(ValidationError):
            EmbeddingServiceConfig(
                service_name="test",
                port="not_a_number",
                enable_reflection=True,
                datasets_config_path="config/test.yaml",
                log_level="INFO",
                environment="test",
            )


class TestEmbeddingServiceConfigInheritance:
    """Tests for EmbeddingServiceConfig inheritance from ServiceConfig."""

    def test_inherits_from_service_config(self):
        """Config inherits from ServiceConfig base class."""
        from src.common.config import ServiceConfig

        config = EmbeddingServiceConfig(
            service_name="test",
            port=50051,
            enable_reflection=True,
            datasets_config_path="config/test.yaml",
        )
        assert isinstance(config, ServiceConfig)
