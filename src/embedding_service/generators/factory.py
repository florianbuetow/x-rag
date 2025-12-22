"""Factory for creating embedding generator instances."""

import logging
from typing import Literal, cast

from src.embedding_service.generators.embedding_generator import EmbeddingGenerator
from src.embedding_service.generators.hash_based_generator import HashBasedEmbeddingGenerator
from src.embedding_service.generators.openai_generator import OpenAIEmbeddingGenerator
from src.llm.config import EmbeddingConfig, EmbeddingProvider

logger = logging.getLogger(__name__)

GeneratorType = Literal["hash_based", "openai"]


class EmbeddingGeneratorFactory:
    """Factory for creating embedding generator instances."""

    @staticmethod
    def create_generator(generator_type: GeneratorType, **kwargs: object) -> EmbeddingGenerator:
        """Create an embedding generator instance.

        Args:
            generator_type: Type of generator ('hash_based', 'openai')
            **kwargs: Generator-specific configuration

        Returns:
            Configured embedding generator instance
        """
        if generator_type == "hash_based":
            return EmbeddingGeneratorFactory._create_hash_based_generator(**kwargs)
        elif generator_type == "openai":
            return EmbeddingGeneratorFactory._create_openai_generator(**kwargs)
        else:
            raise ValueError(f"Unknown generator type '{generator_type}'. Supported types: {EmbeddingGeneratorFactory.list_generators()}")

    @staticmethod
    def create_from_config(config: EmbeddingConfig) -> EmbeddingGenerator:
        """Create an embedding generator from EmbeddingConfig.

        Args:
            config: Embedding configuration

        Returns:
            Configured embedding generator instance
        """
        if config.provider == EmbeddingProvider.HASH_BASED:
            return EmbeddingGeneratorFactory._create_hash_based_generator()
        elif config.provider in (EmbeddingProvider.OPENAI, EmbeddingProvider.LOCAL):
            if not config.api_key:
                raise ValueError(f"{config.provider.value} generator requires 'api_key'")
            return EmbeddingGeneratorFactory._create_openai_generator(
                api_key=config.api_key,
                max_retries=config.max_retries,
                timeout=config.timeout,
                base_url=config.base_url,
            )
        else:
            raise ValueError(f"Unknown provider '{config.provider}'")

    @staticmethod
    def _create_hash_based_generator(**kwargs: object) -> HashBasedEmbeddingGenerator:
        """Create hash-based embedding generator."""
        logger.info("Creating hash-based embedding generator")
        return HashBasedEmbeddingGenerator()

    @staticmethod
    def _create_openai_generator(**kwargs: object) -> OpenAIEmbeddingGenerator:
        """Create OpenAI embedding generator."""
        if "api_key" not in kwargs:
            raise ValueError("OpenAI generator requires 'api_key' parameter")
        if "max_retries" not in kwargs:
            raise ValueError("OpenAI generator requires 'max_retries' parameter")
        if "timeout" not in kwargs:
            raise ValueError("OpenAI generator requires 'timeout' parameter")
        if "base_url" not in kwargs:
            raise ValueError("OpenAI generator requires 'base_url' parameter")
        api_key = cast(str, kwargs["api_key"])
        max_retries = cast(int, kwargs["max_retries"])
        timeout = cast(int, kwargs["timeout"])
        base_url = cast(str | None, kwargs["base_url"])
        logger.info(f"Creating OpenAI embedding generator (base_url={base_url or 'default'})")
        return OpenAIEmbeddingGenerator(
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout,
            base_url=base_url,
        )

    @staticmethod
    def list_generators() -> list[str]:
        """Get list of supported generator types."""
        return ["hash_based", "openai"]
