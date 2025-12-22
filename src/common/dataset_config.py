"""Dataset configuration management.

Provides utilities for loading dataset configurations from datasets_config.yaml
and mapping namespaces to dataset-specific settings (embedding, LLM, chunking, search).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.config import load_yaml_config
from src.core.errors import ConfigurationError
from src.llm.config import EmbeddingConfig, EmbeddingProvider, LLMConfig, LLMProvider


@dataclass
class DatasetEmbeddingConfig:
    """Per-dataset embedding configuration."""

    provider: str
    model: str | None = None
    base_url_env: str | None = None  # Name of env var containing base URL
    api_key_env: str | None = None  # Name of env var containing API key
    dimension: int = 1024
    timeout: int = 30
    max_retries: int = 3
    batch_size: int = 50

    def to_embedding_config(self) -> EmbeddingConfig:
        """Convert to production EmbeddingConfig with env var resolution.

        Returns:
            EmbeddingConfig instance with environment variables resolved.

        Raises:
            ConfigurationError: If provider is unsupported or required env vars are missing.
        """
        provider_enum = EmbeddingProvider(self.provider)

        if provider_enum == EmbeddingProvider.HASH_BASED:
            return EmbeddingConfig.for_hash_based(dimension=self.dimension)

        # Resolve env vars
        api_key = os.getenv(self.api_key_env) if self.api_key_env else None
        base_url = os.getenv(self.base_url_env) if self.base_url_env else None

        if provider_enum == EmbeddingProvider.LOCAL:
            if not base_url:
                raise ConfigurationError(f"Missing environment variable: {self.base_url_env} (required for local embedding provider)")
            return EmbeddingConfig.for_local(
                base_url=base_url,
                model=self.model or "text-embedding-bge-large-en-v1.5",
                api_key=api_key or "local",
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        elif provider_enum == EmbeddingProvider.OPENAI:
            if not api_key:
                raise ConfigurationError(f"Missing environment variable: {self.api_key_env} (required for OpenAI embedding provider)")
            return EmbeddingConfig.for_openai(
                api_key=api_key,
                model=self.model or "text-embedding-3-small",
                timeout=self.timeout,
                max_retries=self.max_retries,
            )

        raise ConfigurationError(f"Unsupported embedding provider: {provider_enum}")


@dataclass
class DatasetLLMConfig:
    """Per-dataset LLM configuration."""

    provider: str
    model: str
    base_url_env: str | None = None
    api_key_env: str | None = None
    max_tokens: int = 500
    temperature: float = 0.7
    timeout: int = 60
    max_retries: int = 3

    def to_llm_config(self) -> LLMConfig:
        """Convert to production LLMConfig with env var resolution.

        Returns:
            LLMConfig instance with environment variables resolved.

        Raises:
            ConfigurationError: If provider is unsupported or required env vars are missing.
        """
        provider_enum = LLMProvider(self.provider)

        # Resolve env vars
        api_key = os.getenv(self.api_key_env) if self.api_key_env else None
        base_url = os.getenv(self.base_url_env) if self.base_url_env else None

        if provider_enum == LLMProvider.LOCAL:
            if not base_url:
                raise ConfigurationError(f"Missing environment variable: {self.base_url_env} (required for local LLM provider)")
            return LLMConfig.for_local(
                base_url=base_url,
                model=self.model,
                api_key=api_key or "local",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        elif provider_enum == LLMProvider.OPENAI:
            if not api_key:
                raise ConfigurationError(f"Missing environment variable: {self.api_key_env} (required for OpenAI LLM provider)")
            return LLMConfig.for_openai(
                api_key=api_key,
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )

        raise ConfigurationError(f"Unsupported LLM provider: {provider_enum}")


@dataclass
class DatasetChunkingConfig:
    """Per-dataset chunking configuration."""

    chunk_size: int = 100
    chunk_overlap: int = 50
    cleaner_remove_empty_lines: bool = True
    cleaner_remove_extra_whitespaces: bool = True
    cleaner_unicode_normalization: str = "NFC"


@dataclass
class DatasetSearchConfig:
    """Per-dataset search configuration."""

    default_top_k: int = 10
    default_mode: str = "hybrid"
    hybrid_alpha: float = 0.5
    max_context_length: int = 4000


@dataclass
class DatasetWeaviateConfig:
    """Per-dataset Weaviate configuration."""

    collection: str


@dataclass
class DatasetConfig:
    """Complete configuration for a single dataset."""

    namespace: str
    description: str
    input_path: str
    qa_output_base: str | None
    eval_output_base: str | None

    embedding: DatasetEmbeddingConfig
    llm: DatasetLLMConfig
    chunking: DatasetChunkingConfig
    search: DatasetSearchConfig
    weaviate: DatasetWeaviateConfig


class DatasetsConfigLoader:
    """Loads and manages datasets_config.yaml with defaults merging."""

    def __init__(self, config_path: str | Path = "config/datasets_config.yaml") -> None:
        """Initialize from config file.

        Args:
            config_path: Path to datasets_config.yaml file.

        Raises:
            ConfigurationError: If config file is invalid or missing.
        """
        self.config_path = Path(config_path)
        self._raw_config = load_yaml_config(self.config_path)
        self._datasets: dict[str, DatasetConfig] = {}
        self._load_all_datasets()

    def _merge_defaults(self, dataset_config: dict[str, Any]) -> dict[str, Any]:
        """Merge global defaults with dataset-specific config.

        Args:
            dataset_config: Raw dataset configuration dict.

        Returns:
            Merged configuration with defaults applied.
        """
        defaults = self._raw_config.get("defaults", {})
        merged = {}

        # Merge each section (embedding, llm, chunking, search)
        for section in ["embedding", "llm", "chunking", "search", "weaviate"]:
            default_section = defaults.get(section, {})
            dataset_section = dataset_config.get(section, {})

            # Merge: dataset-specific overrides defaults
            merged[section] = {**default_section, **dataset_section}

        # Copy non-section fields directly
        for key in dataset_config:
            if key not in ["embedding", "llm", "chunking", "search", "weaviate"]:
                merged[key] = dataset_config[key]

        return merged

    def _parse_dataset_config(self, namespace: str, raw_config: dict[str, Any]) -> DatasetConfig:
        """Parse raw config dict into DatasetConfig with validation.

        Args:
            namespace: Dataset namespace/key.
            raw_config: Raw configuration dictionary for the dataset.

        Returns:
            Validated DatasetConfig instance.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        # Merge defaults
        merged = self._merge_defaults(raw_config)

        try:
            return DatasetConfig(
                namespace=namespace,
                description=merged.get("description", namespace),
                input_path=merged.get("input_path", ""),
                qa_output_base=merged.get("qa_output_base"),
                eval_output_base=merged.get("eval_output_base"),
                embedding=DatasetEmbeddingConfig(**merged["embedding"]),
                llm=DatasetLLMConfig(**merged["llm"]),
                chunking=DatasetChunkingConfig(**merged["chunking"]),
                search=DatasetSearchConfig(**merged["search"]),
                weaviate=DatasetWeaviateConfig(**merged["weaviate"]),
            )
        except (KeyError, TypeError) as e:
            raise ConfigurationError(f"Invalid configuration for dataset '{namespace}': {e}") from e

    def _load_all_datasets(self) -> None:
        """Load and parse all datasets from config file.

        Raises:
            ConfigurationError: If any dataset configuration is invalid.
        """
        datasets_section = self._raw_config.get("datasets", {})

        if not isinstance(datasets_section, dict):
            raise ConfigurationError("'datasets' section must be a dictionary")

        for namespace, config in datasets_section.items():
            if not isinstance(config, dict):
                raise ConfigurationError(f"Dataset '{namespace}' configuration must be a dictionary")

            self._datasets[namespace] = self._parse_dataset_config(namespace, config)

    def get_dataset_config(self, namespace: str) -> DatasetConfig:
        """Get dataset config by namespace.

        Args:
            namespace: Dataset namespace/key.

        Returns:
            DatasetConfig for the namespace.

        Raises:
            ConfigurationError: If namespace not found.
        """
        if namespace not in self._datasets:
            available = ", ".join(self._datasets.keys())
            raise ConfigurationError(f"Unknown namespace: '{namespace}'. Available datasets: {available}")
        return self._datasets[namespace]

    def get_all_datasets(self) -> list[DatasetConfig]:
        """Get all dataset configurations.

        Returns:
            List of all DatasetConfig instances.
        """
        return list(self._datasets.values())

    def list_namespaces(self) -> list[str]:
        """List all available namespace keys.

        Returns:
            List of dataset namespace strings.
        """
        return list(self._datasets.keys())

    def has_dataset(self, namespace: str) -> bool:
        """Check if a dataset exists.

        Args:
            namespace: Dataset namespace/key.

        Returns:
            True if dataset exists, False otherwise.
        """
        return namespace in self._datasets
