"""Base configuration with validation using Pydantic.

Provides utilities for loading configuration from YAML files and environment variables
with validation and helpful error messages.
"""

import os
from pathlib import Path
from typing import Any, TypeVar

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.errors import ConfigurationError

T = TypeVar("T")

# Load .env file at module import time
load_dotenv()


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dictionary containing all configuration values.

    Raises:
        ConfigurationError: If file doesn't exist or contains invalid YAML.
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    try:
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {config_path}: {e}") from e

    if config is None:
        raise ConfigurationError(f"Configuration file is empty: {config_path}")

    if not isinstance(config, dict):
        raise ConfigurationError(f"Configuration must be a YAML mapping, got {type(config).__name__}")

    return config


def get_nested_value(config: dict[str, Any], *keys: str) -> object:
    """Get a nested value from a config dictionary.

    Args:
        config: Configuration dictionary.
        *keys: Sequence of keys to traverse (e.g., "grpc", "timeout").

    Returns:
        The value at the nested path.

    Raises:
        ConfigurationError: If any key in the path is missing.
    """
    current = config
    path = ".".join(keys)

    for key in keys:
        if not isinstance(current, dict):
            raise ConfigurationError(f"Expected dict at '{path}' but got {type(current).__name__}")
        if key not in current:
            raise ConfigurationError(f"Missing required configuration key: '{path}'")
        current = current[key]

    return current


def get_config_value(config: dict[str, Any], *keys: str, env_var: str | None) -> object:
    """Get a config value with optional environment variable override.

    Environment variables take precedence over YAML values.

    Args:
        config: Configuration dictionary.
        *keys: Sequence of keys to traverse in the config dict.
        env_var: Optional environment variable name that can override the YAML value.

    Returns:
        The configuration value (from env var if set, otherwise from YAML).

    Raises:
        ConfigurationError: If the value is not found in either source.
    """
    if env_var:
        env_value = os.getenv(env_var)
        if env_value is not None:
            return env_value

    return get_nested_value(config, *keys)


