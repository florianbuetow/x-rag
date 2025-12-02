"""Configuration for Search Service."""

from pydantic import Field, field_validator

from src.common.config import ServiceConfig


class SearchServiceConfig(ServiceConfig):
    """Search Service configuration.

    Combines all required configuration for the search service including
    Weaviate, Redis, Embedding Service, and OpenAI settings.
    """

    # Service settings
    service_name: str = Field(default="search-service", description="Service name")
    port: int = Field(default=50052, description="gRPC port")
    enable_reflection: bool = Field(default=True, description="Enable gRPC reflection for debugging")

    # Weaviate settings
    weaviate_url: str = Field(default="http://weaviate:8080", description="Weaviate URL")
    weaviate_timeout: int = Field(default=30, description="Weaviate request timeout in seconds")
    weaviate_collection: str = Field(default="DocumentChunk", description="Weaviate collection name")

    # Redis settings
    redis_url: str = Field(default="redis://redis:6379", description="Redis URL")
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    enable_cache: bool = Field(default=True, description="Enable query caching")

    # Embedding Service settings
    embedding_service_addr: str = Field(
        default="embedding-service:50051",
        description="Embedding Service gRPC address",
    )
    embedding_service_timeout: int = Field(default=30, description="Embedding Service timeout in seconds")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model to use")

    # OpenAI settings
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model for answer generation")
    openai_max_tokens: int = Field(default=500, description="Maximum tokens in OpenAI response")
    openai_temperature: float = Field(default=0.7, description="OpenAI temperature (0.0-2.0)")
    openai_max_retries: int = Field(default=3, description="Maximum retries for OpenAI API calls")
    openai_timeout: int = Field(default=60, description="OpenAI API timeout in seconds")

    # Search settings
    default_top_k: int = Field(default=10, description="Default number of documents to retrieve")
    default_mode: str = Field(default="hybrid", description="Default search mode (vector, bm25, hybrid)")
    hybrid_alpha: float = Field(default=0.5, description="Default alpha for hybrid search (0=BM25, 1=vector)")
    max_context_length: int = Field(default=4000, description="Maximum context length in characters")

    @field_validator("weaviate_url")
    @classmethod
    def validate_weaviate_url(cls, v: str) -> str:
        """Validate Weaviate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Weaviate URL '{v}'. Must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith("redis://"):
            raise ValueError(f"Invalid Redis URL '{v}'. Must start with redis://")
        return v

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v: str) -> str:
        """Validate OpenAI API key format."""
        if not v:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in your .env file with your actual API key.")
        # Allow placeholder key for development/testing
        # In production, this should be a real key
        if v == "sk-your-key-here":
            import logging

            logging.warning("Using placeholder OpenAI API key - LLM functionality will fail")
            return v
        if not v.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format. Should start with 'sk-'")
        return v

    @field_validator("openai_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v

    @field_validator("default_mode")
    @classmethod
    def validate_search_mode(cls, v: str) -> str:
        """Validate search mode is valid."""
        valid_modes = ["vector", "bm25", "hybrid"]
        if v not in valid_modes:
            raise ValueError(f"Invalid search mode '{v}'. Must be one of: {', '.join(valid_modes)}")
        return v

    @field_validator("hybrid_alpha")
    @classmethod
    def validate_alpha(cls, v: float) -> float:
        """Validate alpha is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Hybrid alpha must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("default_top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """Validate top_k is positive."""
        if v <= 0:
            raise ValueError(f"default_top_k must be positive, got {v}")
        if v > 100:
            raise ValueError(f"default_top_k too large (max 100), got {v}")
        return v
