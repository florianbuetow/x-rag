"""Configuration for Search UI."""

from pydantic import Field, field_validator

from src.common.config import ServiceConfig


class SearchUIConfig(ServiceConfig):
    """Search UI configuration."""

    service_name: str = Field(...)
    port: int = Field(...)

    # Search Service connection
    search_service_addr: str = Field(
        ...,
        description="Search Service gRPC address",
    )
    search_service_timeout: float = Field(
        ...,
        description="Search Service timeout in seconds",
    )

    # UI settings
    cors_enabled: bool = Field(..., description="Enable CORS for browser access")
    max_query_length: int = Field(..., description="Maximum query length")
    top_k: int = Field(..., description="Number of results")
    mode: str = Field(..., description="Search mode")

    # Dataset config path
    datasets_config_path: str = Field(
        ...,
        description="Path to datasets configuration file",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate search mode is valid."""
        valid_modes = ["vector", "bm25", "hybrid"]
        if v not in valid_modes:
            raise ValueError(f"Invalid mode '{v}'. Must be one of: {', '.join(valid_modes)}")
        return v
