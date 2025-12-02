"""Base abstract class for embedding generators."""

from abc import ABC, abstractmethod


class EmbeddingGenerator(ABC):
    """Abstract base class for embedding generators.

    All embedding generators must implement these methods to support
    both single and batch embedding generation.
    """

    @abstractmethod
    async def embed(self, text: str, model: str, **options: object) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed
            model: Model identifier (e.g., "text-embedding-3-small")
            **options: Additional provider-specific options

        Returns:
            Embedding vector as list of floats
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str], model: str, **options: object) -> list[list[float]]:
        """Generate embeddings for multiple texts (batched for efficiency).

        Args:
            texts: List of input texts to embed
            model: Model identifier
            **options: Additional provider-specific options

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def get_dimension(self, model: str) -> int:
        """Get embedding dimension for a model.

        Args:
            model: Model identifier

        Returns:
            Embedding dimension
        """
        pass
