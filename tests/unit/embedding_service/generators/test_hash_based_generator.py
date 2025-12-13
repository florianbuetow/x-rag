"""Unit tests for src/embedding_service/generators/hash_based_generator.py.

Tests cover:
- HashBasedEmbeddingGenerator initialization
- embed method (determinism, dimension, normalization)
- embed_batch method
- get_dimension method
- _generate_embedding internal method behavior
"""

import pytest

from src.embedding_service.generators.hash_based_generator import HashBasedEmbeddingGenerator


class TestHashBasedEmbeddingGeneratorInit:
    """Tests for HashBasedEmbeddingGenerator initialization."""

    def test_init_sets_default_dimension(self):
        """Tests that __init__ sets default_dimension."""
        generator = HashBasedEmbeddingGenerator(default_dimension=768)

        assert generator.default_dimension == 768

    def test_init_requires_default_dimension(self):
        """Tests that __init__ requires default_dimension parameter."""
        with pytest.raises(TypeError, match="default_dimension"):
            HashBasedEmbeddingGenerator()


class TestHashBasedEmbeddingGeneratorEmbed:
    """Tests for HashBasedEmbeddingGenerator.embed method."""

    @pytest.fixture
    def generator(self):
        """Create generator instance for tests."""
        return HashBasedEmbeddingGenerator(default_dimension=1536)

    @pytest.mark.asyncio
    async def test_embed_returns_list_of_floats(self, generator):
        """Tests that embed returns a list of floats."""
        embedding = await generator.embed("test text", model="text-embedding-3-small")

        assert isinstance(embedding, list)
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_embed_returns_correct_dimension(self, generator):
        """Tests that embed returns embedding with correct dimension."""
        embedding = await generator.embed("test text", model="text-embedding-3-small")

        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_returns_different_dimension_for_different_model(self, generator):
        """Tests that embed respects model dimension."""
        embedding_small = await generator.embed("test", model="hash-small")
        embedding_large = await generator.embed("test", model="hash-large")

        assert len(embedding_small) == 384
        assert len(embedding_large) == 1536

    @pytest.mark.asyncio
    async def test_embed_is_deterministic(self, generator):
        """Tests that same text produces same embedding."""
        embedding1 = await generator.embed("hello world", model="text-embedding-3-small")
        embedding2 = await generator.embed("hello world", model="text-embedding-3-small")

        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_embed_different_texts_produce_different_embeddings(self, generator):
        """Tests that different texts produce different embeddings."""
        embedding1 = await generator.embed("hello", model="text-embedding-3-small")
        embedding2 = await generator.embed("world", model="text-embedding-3-small")

        assert embedding1 != embedding2

    @pytest.mark.asyncio
    async def test_embed_handles_empty_string(self, generator):
        """Tests that embed handles empty string."""
        embedding = await generator.embed("", model="text-embedding-3-small")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_handles_unicode(self, generator):
        """Tests that embed handles unicode text."""
        embedding = await generator.embed("Hello 世界 🚀", model="text-embedding-3-small")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_handles_long_text(self, generator):
        """Tests that embed handles long text."""
        long_text = "word " * 10000
        embedding = await generator.embed(long_text, model="text-embedding-3-small")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_produces_normalized_vector(self, generator):
        """Tests that embed produces unit vector (magnitude ~= 1)."""
        embedding = await generator.embed("test text", model="text-embedding-3-small")

        magnitude = sum(x * x for x in embedding) ** 0.5
        assert abs(magnitude - 1.0) < 0.0001

    @pytest.mark.asyncio
    async def test_embed_values_in_valid_range(self, generator):
        """Tests that embedding values are in reasonable range."""
        embedding = await generator.embed("test text", model="text-embedding-3-small")

        # Normalized vectors should have values between -1 and 1
        assert all(-1.0 <= x <= 1.0 for x in embedding)


