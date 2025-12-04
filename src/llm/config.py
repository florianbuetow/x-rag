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
    base_url: str | None = Field(
        default=None,
        description="Base URL for API (None = OpenAI default, or local server URL)",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Model name/ID",
    )
    max_tokens: int = Field(
        default=500,
        description="Maximum tokens in response",
    )
    temperature: float = Field(
        default=0.7,
        description="Sampling temperature (0.0-2.0)",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts",
    )
    timeout: int = Field(
        default=60,
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
        model: str = "gpt-4o-mini",
        **kwargs: object,
    ) -> "LLMConfig":
        """Create config for OpenAI API."""
        return cls(
            provider=LLMProvider.OPENAI,
            api_key=api_key,
            base_url=None,
            model=model,
            **kwargs,  # type: ignore[arg-type]
        )

    @classmethod
    def for_local(
        cls,
        base_url: str,
        model: str,
        api_key: str = "local",
        **kwargs: object,
    ) -> "LLMConfig":
        """Create config for local LLM (LM Studio, Ollama, etc.)."""
        return cls(
            provider=LLMProvider.LOCAL,
            api_key=api_key,
            base_url=base_url,
            model=model,
            **kwargs,  # type: ignore[arg-type]
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
        default="text-embedding-3-small",
        description="Embedding model name/ID",
    )
    # OpenAI/Local provider settings
    api_key: str | None = Field(
        default=None,
        description="API key (required for OpenAI/Local providers)",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for API (required for Local provider)",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )
    # Hash-based provider settings
    dimension: int = Field(
        default=768,
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
        model: str = "text-embedding-3-small",
        **kwargs: object,
    ) -> "EmbeddingConfig":
        """Create config for OpenAI API."""
        return cls(
            provider=EmbeddingProvider.OPENAI,
            api_key=api_key,
            base_url=None,
            model=model,
            **kwargs,  # type: ignore[arg-type]
        )

    @classmethod
    def for_local(
        cls,
        base_url: str,
        model: str,
        api_key: str = "local",
        **kwargs: object,
    ) -> "EmbeddingConfig":
        """Create config for local embedding server (LM Studio, Ollama, etc.)."""
        return cls(
            provider=EmbeddingProvider.LOCAL,
            api_key=api_key,
            base_url=base_url,
            model=model,
            **kwargs,  # type: ignore[arg-type]
        )

    @classmethod
    def for_hash_based(
        cls,
        dimension: int = 768,
        **kwargs: object,
    ) -> "EmbeddingConfig":
        """Create config for hash-based embeddings (testing only)."""
        return cls(
            provider=EmbeddingProvider.HASH_BASED,
            model="hash-based",
            dimension=dimension,
            **kwargs,  # type: ignore[arg-type]
        )

    @property
    def is_local(self) -> bool:
        """Check if using a local embedding model (not calling external API)."""
        return self.provider in (EmbeddingProvider.LOCAL, EmbeddingProvider.HASH_BASED)

    @property
    def requires_api_key(self) -> bool:
        """Check if this provider requires an API key."""
        return self.provider in (EmbeddingProvider.OPENAI, EmbeddingProvider.LOCAL)
