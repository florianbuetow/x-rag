"""Configuration for Embedding Service."""

from pydantic import Field

from src.common.config import ServiceConfig


class EmbeddingServiceConfig(ServiceConfig):
    """Embedding Service configuration.

    Namespace-aware service that loads embedding model configurations
    from datasets_config.yaml based on the namespace parameter in requests.

    Infrastructure settings only - embedding provider, model, and other
    dataset-specific settings are now configured per-namespace in datasets_config.yaml.
    """

    service_name: str = Field(..., description="Service name")
    port: int = Field(..., description="gRPC port")
    enable_reflection: bool = Field(..., description="Enable gRPC reflection")

    # Dataset configuration path
    datasets_config_path: str = Field(
        ...,
        description="Path to datasets configuration file",
    )
