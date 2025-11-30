"""Configuration for Embedding Service."""

from pydantic import Field

from src.common.config import BaseConfig, ServiceConfig, OpenAIConfig


class EmbeddingServiceConfig(ServiceConfig, OpenAIConfig):
    """Embedding Service configuration.

    Combines common service config with OpenAI-specific settings.
    """

    service_name: str = Field(default="embedding-service", description="Service name")
    port: int = Field(default=50051, description="gRPC port")

    # Embedding-specific settings
    default_model: str = Field(
        default="text-embedding-3-small",
        description="Default embedding model",
    )
    max_batch_size: int = Field(
        default=100,
        description="Maximum number of texts to embed in a single batch",
    )
    enable_reflection: bool = Field(
        default=True,
        description="Enable gRPC server reflection for debugging",
    )

    # Performance settings
    max_workers: int = Field(
        default=10,
        description="Maximum number of worker threads for gRPC server",
    )
