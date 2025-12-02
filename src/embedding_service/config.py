"""Configuration for Embedding Service."""

from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_core import ValidationInfo

from src.common.config import ServiceConfig


class EmbeddingServiceConfig(ServiceConfig):
    """Embedding Service configuration."""

    service_name: str = Field(default="embedding-service", description="Service name")
    port: int = Field(default=50051, description="gRPC port")
    embedding_generator: Literal["hash_based", "openai"] = Field(
        default="hash_based",
        description="Embedding generator to use (hash_based or openai)",
    )
    default_model: str = Field(default="hash-small", description="Default embedding model")
    max_batch_size: int = Field(default=100, description="Maximum batch size")
    enable_reflection: bool = Field(default=True, description="Enable gRPC reflection")
    max_workers: int = Field(default=10, description="Max worker threads")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_max_retries: int = Field(default=3)
    openai_timeout: int = Field(default=30)
    hash_based_dimension: int = Field(default=1536, description="Default hash-based dimension")

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Validate OpenAI API key if using openai generator."""
        generator = info.data.get("embedding_generator", "hash_based")
        if generator == "openai":
            if not v or v == "sk-your-key-here":
                raise ValueError("OpenAI API key required when using 'openai' generator.")
            if not v.startswith("sk-"):
                raise ValueError("Invalid OpenAI API key format.")
        return v
