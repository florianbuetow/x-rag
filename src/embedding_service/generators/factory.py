"""Factory for creating embedding generator instances."""

import logging
from typing import Literal, cast

from src.embedding_service.generators.embedding_generator import EmbeddingGenerator
from src.embedding_service.generators.hash_based_generator import HashBasedEmbeddingGenerator
from src.embedding_service.generators.openai_generator import OpenAIEmbeddingGenerator

logger = logging.getLogger(__name__)

GeneratorType = Literal["hash_based", "openai"]


class EmbeddingGeneratorFactory:
    """Factory for creating embedding generator instances."""

    @staticmethod
    def create_generator(generator_type: GeneratorType, **kwargs: object) -> EmbeddingGenerator:
        """Create an embedding generator instance."""
        if generator_type == "hash_based":
            return EmbeddingGeneratorFactory._create_hash_based_generator(**kwargs)
        elif generator_type == "openai":
            return EmbeddingGeneratorFactory._create_openai_generator(**kwargs)
        else:
            raise ValueError(f"Unknown generator type '{generator_type}'. Supported types: hash_based, openai")

    @staticmethod
    def _create_hash_based_generator(**kwargs: object) -> HashBasedEmbeddingGenerator:
        """Create hash-based embedding generator."""
        default_dimension = cast(int, kwargs.get("default_dimension", 1536))
        logger.info(f"Creating hash-based embedding generator (dimension={default_dimension})")
        return HashBasedEmbeddingGenerator(default_dimension=default_dimension)

    @staticmethod
    def _create_openai_generator(**kwargs: object) -> OpenAIEmbeddingGenerator:
        """Create OpenAI embedding generator."""
        api_key = kwargs.get("api_key")
        if not api_key:
            raise ValueError("OpenAI generator requires 'api_key' parameter")
        max_retries = cast(int, kwargs.get("max_retries", 3))
        timeout = cast(int, kwargs.get("timeout", 30))
        logger.info("Creating OpenAI embedding generator")
        return OpenAIEmbeddingGenerator(api_key=cast(str, api_key), max_retries=max_retries, timeout=timeout)

    @staticmethod
    def list_generators() -> list[str]:
        """Get list of supported generator types."""
        return ["hash_based", "openai"]
