"""Base protocol for embedding backends."""

from typing import Protocol


class EmbeddingBackend(Protocol):
    """Protocol for embedding generation backends.

    Implementations should support both single and batch embedding generation.
    """

    async def embed(self, text: str, model: str, **options) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed
            model: Model identifier (e.g., "text-embedding-3-small")
            **options: Additional provider-specific options

        Returns:
            Embedding vector as list of floats
        """
        ...

    async def embed_batch(self, texts: list[str], model: str, **options) -> list[list[float]]:
        """Generate embeddings for multiple texts (batched for efficiency).

        Args:
            texts: List of input texts to embed
            model: Model identifier
            **options: Additional provider-specific options

        Returns:
            List of embedding vectors
        """
        ...

    def get_dimension(self, model: str) -> int:
        """Get embedding dimension for a model.

        Args:
            model: Model identifier

        Returns:
            Embedding dimension
        """
        ...