class BaseConfig(BaseSettings):
    """Base configuration class with environment variable loading.

    Inherits from Pydantic BaseSettings for automatic environment
    variable loading and validation.

    Example:
        class MyServiceConfig(BaseConfig):
            service_name: str
            port: int = 8080
            weaviate_url: str

        config = MyServiceConfig()
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,  # Immutable configs for reproducible evaluation
    )

    @classmethod
    def from_env(cls, env_file: str) -> "BaseConfig":
        """Load configuration from environment file.

        Args:
            env_file: Path to .env file

        Returns:
            Configured instance

        Raises:
            ConfigurationError: If validation fails
        """
        try:
            return cls(_env_file=env_file)
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}") from e

    def validate_config(self) -> dict[str, Any]:
        """Validate the entire configuration object.

        Returns:
            Dictionary with validation results:
            {
                "valid": bool,
                "errors": list[str],
                "warnings": list[str]
            }
        """
        errors: list[str] = []
        warnings: list[str] = []

        try:
            # Pydantic validation happens at instantiation
            # This method can perform additional cross-field validation
            self._validate_cross_fields(errors, warnings)
        except ValidationError as e:
            errors.extend(str(err) for err in e.errors())

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_cross_fields(self, errors: list[str], warnings: list[str]) -> None:
        """Override in subclasses for cross-field validation.

        Args:
            errors: List to append validation errors to
            warnings: List to append validation warnings to
        """
        pass

    def get_config_dict(self) -> dict[str, Any]:
        """Get all configuration as a dictionary.

        Returns:
            Dictionary of all configuration values
        """
        return self.model_dump()


def require_env_file(path: str) -> None:
    """Check that .env file exists, guide user if not.

    Args:
        path: Path to .env file

    Raises:
        ConfigurationError: If .env file doesn't exist
    """
    env_path = Path(path)
    if not env_path.exists():
        example_path = Path(f"{path}.example")
        error_msg = f"Configuration file '{path}' not found."

        if example_path.exists():
            error_msg += "\n\nCopy the example file to get started:"
            error_msg += f"\n  cp {path}.example {path}"
            error_msg += f"\n\nThen edit {path} and add your API keys and configuration."
        else:
            error_msg += f"\n\nCreate {path} with your configuration."

        raise ConfigurationError(error_msg)


def get_env_or_error(key: str) -> str:
    """Get environment variable or raise helpful error.

    Args:
        key: Environment variable name

    Returns:
        Environment variable value

    Raises:
        ConfigurationError: If variable not set
    """
    value = os.getenv(key)
    if value is None:
        raise ConfigurationError(
            f"Required environment variable '{key}' is not set.\nAdd it to your .env file or set it in your environment."
        )
    return value


# Common configuration models


class ServiceConfig(BaseConfig):
    """Common service configuration."""

    service_name: str = Field(..., description="Service name for logging and metrics")
    log_level: str = Field(..., description="Logging level")
    port: int = Field(..., description="Service port")

    # OpenTelemetry tracing configuration
    otlp_endpoint: str | None = None
    environment: str = Field(..., description="Deployment environment (development, staging, production)")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log_level '{v}'. Must be one of: {', '.join(valid_levels)}")
        return v_upper


# Standalone Pydantic models for composition (not BaseSettings)
# These are used as building blocks in service configs


class WeaviateConfig(BaseModel):
    """Weaviate connection configuration.

    This is a standalone Pydantic model used for composition in service configs.
    """

    weaviate_url: str = Field(..., description="Weaviate URL")
    weaviate_timeout_init: int = Field(..., ge=1, description="Weaviate init timeout in seconds")
    weaviate_timeout_query: int = Field(..., ge=1, description="Weaviate query timeout in seconds")
    weaviate_timeout_insert: int = Field(..., ge=1, description="Weaviate insert timeout in seconds")
    weaviate_collection: str = Field(..., description="Weaviate collection name")

    @field_validator("weaviate_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Weaviate URL '{v}'. Must start with http:// or https://")
        return v.rstrip("/")


class RedisConfig(BaseModel):
    """Redis connection configuration.

    This is a standalone Pydantic model used for composition in service configs.
    """

    redis_url: str = Field(..., description="Redis URL")
    cache_ttl: int = Field(..., ge=0, description="Default cache TTL in seconds")
    enable_cache: bool = Field(..., description="Whether caching is enabled")

    @field_validator("redis_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith("redis://"):
            raise ValueError(f"Invalid Redis URL '{v}'. Must start with redis://")
        return v


class KafkaConfig(BaseModel):
    """Kafka connection configuration.

    This is a standalone Pydantic model used for composition in service configs.
    """

    kafka_bootstrap: str = Field(..., description="Kafka bootstrap servers")
    kafka_topic: str = Field(..., description="Kafka topic for document changes")
    kafka_group_id: str | None = None
    kafka_acks: str = Field(..., description="Kafka acknowledgment setting (0, 1, or 'all')")
    kafka_auto_offset_reset: str = Field(..., description="Kafka auto offset reset (earliest/latest)")

    @field_validator("kafka_acks")
    @classmethod
    def validate_acks(cls, v: str) -> str:
        """Validate acks value."""
        valid_acks = ["0", "1", "all"]
        if v not in valid_acks:
            raise ValueError(f"Invalid kafka_acks '{v}'. Must be one of: {', '.join(valid_acks)}")
        return v

    @field_validator("kafka_auto_offset_reset")
    @classmethod
    def validate_auto_offset_reset(cls, v: str) -> str:
        """Validate auto_offset_reset value."""
        valid_values = ["earliest", "latest"]
        if v not in valid_values:
            raise ValueError(f"Invalid kafka_auto_offset_reset '{v}'. Must be one of: {', '.join(valid_values)}")
        return v


class OpenAIConfig(BaseModel):
    """OpenAI API configuration.

    This is a standalone Pydantic model used for composition in service configs.
    Supports both OpenAI API and OpenAI-compatible local servers (LM Studio, etc.).
    """

    openai_api_key: str = Field(..., description="OpenAI API key (any non-empty value for local LLMs)")
    openai_api_base: str | None = None
    openai_model: str = Field(..., description="OpenAI model name")
    openai_max_tokens: int = Field(..., ge=1, le=32000, description="Maximum tokens in response")
    openai_temperature: float = Field(..., ge=0.0, le=2.0, description="Sampling temperature (0.0-2.0)")
    openai_max_retries: int = Field(..., ge=0, description="Maximum retry attempts")
    openai_timeout: int = Field(..., ge=1, description="Request timeout in seconds")

    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key format.

        Note: When using a custom base URL (e.g., LM Studio), any non-empty
        key is accepted since local LLM servers don't require real API keys.
        The actual OpenAI API will reject invalid keys if used.
        """
        if not v:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in your .env file.")
        # For local LLMs and testing, any non-empty key is valid
        # The OpenAI API itself will validate the key format when actually used
        return v

    @field_validator("openai_api_base")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Validate and normalize base URL."""
        if v is None or v == "":
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base URL '{v}'. Must start with http:// or https://")
        return v.rstrip("/")


class MinIOConfig(BaseModel):
    """MinIO storage configuration.

    This is a standalone Pydantic model used for composition in service configs.
    """

    minio_endpoint: str = Field(..., description="MinIO endpoint")
    minio_access_key: str = Field(..., description="MinIO access key")
    minio_secret_key: str = Field(..., description="MinIO secret key")
    minio_bucket: str = Field(..., description="MinIO bucket name")
    minio_secure: bool = Field(..., description="Use HTTPS for MinIO")

    @field_validator("minio_endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate and normalize endpoint format."""
        # Normalize endpoint
        if v.startswith(("http://", "https://")):
            return v.rstrip("/")
        # Assume http:// if no scheme
        return f"http://{v}".rstrip("/")