class TestHashBasedEmbeddingGeneratorEmbedBatch:
    """Tests for HashBasedEmbeddingGenerator.embed_batch method."""

    @pytest.fixture
    def generator(self):
        """Create generator instance for tests."""
        return HashBasedEmbeddingGenerator(default_dimension=1536)

    @pytest.mark.asyncio
    async def test_embed_batch_returns_list_of_embeddings(self, generator):
        """Tests that embed_batch returns list of embeddings."""
        embeddings = await generator.embed_batch(["text1", "text2", "text3"], model="text-embedding-3-small")

        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        assert all(isinstance(e, list) for e in embeddings)

    @pytest.mark.asyncio
    async def test_embed_batch_returns_empty_for_empty_input(self, generator):
        """Tests that embed_batch returns empty list for empty input."""
        embeddings = await generator.embed_batch([], model="text-embedding-3-small")

        assert embeddings == []

    @pytest.mark.asyncio
    async def test_embed_batch_each_embedding_correct_dimension(self, generator):
        """Tests that each embedding in batch has correct dimension."""
        embeddings = await generator.embed_batch(["a", "b", "c"], model="text-embedding-3-small")

        assert all(len(e) == 1536 for e in embeddings)

    @pytest.mark.asyncio
    async def test_embed_batch_is_deterministic(self, generator):
        """Tests that batch embedding is deterministic."""
        texts = ["hello", "world"]
        embeddings1 = await generator.embed_batch(texts, model="text-embedding-3-small")
        embeddings2 = await generator.embed_batch(texts, model="text-embedding-3-small")

        assert embeddings1 == embeddings2

    @pytest.mark.asyncio
    async def test_embed_batch_matches_individual_embeds(self, generator):
        """Tests that batch embeddings match individual embeddings."""
        texts = ["hello", "world"]

        batch_embeddings = await generator.embed_batch(texts, model="text-embedding-3-small")
        individual_embeddings = [await generator.embed(t, model="text-embedding-3-small") for t in texts]

        assert batch_embeddings == individual_embeddings

    @pytest.mark.asyncio
    async def test_embed_batch_handles_large_batch(self, generator):
        """Tests that embed_batch handles large batches."""
        texts = [f"text {i}" for i in range(100)]
        embeddings = await generator.embed_batch(texts, model="text-embedding-3-small")

        assert len(embeddings) == 100


class TestHashBasedEmbeddingGeneratorGetDimension:
    """Tests for HashBasedEmbeddingGenerator.get_dimension method."""

    @pytest.fixture
    def generator(self):
        """Create generator instance for tests."""
        return HashBasedEmbeddingGenerator(default_dimension=1536)

    def test_get_dimension_known_models(self, generator):
        """Tests that get_dimension returns correct dimension for known models."""
        assert generator.get_dimension("text-embedding-3-small") == 1536
        assert generator.get_dimension("text-embedding-3-large") == 3072
        assert generator.get_dimension("text-embedding-ada-002") == 1536
        assert generator.get_dimension("hash-small") == 384
        assert generator.get_dimension("hash-medium") == 768
        assert generator.get_dimension("hash-large") == 1536

    def test_get_dimension_unknown_model_returns_default(self, generator):
        """Tests that get_dimension returns default for unknown model."""
        dimension = generator.get_dimension("unknown-model")

        assert dimension == 1536

    def test_get_dimension_unknown_model_respects_custom_default(self):
        """Tests that get_dimension uses custom default dimension."""
        generator = HashBasedEmbeddingGenerator(default_dimension=512)
        dimension = generator.get_dimension("unknown-model")

        assert dimension == 512


class TestHashBasedEmbeddingGeneratorInternals:
    """Tests for HashBasedEmbeddingGenerator internal methods."""

    @pytest.fixture
    def generator(self):
        """Create generator instance for tests."""
        return HashBasedEmbeddingGenerator(default_dimension=1536)

    def test_generate_embedding_produces_deterministic_output(self, generator):
        """Tests that _generate_embedding is deterministic."""
        embedding1 = generator._generate_embedding("test", 100)
        embedding2 = generator._generate_embedding("test", 100)

        assert embedding1 == embedding2

    def test_generate_embedding_respects_dimension(self, generator):
        """Tests that _generate_embedding produces correct dimension."""
        embedding = generator._generate_embedding("test", 256)

        assert len(embedding) == 256

    def test_generate_embedding_different_texts_different_outputs(self, generator):
        """Tests that different texts produce different embeddings."""
        embedding1 = generator._generate_embedding("hello", 100)
        embedding2 = generator._generate_embedding("world", 100)

        assert embedding1 != embedding2

    def test_generate_embedding_is_normalized(self, generator):
        """Tests that _generate_embedding produces normalized vector."""
        embedding = generator._generate_embedding("test", 100)

        magnitude = sum(x * x for x in embedding) ** 0.5
        assert abs(magnitude - 1.0) < 0.0001

    def test_large_prime_is_prime(self, generator):
        """Tests that LARGE_PRIME constant is indeed a prime number."""
        # Simple primality test for the constant
        n = generator.LARGE_PRIME

        if n < 2:
            pytest.fail("LARGE_PRIME should be >= 2")

        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                pytest.fail(f"LARGE_PRIME {n} is divisible by {i}")
