"""LLM provider configuration.

Supports multiple LLM backends:
- OpenAI API
- Local LLMs via OpenAI-compatible APIs (LM Studio, Ollama, vLLM, etc.)
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    LOCAL = "local"  # OpenAI-compatible local servers (LM Studio, Ollama, etc.)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    LOCAL = "local"  # OpenAI-compatible local servers (LM Studio, Ollama, etc.)
    HASH_BASED = "hash_based"  # Deterministic hash-based (for testing)


class LLMConfig(BaseModel):
    """Configuration for an LLM connection.

    Supports both OpenAI API and OpenAI-compatible local servers.
    """

    provider: LLMProvider = Field(
        ...,
        description="LLM provider type. Required - no default.",
    )
    api_key: str = Field(
        ...,
        description="API key (any non-empty value for local LLMs)",
    )
    base_url: str | None = None
    model: str = Field(
        ...,
        description="Model name/ID",
    )
    max_tokens: int = Field(
        ...,
        description="Maximum tokens in response",
    )
    temperature: float = Field(
        ...,
        description="Sampling temperature (0.0-2.0)",
    )
    max_retries: int = Field(
        ...,
        description="Maximum retry attempts",
    )
    timeout: int = Field(
        ...,
        description="Request timeout in seconds",
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key is not empty."""
        if not v:
            raise ValueError("API key cannot be empty")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Validate and normalize base URL."""
        if v is None or v == "":
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base URL '{v}'. Must start with http:// or https://")
        return v.rstrip("/")

    @classmethod
    def for_openai(
        cls,
        api_key: str,
        model: str,
        max_tokens: int,
        temperature: float,
        max_retries: int,
        timeout: int,
        **kwargs: object,
    ) -> "LLMConfig":
        """Create config for OpenAI API.

        All parameters required. For namespace-based config with defaults,
        use DatasetsConfigLoader.get_dataset_config(namespace).llm.to_llm_config()

        Args:
            api_key: OpenAI API key (required)
            model: Model name (required, e.g., 'gpt-4')
            max_tokens: Maximum tokens in response (required)
            temperature: Sampling temperature 0.0-2.0 (required)
            max_retries: Maximum retry attempts (required)
            timeout: Request timeout in seconds (required)
            **kwargs: Additional config overrides
        """
        return cls(
            provider=LLMProvider.OPENAI,
            api_key=api_key,
            base_url=None,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            **kwargs,
        )

    @classmethod
    def for_local(
        cls,
        base_url: str,
        model: str,
        api_key: str,
        max_tokens: int,
        temperature: float,
        max_retries: int,
        timeout: int,
        **kwargs: object,
    ) -> "LLMConfig":
        """Create config for local LLM (LM Studio, Ollama, etc.).

        All parameters required. For namespace-based config with defaults,
        use DatasetsConfigLoader.get_dataset_config(namespace).llm.to_llm_config()

        Args:
            base_url: Base URL for the local LLM server (required)
            model: Model name/ID (required)
            api_key: API key (required - use "local" for servers that don't validate)
            max_tokens: Maximum tokens in response (required)
            temperature: Sampling temperature 0.0-2.0 (required)
            max_retries: Maximum retry attempts (required)
            timeout: Request timeout in seconds (required)
            **kwargs: Additional config overrides
        """
        return cls(
            provider=LLMProvider.LOCAL,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            **kwargs,
        )

    @property
    def is_local(self) -> bool:
        """Check if using a local LLM server."""
        return self.provider == LLMProvider.LOCAL or self.base_url is not None


class EmbeddingConfig(BaseModel):
    """Configuration for an embedding model connection.

    Supports multiple embedding backends:
    - OpenAI API
    - OpenAI-compatible local servers (LM Studio, Ollama, etc.)
    - Hash-based (for testing)
    """

    provider: EmbeddingProvider = Field(
        ...,
        description="Embedding provider type. Required - no default.",
    )
    model: str = Field(
        ...,
        description="Embedding model name/ID",
    )
    # OpenAI/Local provider settings
    api_key: str | None = None
    base_url: str | None = None
    max_retries: int = Field(
        ...,
        description="Maximum retry attempts",
    )
    timeout: int = Field(
        ...,
        description="Request timeout in seconds",
    )
    # Hash-based provider settings
    dimension: int = Field(
        ...,
        description="Embedding dimension (for hash_based provider)",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Validate and normalize base URL."""
        if v is None or v == "":
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base URL '{v}'. Must start with http:// or https://")
        return v.rstrip("/")

    @classmethod
    def for_openai(
        cls,
        api_key: str,
        model: str,
        max_retries: int,
        timeout: int,
        dimension: int,
    ) -> "EmbeddingConfig":
        """Create config for OpenAI API.

        All parameters required. For namespace-based config with defaults,
        use DatasetsConfigLoader.get_dataset_config(namespace).embedding.to_embedding_config()

        Args:
            api_key: OpenAI API key (required)
            model: Embedding model name (required, e.g., 'text-embedding-3-small')
            max_retries: Maximum retry attempts (required)
            timeout: Request timeout in seconds (required)
            dimension: Embedding dimension (required)
        """
        return cls(
            provider=EmbeddingProvider.OPENAI,
            api_key=api_key,
            base_url=None,
            model=model,
            max_retries=max_retries,
            timeout=timeout,
            dimension=dimension,
        )

    @classmethod
    def for_local(
        cls,
        base_url: str,
        model: str,
        api_key: str,
        max_retries: int,
        timeout: int,
        dimension: int,
    ) -> "EmbeddingConfig":
        """Create config for local embedding server (LM Studio, Ollama, etc.).

        All parameters required. For namespace-based config with defaults,
        use DatasetsConfigLoader.get_dataset_config(namespace).embedding.to_embedding_config()

        Args:
            base_url: Base URL for the local embedding server (required)
            model: Model name/ID (required)
            api_key: API key (required - use "local" for servers that don't validate)
            max_retries: Maximum retry attempts (required)
            timeout: Request timeout in seconds (required)
            dimension: Embedding dimension (required)
        """
        return cls(
            provider=EmbeddingProvider.LOCAL,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_retries=max_retries,
            timeout=timeout,
            dimension=dimension,
        )

    @classmethod
    def for_hash_based(
        cls,
        dimension: int,
        max_retries: int,
        timeout: int,
    ) -> "EmbeddingConfig":
        """Create config for hash-based embeddings (testing only).

        All parameters required. For namespace-based config with defaults,
        use DatasetsConfigLoader.get_dataset_config(namespace).embedding.to_embedding_config()

        Args:
            dimension: Embedding dimension (required)
            max_retries: Maximum retry attempts (required - typically 0 for local hashing)
            timeout: Request timeout in seconds (required)
        """
        return cls(
            provider=EmbeddingProvider.HASH_BASED,
            model="hash-based",
            dimension=dimension,
            max_retries=max_retries,
            timeout=timeout,
            api_key=None,
            base_url=None,
        )

    @property
    def is_local(self) -> bool:
        """Check if using a local embedding model (not calling external API)."""
        return self.provider in (EmbeddingProvider.LOCAL, EmbeddingProvider.HASH_BASED)

    @property
    def requires_api_key(self) -> bool:
        """Check if this provider requires an API key."""
        return self.provider in (EmbeddingProvider.OPENAI, EmbeddingProvider.LOCAL)
