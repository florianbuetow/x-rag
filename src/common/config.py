"""Base configuration with validation using Pydantic.

Provides utilities for loading configuration from YAML files and environment variables
with validation and helpful error messages.
"""

import os
from pathlib import Path
from typing import Any, TypeVar

import yaml
from dotenv import load_dotenv
from pydantic import Field, field_validator
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


def get_config_value(config: dict[str, Any], *keys: str, env_var: str | None = None) -> object:
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
    def from_env(cls, env_file: str = ".env") -> "BaseConfig":
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


def require_env_file(path: str = ".env") -> None:
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


def get_env_or_error(key: str, default: str | None = None) -> str:
    """Get environment variable or raise helpful error.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Environment variable value

    Raises:
        ConfigurationError: If variable not set and no default
    """
    value = os.getenv(key, default)
    if value is None:
        raise ConfigurationError(
            f"Required environment variable '{key}' is not set.\nAdd it to your .env file or set it in your environment."
        )
    return value


# Common configuration models


class ServiceConfig(BaseConfig):
    """Common service configuration."""

    service_name: str = Field(..., description="Service name for logging and metrics")
    log_level: str = Field(default="INFO", description="Logging level")
    port: int = Field(default=8080, description="Service port")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log_level '{v}'. Must be one of: {', '.join(valid_levels)}")
        return v_upper


class WeaviateConfig(BaseConfig):
    """Weaviate connection configuration."""

    weaviate_url: str = Field(default="http://weaviate:8080", description="Weaviate URL")
    weaviate_timeout: int = Field(default=30, description="Request timeout in seconds")

    @field_validator("weaviate_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Weaviate URL '{v}'. Must start with http:// or https://")
        return v.rstrip("/")


class RedisConfig(BaseConfig):
    """Redis connection configuration."""

    redis_url: str = Field(default="redis://redis:6379", description="Redis URL")
    cache_ttl: int = Field(default=3600, description="Default cache TTL in seconds")

    @field_validator("redis_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith("redis://"):
            raise ValueError(f"Invalid Redis URL '{v}'. Must start with redis://")
        return v


class KafkaConfig(BaseConfig):
    """Kafka connection configuration."""

    kafka_bootstrap: str = Field(default="kafka:9092", description="Kafka bootstrap servers")
    kafka_topic: str = Field(default="document-changes", description="Kafka topic for document changes")


class OpenAIConfig(BaseConfig):
    """OpenAI API configuration."""

    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model")
    openai_chat_model: str = Field(default="gpt-4", description="Chat model")

    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key format."""
        if not v or v == "sk-your-key-here":
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in your .env file with your actual API key.")
        if not v.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format. Should start with 'sk-'")
        return v
