"""Configuration for Search UI."""

from pydantic import Field, field_validator

from src.common.config import ServiceConfig


class SearchUIConfig(ServiceConfig):
    """Search UI configuration."""

    service_name: str = Field(default="search-ui")
    port: int = Field(default=8080)

    # Search Service connection
    search_service_addr: str = Field(
        default="search-service:50052",
        description="Search Service gRPC address",
    )
    search_service_timeout: float = Field(
        default=30.0,
        description="Search Service timeout in seconds",
    )

    # UI settings
    cors_enabled: bool = Field(default=True, description="Enable CORS for browser access")
    max_query_length: int = Field(default=1000, description="Maximum query length")
    default_top_k: int = Field(default=5, description="Default number of results")
    default_mode: str = Field(default="hybrid", description="Default search mode")

    @field_validator("default_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate search mode is valid."""
        valid_modes = ["vector", "bm25", "hybrid"]
        if v not in valid_modes:
            raise ValueError(f"Invalid mode '{v}'. Must be one of: {', '.join(valid_modes)}")
        return v
