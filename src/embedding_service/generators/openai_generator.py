"""OpenAI embedding generator implementation."""

import logging
from typing import Any

from openai import APIError, AsyncOpenAI, RateLimitError

from src.core.errors import ServiceUnavailableError
from src.embedding_service.generators.embedding_generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


class OpenAIEmbeddingGenerator(EmbeddingGenerator):
    """OpenAI embedding generator with rate limiting and error handling.

    Supports OpenAI embedding models like text-embedding-3-small and
    text-embedding-3-large with automatic retry logic.
    """

    # Model dimensions mapping
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, api_key: str, max_retries: int = 3, timeout: int = 30):
        """Initialize OpenAI generator.

        Args:
            api_key: OpenAI API key
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.client = AsyncOpenAI(
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout,
        )
        self.max_retries = max_retries
        logger.info("OpenAIEmbeddingGenerator initialized")

    async def embed(self, text: str, model: str, **options: Any) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed
            model: Model identifier (e.g., "text-embedding-3-small")
            **options: Additional options (dimensions, etc.)

        Returns:
            Embedding vector as list of floats

        Raises:
            ServiceUnavailableError: If API call fails after retries
        """
        try:
            response = await self.client.embeddings.create(
                input=text,
                model=model,
                **options,
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text (length={len(text)})")
            return embedding

        except RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise ServiceUnavailableError("Rate limit exceeded. Please try again later.") from e

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise ServiceUnavailableError(f"OpenAI API error: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error in embed: {e}")
            raise ServiceUnavailableError(f"Embedding generation failed: {e}") from e

    async def embed_batch(
        self, texts: list[str], model: str, **options: Any
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts (batched for efficiency).

        OpenAI API supports batch embedding which is more efficient than
        individual calls.

        Args:
            texts: List of input texts to embed
            model: Model identifier
            **options: Additional options (dimensions, etc.)

        Returns:
            List of embedding vectors

        Raises:
            ServiceUnavailableError: If API call fails after retries
        """
        if not texts:
            return []

        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=model,
                **options,
            )
            # Extract embeddings in the same order as input
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Generated {len(embeddings)} embeddings in batch")
            return embeddings

        except RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise ServiceUnavailableError("Rate limit exceeded. Please try again later.") from e

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise ServiceUnavailableError(f"OpenAI API error: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error in embed_batch: {e}")
            raise ServiceUnavailableError(f"Batch embedding generation failed: {e}") from e

    def get_dimension(self, model: str) -> int:
        """Get embedding dimension for a model.

        Args:
            model: Model identifier

        Returns:
            Embedding dimension

        Raises:
            ValueError: If model is not supported
        """
        if model not in self.MODEL_DIMENSIONS:
            raise ValueError(
                f"Unknown model '{model}'. Supported models: "
                f"{', '.join(self.MODEL_DIMENSIONS.keys())}"
            )
        return self.MODEL_DIMENSIONS[model]
