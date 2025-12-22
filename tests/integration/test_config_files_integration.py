"""Integration tests for verifying YAML config files can be loaded and validated.

These tests verify that the YAML configuration files in config/apps/ can be
loaded and used to create valid service config instances.
"""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from src.common.config import load_yaml_config
from src.embedding_service.config import EmbeddingServiceConfig
from src.indexer.config import IndexerConfig
from src.ingestion_api.config import IngestionAPIConfig
from src.search_service.config import SearchServiceConfig
from src.search_ui.config import SearchUIConfig


def load_app_config_yaml(service_name: str) -> dict:
    """Load YAML config file for a service.

    Args:
        service_name: Name of the service (e.g., "indexer", "search-service")

    Returns:
        Dictionary containing the YAML config
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "apps" / f"{service_name}.yaml"
    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")
    return load_yaml_config(config_path)


def yaml_to_env_vars(yaml_config: dict, prefix: str = "") -> dict[str, str]:
    """Convert YAML config structure to flat environment variable dictionary.

    Args:
        yaml_config: Nested dictionary from YAML
        prefix: Prefix for environment variable names

    Returns:
        Dictionary mapping env var names to string values
    """
    env_vars: dict[str, str] = {}

    def flatten_dict(d: dict, prefix: str) -> None:
        for key, value in d.items():
            env_key = f"{prefix}_{key}".upper() if prefix else key.upper()
            if isinstance(value, dict):
                flatten_dict(value, env_key)
            else:
                # Convert value to string (env vars are strings)
                env_vars[env_key] = str(value)

    flatten_dict(yaml_config, prefix)
    return env_vars


class TestIndexerConfigFileIntegration:
    """Test IndexerConfig can be created from YAML config file."""

    def test_indexer_yaml_file_exists(self):
        """Test that indexer.yaml config file exists."""
        config_path = Path(__file__).parent.parent.parent / "config" / "apps" / "indexer.yaml"
        assert config_path.exists(), f"Config file not found: {config_path}"

    def test_indexer_yaml_file_valid(self):
        """Test that indexer.yaml is valid YAML."""
        yaml_config = load_app_config_yaml("indexer")
        assert isinstance(yaml_config, dict)
        assert "service" in yaml_config
        assert "kafka" in yaml_config

    def test_indexer_config_from_yaml_values(self):
        """Test IndexerConfig can be created with values from YAML file."""
        yaml_config = load_app_config_yaml("indexer")

        # Extract values from YAML structure
        service_config = yaml_config.get("service", {})
        kafka_config = yaml_config.get("kafka", {})
        minio_config = yaml_config.get("minio", {})
        weaviate_config = yaml_config.get("weaviate", {})

        # Create IndexerConfig with YAML values
        config = IndexerConfig(
            service_name=service_config.get("name", "indexer"),
            kafka_bootstrap=kafka_config.get("bootstrap", "kafka:9092"),
            kafka_topic=kafka_config.get("topic", "document-changes"),
            kafka_group_id=kafka_config.get("group_id", "indexer-group"),
            kafka_auto_offset_reset=kafka_config.get("auto_offset_reset", "earliest"),
            minio_endpoint=minio_config.get("endpoint", "minio:9000"),
            minio_bucket=minio_config.get("bucket", "documents"),
            minio_secure=minio_config.get("secure", False),
            weaviate_url=weaviate_config.get("url", "http://weaviate:8080"),
            weaviate_class=weaviate_config.get("collection", "DocumentChunk"),
        )

        # Verify config is valid
        assert config.service_name == service_config.get("name", "indexer")
        validation_result = config.validate_config()
        assert validation_result["valid"] is True

        # Verify getters work
        kafka_config_obj = config.get_kafka_config()
        assert kafka_config_obj.kafka_bootstrap == kafka_config.get("bootstrap", "kafka:9092")

        minio_config_obj = config.get_minio_config()
        assert minio_config_obj.minio_bucket == minio_config.get("bucket", "documents")

        weaviate_config_obj = config.get_weaviate_config()
        assert weaviate_config_obj.weaviate_url == weaviate_config.get("url", "http://weaviate:8080").rstrip("/")


class TestIngestionAPIConfigFileIntegration:
    """Test IngestionAPIConfig can be created from YAML config file."""

    def test_ingestion_api_yaml_file_exists(self):
        """Test that ingestion-api.yaml config file exists."""
        config_path = Path(__file__).parent.parent.parent / "config" / "apps" / "ingestion-api.yaml"
        assert config_path.exists(), f"Config file not found: {config_path}"

    def test_ingestion_api_yaml_file_valid(self):
        """Test that ingestion-api.yaml is valid YAML."""
        yaml_config = load_app_config_yaml("ingestion-api")
        assert isinstance(yaml_config, dict)
        assert "service" in yaml_config
        assert "kafka" in yaml_config
        assert "minio" in yaml_config

    def test_ingestion_api_config_from_yaml_values(self):
        """Test IngestionAPIConfig can be created with values from YAML file."""
        yaml_config = load_app_config_yaml("ingestion-api")

        service_config = yaml_config.get("service", {})
        kafka_config = yaml_config.get("kafka", {})
        minio_config = yaml_config.get("minio", {})
        api_config = yaml_config.get("api", {})

        # Convert kafka_acks to string if it's an int (YAML may load it as int)
        kafka_acks = kafka_config.get("acks", "1")
        if isinstance(kafka_acks, int):
            kafka_acks = str(kafka_acks)

        config = IngestionAPIConfig(
            service_name=service_config.get("name", "ingestion-api"),
            port=service_config.get("port", 8082),
            kafka_bootstrap=kafka_config.get("bootstrap", "kafka:9092"),
            kafka_topic=kafka_config.get("topic", "document-changes"),
            kafka_acks=kafka_acks,
            minio_endpoint=minio_config.get("endpoint", "minio:9000"),
            minio_bucket=minio_config.get("bucket", "documents"),
            minio_secure=minio_config.get("secure", False),
            max_content_length=api_config.get("max_content_length", 10_485_760),
            cors_enabled=api_config.get("cors_enabled", True),
        )

        # Verify config is valid
        validation_result = config.validate_config()
        assert validation_result["valid"] is True

        # Verify getters work
        kafka_config_obj = config.get_kafka_config()
        assert kafka_config_obj.kafka_bootstrap == kafka_config.get("bootstrap", "kafka:9092")

        minio_config_obj = config.get_minio_config()
        assert minio_config_obj.minio_bucket == minio_config.get("bucket", "documents")


class TestSearchServiceConfigFileIntegration:
    """Test SearchServiceConfig can be created from YAML config file."""

    def test_search_service_yaml_file_exists(self):
        """Test that search-service.yaml config file exists."""
        config_path = Path(__file__).parent.parent.parent / "config" / "apps" / "search-service.yaml"
        assert config_path.exists(), f"Config file not found: {config_path}"

    def test_search_service_yaml_file_valid(self):
        """Test that search-service.yaml is valid YAML."""
        yaml_config = load_app_config_yaml("search-service")
        assert isinstance(yaml_config, dict)
        assert "service" in yaml_config
        assert "weaviate" in yaml_config
        assert "openai" in yaml_config

    def test_search_service_config_from_yaml_values(self, monkeypatch):
        """Test SearchServiceConfig can be created with values from YAML file."""
        yaml_config = load_app_config_yaml("search-service")

        service_config = yaml_config.get("service", {})
        weaviate_config = yaml_config.get("weaviate", {})
        openai_config = yaml_config.get("openai", {})
        search_config = yaml_config.get("search", {})

        # Set required OpenAI API key (required field)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-from-yaml")

        config = SearchServiceConfig(
            service_name=service_config.get("name", "search-service"),
            port=service_config.get("port", 50052),
            weaviate_url=weaviate_config.get("url", "http://weaviate:8080"),
            weaviate_timeout=weaviate_config.get("timeout", 30),
            weaviate_collection=weaviate_config.get("collection", "DocumentChunk"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "sk-test-key"),
            openai_api_base=openai_config.get("api_base"),
            openai_model=openai_config.get("model", "gpt-4o-mini"),
            openai_max_tokens=openai_config.get("max_tokens", 500),
            openai_temperature=openai_config.get("temperature", 0.7),
            openai_max_retries=openai_config.get("max_retries", 3),
            openai_timeout=openai_config.get("timeout", 60),
            default_top_k=search_config.get("default_top_k", 10),
            default_mode=search_config.get("default_mode", "hybrid"),
            hybrid_alpha=search_config.get("hybrid_alpha", 0.5),
            max_context_length=search_config.get("max_context_length", 4000),
        )

        # Verify config is valid
        validation_result = config.validate_config()
        assert validation_result["valid"] is True

        # Verify getters work
        weaviate_config_obj = config.get_weaviate_config()
        assert weaviate_config_obj.weaviate_url == weaviate_config.get("url", "http://weaviate:8080").rstrip("/")

        openai_config_obj = config.get_openai_config()
        assert openai_config_obj.openai_model == openai_config.get("model", "gpt-4o-mini")


class TestEmbeddingServiceConfigFileIntegration:
    """Test EmbeddingServiceConfig can be created from YAML config file."""

    def test_embedding_service_yaml_file_exists(self):
        """Test that embedding-service.yaml config file exists."""
        config_path = Path(__file__).parent.parent.parent / "config" / "apps" / "embedding-service.yaml"
        assert config_path.exists(), f"Config file not found: {config_path}"

    def test_embedding_service_yaml_file_valid(self):
        """Test that embedding-service.yaml is valid YAML."""
        yaml_config = load_app_config_yaml("embedding-service")
        assert isinstance(yaml_config, dict)
        assert "service" in yaml_config

    def test_embedding_service_config_from_yaml_values(self):
        """Test EmbeddingServiceConfig can be created with values from YAML file."""
        yaml_config = load_app_config_yaml("embedding-service")

        service_config = yaml_config.get("service", {})
        generator_config = yaml_config.get("generator", {})

        config = EmbeddingServiceConfig(
            service_name=service_config.get("name", "embedding-service"),
            port=service_config.get("port", 50051),
            embedding_generator=generator_config.get("type", "hash_based"),
            default_model=generator_config.get("default_model", "hash-small"),
            max_batch_size=generator_config.get("max_batch_size", 100),
        )

        # Verify config is valid
        assert config.service_name == service_config.get("name", "embedding-service")
        assert config.embedding_generator == generator_config.get("type", "hash_based")


class TestSearchUIConfigFileIntegration:
    """Test SearchUIConfig can be created from YAML config file."""

    def test_search_ui_yaml_file_exists(self):
        """Test that search-ui.yaml config file exists."""
        config_path = Path(__file__).parent.parent.parent / "config" / "apps" / "search-ui.yaml"
        assert config_path.exists(), f"Config file not found: {config_path}"

    def test_search_ui_yaml_file_valid(self):
        """Test that search-ui.yaml is valid YAML."""
        yaml_config = load_app_config_yaml("search-ui")
        assert isinstance(yaml_config, dict)
        assert "service" in yaml_config

    def test_search_ui_config_from_yaml_values(self):
        """Test SearchUIConfig can be created with values from YAML file."""
        yaml_config = load_app_config_yaml("search-ui")

        service_config = yaml_config.get("service", {})
        search_config = yaml_config.get("search", {})

        config = SearchUIConfig(
            service_name=service_config.get("name", "search-ui"),
            port=service_config.get("port", 8080),
            search_service_addr=search_config.get("service_addr", "search-service:50052"),
            search_service_timeout=search_config.get("service_timeout", 30.0),
            default_top_k=search_config.get("default_top_k", 5),
            default_mode=search_config.get("default_mode", "hybrid"),
        )

        # Verify config is valid
        validation_result = config.validate_config()
        assert validation_result["valid"] is True


class TestAllConfigFilesIntegration:
    """Test that all config files can be loaded and are valid."""

    def test_all_config_files_exist(self):
        """Test that all expected config files exist."""
        config_dir = Path(__file__).parent.parent.parent / "config" / "apps"
        expected_files = [
            "indexer.yaml",
            "ingestion-api.yaml",
            "search-service.yaml",
            "embedding-service.yaml",
            "search-ui.yaml",
        ]

        for filename in expected_files:
            config_path = config_dir / filename
            assert config_path.exists(), f"Config file not found: {config_path}"

    def test_all_config_files_are_valid_yaml(self):
        """Test that all config files are valid YAML."""
        config_dir = Path(__file__).parent.parent.parent / "config" / "apps"
        yaml_files = list(config_dir.glob("*.yaml"))

        assert len(yaml_files) > 0, "No YAML config files found"

        for yaml_file in yaml_files:
            try:
                config = load_yaml_config(yaml_file)
                assert isinstance(config, dict), f"{yaml_file.name} is not a valid YAML dictionary"
                assert "service" in config, f"{yaml_file.name} missing 'service' section"
            except Exception as e:
                pytest.fail(f"Failed to load {yaml_file.name}: {e}")


class TestEnvFileIntegration:
    """Test that .env file contains all keys from .env.example with values."""

    def test_env_example_file_exists(self):
        """Test that .env.example file exists."""
        env_example_path = Path(__file__).parent.parent.parent / ".env.example"
        assert env_example_path.exists(), f".env.example file not found: {env_example_path}"

    def test_env_file_exists(self):
        """Test that .env file exists."""
        env_path = Path(__file__).parent.parent.parent / ".env"
        if not env_path.exists():
            pytest.skip(".env file not found - this is expected in CI environments")

    def test_env_contains_all_example_keys(self):
        """Test that .env and .env.example contain the exact same keys."""
        project_root = Path(__file__).parent.parent.parent
        env_example_path = project_root / ".env.example"
        env_path = project_root / ".env"

        # Skip if .env doesn't exist (CI environments)
        if not env_path.exists():
            pytest.skip(".env file not found - this is expected in CI environments")

        # Load both files using dotenv
        env_example = dotenv_values(env_example_path)
        env_actual = dotenv_values(env_path)

        # Filter out comment-only lines and empty keys
        env_example_keys = {k for k, v in env_example.items() if k and v is not None}
        env_actual_keys = set(env_actual.keys())

        # Check for keys missing from .env (critical config missing)
        missing_from_env = env_example_keys - env_actual_keys

        # Check for keys in .env but not in .env.example (undocumented config)
        missing_from_example = env_actual_keys - env_example_keys

        # Build error message
        error_parts = []

        if missing_from_env:
            error_parts.append(
                "❌ CRITICAL: The following keys from .env.example are missing from .env:\n"
                + "\n".join([f"  - {key}" for key in sorted(missing_from_env)])
                + "\n\nThese are required configuration keys. Please add them to your .env file."
            )

        if missing_from_example:
            error_parts.append(
                "⚠️  DOCUMENTATION: The following keys exist in .env but are not documented in .env.example:\n"
                + "\n".join([f"  - {key}" for key in sorted(missing_from_example)])
                + "\n\nPlease add these keys to .env.example to keep documentation up to date."
            )

        if error_parts:
            pytest.fail("\n\n".join(error_parts))

    def test_env_keys_have_values(self):
        """Test that all keys from .env.example are set to non-empty values in .env."""
        project_root = Path(__file__).parent.parent.parent
        env_example_path = project_root / ".env.example"
        env_path = project_root / ".env"

        # Skip if .env doesn't exist (CI environments)
        if not env_path.exists():
            pytest.skip(".env file not found - this is expected in CI environments")

        # Load both files using dotenv
        env_example = dotenv_values(env_example_path)
        env_actual = dotenv_values(env_path)

        # Filter out comment-only lines and empty keys from example
        env_example_keys = {k for k, v in env_example.items() if k and v is not None}

        # Check for keys that are present but have no value
        unset_keys = [key for key in env_example_keys if key not in env_actual or not env_actual[key] or env_actual[key].strip() == ""]

        # Build error message
        if unset_keys:
            pytest.fail(
                "❌ CRITICAL: The following keys from .env.example are not set to a value in .env:\n"
                + "\n".join([f"  - {key}" for key in sorted(unset_keys)])
                + "\n\nPlease set these environment variables to actual values in your .env file."
            )