# YAML/JSON Configuration


class Config:
    """Configuration class for YAML/JSON dataset config files.

    Auto-detects format from file extension and loads the config file.
    Stores config internally as dict.

    Example:
        config = Config("config/ingestion_config.yaml")
        value = config.get_dataset_value("nutritionfacts.org", "chunking", "chunk_size")
    """

    def __init__(self, config_path: str | Path) -> None:
        """Initialize Config and load from file.

        Args:
            config_path: Path to YAML or JSON config file

        Raises:
            ConfigurationError: If file doesn't exist or has invalid format
        """
        self._config_path = Path(config_path)

        if not self._config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        suffix = self._config_path.suffix.lower()
        if suffix == ".json":
            self._data = self._load_from_json()
        elif suffix in [".yaml", ".yml"]:
            self._data = self._load_from_yaml()
        else:
            raise ConfigurationError(f"Unsupported config file format: {suffix}. Must be .json, .yaml, or .yml")

        self._defaults = self._data.get("defaults", {})  # nosemgrep: xrag.no-dict-get-with-default
        self._datasets = self._data.get("datasets", {})  # nosemgrep: xrag.no-dict-get-with-default

    def _load_from_yaml(self) -> dict[str, Any]:
        """Load configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If YAML is invalid
        """
        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {self._config_path}: {e}") from e

        if config_data is None:
            raise ConfigurationError(f"Configuration file is empty: {self._config_path}")

        if not isinstance(config_data, dict):
            raise ConfigurationError(f"Configuration must be a YAML mapping, got {type(config_data).__name__}")

        return config_data

    def _load_from_json(self) -> dict[str, Any]:
        """Load configuration from JSON file.

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If JSON is invalid
        """
        import json

        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {self._config_path}: {e}") from e

        if not isinstance(config_data, dict):
            raise ConfigurationError(f"Configuration must be a JSON object, got {type(config_data).__name__}")

        return config_data

    def get_datasets(self) -> list[str]:
        """Get list of all dataset names."""
        return list(self._datasets.keys())

    def has_dataset(self, dataset_name: str) -> bool:
        """Check if dataset exists."""
        return dataset_name in self._datasets

    def get_dataset_value(self, dataset_name: str, *keys: str, config_slug: str | None = None) -> Any:  # noqa: C901, ANN401  # nosemgrep: xrag.no-default-parameter-values
        """Get a value from dataset config with defaults merging.

        Args:
            dataset_name: Dataset name
            *keys: Nested keys to traverse
            config_slug: Optional config variant slug

        Returns:
            Configuration value

        Raises:
            ConfigurationError: If dataset not found or key path invalid
        """
        if not self.has_dataset(dataset_name):
            available = ", ".join(self.get_datasets()) if self.get_datasets() else "none"
            raise ConfigurationError(f"Dataset '{dataset_name}' not found in {self._config_path}. Available: {available}")

        merged = dict(self._defaults)
        dataset = self._datasets[dataset_name]
        for key, value in dataset.items():
            if key != "configs":
                merged[key] = value  # noqa: PERF403

        if config_slug:
            configs = dataset.get("configs", [])  # nosemgrep: xrag.no-dict-get-with-default
            variant = None
            for cfg in configs:
                if cfg.get("slug") == config_slug:
                    variant = cfg
                    break
            if variant is None:
                available_slugs = [cfg.get("slug") for cfg in configs] if configs else []
                raise ConfigurationError(
                    f"Config slug '{config_slug}' not found for dataset '{dataset_name}'. "
                    f"Available: {', '.join(available_slugs) if available_slugs else 'none'}"
                )
            for key, value in variant.items():
                if key not in ["slug", "description"]:
                    merged[key] = value  # noqa: PERF403

        current = merged
        for key in keys:
            if not isinstance(current, dict):
                path = ".".join(keys)
                raise ConfigurationError(f"Cannot access '{key}' in '{path}' - expected dict, got {type(current).__name__}")
            if key not in current:
                path = ".".join(keys)
                raise ConfigurationError(f"Key '{path}' not found for dataset '{dataset_name}' in {self._config_path}")
            current = current[key]

        return current

    def get_dataset_config(  # nosemgrep: xrag.no-default-parameter-values
        self, dataset_name: str, config_slug: str | None = None
    ) -> dict[str, Any]:
        """Get complete merged configuration for a dataset.

        Args:
            dataset_name: Dataset name
            config_slug: Optional config variant slug

        Returns:
            Complete merged configuration dictionary
        """
        if not self.has_dataset(dataset_name):
            available = ", ".join(self.get_datasets()) if self.get_datasets() else "none"
            raise ConfigurationError(f"Dataset '{dataset_name}' not found in {self._config_path}. Available: {available}")

        merged = dict(self._defaults)
        dataset = self._datasets[dataset_name]
        for key, value in dataset.items():
            if key != "configs":
                merged[key] = value  # noqa: PERF403

        if config_slug:
            configs = dataset.get("configs", [])  # nosemgrep: xrag.no-dict-get-with-default
            variant = None
            for cfg in configs:
                if cfg.get("slug") == config_slug:
                    variant = cfg
                    break
            if variant is None:
                available_slugs = [cfg.get("slug") for cfg in configs] if configs else []
                raise ConfigurationError(
                    f"Config slug '{config_slug}' not found for dataset '{dataset_name}'. "
                    f"Available: {', '.join(available_slugs) if available_slugs else 'none'}"
                )
            for key, value in variant.items():
                if key not in ["slug", "description"]:
                    merged[key] = value  # noqa: PERF403

        return merged
