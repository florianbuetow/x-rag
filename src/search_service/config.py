"""Configuration for Search Service."""

from pydantic import Field, ValidationError, field_validator

from src.common.config import OpenAIConfig, RedisConfig, ServiceConfig, WeaviateConfig
from src.llm.config import LLMConfig, LLMProvider


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
    weaviate_collection: str = Field(default="DocumentChunk", description="Weaviate collection name")

    # Embedding Service settings
    embedding_service_addr: str = Field(
        default="embedding-service:50051",
        description="Embedding Service gRPC address",
    )
    embedding_service_timeout: int = Field(default=30, description="Embedding Service timeout in seconds")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model to use")

    # OpenAI settings
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_api_base: str | None = Field(
        default=None,
        description="OpenAI API base URL for compatible APIs (e.g., LM Studio)",
    )
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

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v: str) -> str:
        """Validate OpenAI API key format.

        Note: When using a custom base URL (e.g., LM Studio), any non-empty
        key is accepted since local LLM servers don't require real API keys.
        """
        if not v:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in your .env file.")
        # Any non-empty key is valid - local LLM servers accept any key
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

    # Getter methods for composed configs

    def get_weaviate_config(self) -> WeaviateConfig:
        """Get Weaviate configuration as a validated model.

        Returns:
            WeaviateConfig instance with validated Weaviate settings
        """
        return WeaviateConfig(
            weaviate_url=self.weaviate_url,
            weaviate_timeout=self.weaviate_timeout,
            weaviate_collection=self.weaviate_collection,
        )

    def get_redis_config(self) -> RedisConfig | None:
        """Get Redis configuration if enabled.

        Returns:
            RedisConfig instance if caching is enabled, None otherwise
        """
        # Check if we have redis_url field (for backward compatibility)
        redis_url = getattr(self, "redis_url", None)
        enable_cache = getattr(self, "enable_cache", True)
        cache_ttl = getattr(self, "cache_ttl", 3600)

        if not enable_cache or not redis_url:
            return None

        return RedisConfig(
            redis_url=redis_url,
            cache_ttl=cache_ttl,
            enable_cache=enable_cache,
        )

    def get_openai_config(self) -> OpenAIConfig:
        """Get OpenAI configuration as a validated model.

        Returns:
            OpenAIConfig instance with validated OpenAI settings
        """
        return OpenAIConfig(
            openai_api_key=self.openai_api_key,
            openai_api_base=self.openai_api_base,
            openai_model=self.openai_model,
            openai_max_tokens=self.openai_max_tokens,
            openai_temperature=self.openai_temperature,
            openai_max_retries=self.openai_max_retries,
            openai_timeout=self.openai_timeout,
        )

    def get_llm_config(self) -> LLMConfig:
        """Create LLMConfig from service configuration.

        Automatically detects provider type based on base_url presence.
        Uses OpenAI config internally for consistency.

        Returns:
            LLMConfig instance for creating LLM client
        """
        openai_config = self.get_openai_config()
        provider = LLMProvider.LOCAL if openai_config.openai_api_base else LLMProvider.OPENAI

        return LLMConfig(
            provider=provider,
            api_key=openai_config.openai_api_key,
            base_url=openai_config.openai_api_base,
            model=openai_config.openai_model,
            max_tokens=openai_config.openai_max_tokens,
            temperature=openai_config.openai_temperature,
            max_retries=openai_config.openai_max_retries,
            timeout=openai_config.openai_timeout,
        )

    def _validate_cross_fields(self, errors: list[str], warnings: list[str]) -> None:
        """Validate cross-field dependencies and composed configs.

        Args:
            errors: List to append validation errors to
            warnings: List to append validation warnings to
        """
        # Validate composed configs
        try:
            self.get_weaviate_config()
        except ValidationError as e:
            errors.extend(f"Weaviate config: {err}" for err in e.errors())

        try:
            self.get_openai_config()
        except ValidationError as e:
            errors.extend(f"OpenAI config: {err}" for err in e.errors())

        # Validate Redis config if cache is enabled
        redis_url = getattr(self, "redis_url", None)
        enable_cache = getattr(self, "enable_cache", True)
        if enable_cache and redis_url:
            try:
                redis_config = self.get_redis_config()
                if redis_config is None:
                    errors.append("Redis config is None but cache is enabled")
            except ValidationError as e:
                errors.extend(f"Redis config: {err}" for err in e.errors())
        elif enable_cache and not redis_url:
            warnings.append("Cache is enabled but redis_url is not set")
