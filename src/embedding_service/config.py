"""Configuration for Embedding Service."""

from typing import Literal

from pydantic import Field, ValidationInfo, field_validator

from src.common.config import ServiceConfig
from src.llm.config import EmbeddingConfig, EmbeddingProvider


class EmbeddingServiceConfig(ServiceConfig):
    """Embedding Service configuration.

    Supports multiple embedding providers:
    - hash_based: Deterministic hash-based embeddings (for testing)
    - openai: OpenAI API or OpenAI-compatible embeddings (LM Studio, etc.)
    """

    service_name: str = Field(default="embedding-service", description="Service name")
    port: int = Field(default=50051, description="gRPC port")
    embedding_generator: Literal["hash_based", "openai"] = Field(
        ...,
        description="Embedding generator to use (hash_based or openai). Required - no default.",
    )
    default_model: str = Field(default="hash-small", description="Default embedding model")
    max_batch_size: int = Field(default=100, description="Maximum batch size")
    enable_reflection: bool = Field(default=True, description="Enable gRPC reflection")
    max_workers: int = Field(default=10, description="Max worker threads")

    # OpenAI/Local provider settings
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_api_base: str | None = Field(
        default=None,
        description="OpenAI API base URL for compatible APIs (e.g., LM Studio)",
    )
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_max_retries: int = Field(default=3)
    openai_timeout: int = Field(default=30)

    # Hash-based provider settings
    hash_based_dimension: int = Field(default=1536, description="Default hash-based dimension")

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Validate OpenAI API key if using openai generator.

        Note: When using a custom base URL (e.g., LM Studio), any non-empty
        key is accepted since local LLM servers don't require real API keys.
        """
        generator = info.data.get("embedding_generator")
        if generator == "openai" and not v:
            raise ValueError("OpenAI API key required when using 'openai' generator.")
        return v

    def get_embedding_config(self) -> EmbeddingConfig:
        """Create EmbeddingConfig from service configuration.

        Returns:
            EmbeddingConfig instance for creating embedding generator
        """
        if self.embedding_generator == "hash_based":
            return EmbeddingConfig.for_hash_based(dimension=self.hash_based_dimension)
        elif self.embedding_generator == "openai":
            provider = EmbeddingProvider.LOCAL if self.openai_api_base else EmbeddingProvider.OPENAI
            return EmbeddingConfig(
                provider=provider,
                api_key=self.openai_api_key or "",
                base_url=self.openai_api_base,
                model=self.openai_embedding_model,
                max_retries=self.openai_max_retries,
                timeout=self.openai_timeout,
            )
        else:
            raise ValueError(f"Unknown generator: {self.embedding_generator}")
