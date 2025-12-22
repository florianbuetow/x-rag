"""Configuration for Search Service."""

from pydantic import Field, field_validator

from src.common.config import ServiceConfig


class SearchServiceConfig(ServiceConfig):
    """Search Service configuration.

    Combines all required configuration for the search service including
    Weaviate, Embedding Service, and OpenAI settings.
    """

    # Service settings
    service_name: str = Field(default="search-service", description="Service name")
    port: int = Field(default=50052, description="gRPC port")
    enable_reflection: bool = Field(default=True, description="Enable gRPC reflection for debugging")

    # Weaviate settings
    weaviate_url: str = Field(default="http://weaviate:8080", description="Weaviate URL")
    weaviate_timeout: int = Field(default=30, description="Weaviate request timeout in seconds")

    # Embedding Service settings
    embedding_service_addr: str = Field(
        default="embedding-service:50051",
        description="Embedding Service gRPC address",
    )
    embedding_service_timeout: int = Field(default=30, description="Embedding Service timeout in seconds")

    # Dataset config path
    datasets_config_path: str = Field(
        default="config/datasets_config.yaml",
        description="Path to datasets configuration file",
    )

    @field_validator("weaviate_url")
    @classmethod
    def validate_weaviate_url(cls, v: str) -> str:
        """Validate Weaviate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Weaviate URL '{v}'. Must start with http:// or https://")
        return v.rstrip("/")
