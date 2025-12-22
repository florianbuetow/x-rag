"""Hash-based embedding generator for testing and development.

Uses deterministic hash-based generation to create reproducible "embeddings"
without requiring external API calls. Useful for testing, CI/CD, and development.
"""

import hashlib
import logging

from src.embedding_service.generators.embedding_generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


class HashBasedEmbeddingGenerator(EmbeddingGenerator):
    """Hash-based embedding generator using deterministic hash generation.

    Generates deterministic embeddings based on text hash, useful for:
    - Testing without API costs
    - Reproducible tests
    - CI/CD pipelines
    - Development without API keys
    - Load testing

    The embeddings are deterministic: same text always produces same embedding.
    """

    # Large prime number for hash modulo operation
    LARGE_PRIME = 999999937

    # Model dimensions mapping (compatible with OpenAI models for testing)
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        "hash-small": 384,
        "hash-medium": 768,
        "hash-large": 1536,
    }

    def __init__(self) -> None:
        """Initialize hash-based generator."""
        logger.info("HashBasedEmbeddingGenerator initialized")

    async def embed(self, text: str, model: str, **options: object) -> list[float]:
        """Generate deterministic embedding for a single text.

        Uses SHA-256 hash of the text to generate a deterministic embedding vector.
        The embedding is reproducible: same text always generates same vector.

        Args:
            text: Input text to embed
            model: Model identifier
            **options: Additional options (ignored for hash-based generator)

        Returns:
            Deterministic embedding vector as list of floats
        """
        dimension = self.get_dimension(model)
        embedding = self._generate_embedding(text, dimension)
        logger.debug(f"Generated hash-based embedding for text (length={len(text)}, dim={dimension})")
        return embedding

    async def embed_batch(self, texts: list[str], model: str, **options: object) -> list[list[float]]:
        """Generate deterministic embeddings for multiple texts.

        Args:
            texts: List of input texts to embed
            model: Model identifier
            **options: Additional options (ignored for hash-based generator)

        Returns:
            List of deterministic embedding vectors
        """
        if not texts:
            return []

        dimension = self.get_dimension(model)
        embeddings = [self._generate_embedding(text, dimension) for text in texts]
        logger.debug(f"Generated {len(embeddings)} hash-based embeddings in batch (dim={dimension})")
        return embeddings

    def get_dimension(self, model: str) -> int:
        """Get embedding dimension for a model.

        Args:
            model: Model identifier

        Returns:
            Embedding dimension

        Raises:
            ValueError: If model is not recognized
        """
        if model not in self.MODEL_DIMENSIONS:
            raise ValueError(
                f"Unknown model '{model}'. Supported models: {', '.join(self.MODEL_DIMENSIONS.keys())}"
            )
        return self.MODEL_DIMENSIONS[model]

    def _generate_embedding(self, text: str, dimension: int) -> list[float]:
        """Generate deterministic embedding vector from text.

        Algorithm:
        1. Compute SHA-256 hash of the text
        2. Use hash bytes to seed deterministic float generation
        3. Generate 'dimension' floats in range [-1, 1]
        4. Normalize to unit vector for cosine similarity compatibility

        Args:
            text: Input text
            dimension: Embedding dimension

        Returns:
            Normalized embedding vector
        """
        # Compute stable hash of the text
        text_hash = hashlib.sha256(text.encode("utf-8")).digest()

        # Generate deterministic floats from hash
        embedding = []
        for i in range(dimension):
            # Use different parts of hash for each dimension
            # Combine hash with dimension index for variety
            seed = int.from_bytes(text_hash[(i % 32) : ((i % 32) + 1)], byteorder="big")
            seed = (seed + i * 31) % self.LARGE_PRIME

            # Convert to float in range [-1, 1]
            value = (seed / self.LARGE_PRIME) * 2 - 1
            embedding.append(value)

        # Normalize to unit vector (for cosine similarity)
        magnitude = sum(x * x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding
