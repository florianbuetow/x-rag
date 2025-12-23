"""Unit tests for src/core/types.py.

Tests cover:
- Chunk creation and methods
- IndexedChunk creation from Chunk
- RetrievedChunk with_content method
- RetrievalResult factory and properties
"""

import pytest

from src.core.types import Chunk, IndexedChunk, RetrievalResult, RetrievedChunk


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_generate_chunk_id(self):
        """Test deterministic chunk ID generation."""
        chunk_id = Chunk.generate_chunk_id("doc-123", 5)
        assert chunk_id == "doc-123-chunk-5"

    def test_create_with_all_fields(self):
        """Test factory method with all fields."""
        metadata = {"source": "test", "page": 1}
        chunk = Chunk.create(
            doc_id="doc-456",
            chunk_index=3,
            content="Test content",
            metadata=metadata,
            start_char=100,
            end_char=200,
        )

        assert chunk.chunk_id == "doc-456-chunk-3"
        assert chunk.doc_id == "doc-456"
        assert chunk.chunk_index == 3
        assert chunk.content == "Test content"
        assert chunk.metadata == metadata
        assert chunk.start_char == 100
        assert chunk.end_char == 200

    def test_create_with_none_metadata(self):
        """Test factory method converts None metadata to empty dict."""
        chunk = Chunk.create(
            doc_id="doc-789",
            chunk_index=0,
            content="Content",
            metadata=None,
            start_char=None,
            end_char=None,
        )

        assert chunk.metadata == {}
        assert chunk.start_char is None
        assert chunk.end_char is None

    def test_chunk_is_frozen(self):
        """Test that Chunk is immutable."""
        chunk = Chunk.create(
            doc_id="doc-1",
            chunk_index=0,
            content="Test",
            metadata=None,
            start_char=None,
            end_char=None,
        )

        with pytest.raises(AttributeError):
            chunk.content = "Modified"


class TestIndexedChunk:
    """Tests for IndexedChunk dataclass."""

    def test_from_chunk(self):
        """Test creating IndexedChunk from Chunk and vector."""
        chunk = Chunk.create(
            doc_id="doc-xyz",
            chunk_index=2,
            content="Chunk content",
            metadata={"key": "value"},
            start_char=50,
            end_char=100,
        )

        vector = [0.1, 0.2, 0.3, 0.4]
        indexed_chunk = IndexedChunk.from_chunk(chunk, vector)

        assert indexed_chunk.chunk_id == chunk.chunk_id
        assert indexed_chunk.doc_id == chunk.doc_id
        assert indexed_chunk.content == chunk.content
        assert indexed_chunk.metadata == chunk.metadata
        assert indexed_chunk.vector == tuple(vector)

    def test_indexed_chunk_is_frozen(self):
        """Test that IndexedChunk is immutable."""
        chunk = Chunk.create(
            doc_id="doc-1",
            chunk_index=0,
            content="Test",
            metadata=None,
            start_char=None,
            end_char=None,
        )

        indexed = IndexedChunk.from_chunk(chunk, [0.1, 0.2])

        with pytest.raises(AttributeError):
            indexed.content = "Modified"


class TestRetrievedChunk:
    """Tests for RetrievedChunk dataclass."""

    def test_with_content(self):
        """Test adding content to a retrieved chunk."""
        chunk = RetrievedChunk(
            chunk_id="chunk-123",
            score=0.95,
            content=None,
            metadata={"source": "test"},
            doc_id="doc-abc",
        )

        chunk_with_content = chunk.with_content("Retrieved content text")

        assert chunk_with_content.chunk_id == chunk.chunk_id
        assert chunk_with_content.score == chunk.score
        assert chunk_with_content.content == "Retrieved content text"
        assert chunk_with_content.metadata == chunk.metadata
        assert chunk_with_content.doc_id == chunk.doc_id

    def test_retrieved_chunk_defaults(self):
        """Test RetrievedChunk with default values."""
        chunk = RetrievedChunk(chunk_id="chunk-1", score=0.8)

        assert chunk.chunk_id == "chunk-1"
        assert chunk.score == 0.8
        assert chunk.content is None
        assert chunk.metadata == {}
        assert chunk.doc_id is None

    def test_retrieved_chunk_is_frozen(self):
        """Test that RetrievedChunk is immutable."""
        chunk = RetrievedChunk(chunk_id="chunk-1", score=0.8)

        with pytest.raises(AttributeError):
            chunk.score = 0.9


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""

    def test_create_with_all_fields(self):
        """Test factory method with all fields."""
        chunks = [
            RetrievedChunk(chunk_id="chunk-1", score=0.95, content="Content 1"),
            RetrievedChunk(chunk_id="chunk-2", score=0.85, content="Content 2"),
        ]
        config = {"top_k": 10, "mode": "hybrid"}

        result = RetrievalResult.create(
            query="test query",
            chunks=chunks,
            latency_ms=150.5,
            config_snapshot=config,
        )

        assert result.query == "test query"
        assert result.chunks == tuple(chunks)
        assert result.latency_ms == 150.5
        assert result.config_snapshot == config

    def test_create_with_none_config(self):
        """Test factory method converts None config to empty dict."""
        chunks = [RetrievedChunk(chunk_id="chunk-1", score=0.9)]

        result = RetrievalResult.create(
            query="test",
            chunks=chunks,
            latency_ms=100.0,
            config_snapshot=None,
        )

        assert result.config_snapshot == {}

    def test_chunk_ids_property(self):
        """Test chunk_ids property returns list of IDs in order."""
        chunks = [
            RetrievedChunk(chunk_id="chunk-3", score=0.95),
            RetrievedChunk(chunk_id="chunk-1", score=0.85),
            RetrievedChunk(chunk_id="chunk-2", score=0.75),
        ]

        result = RetrievalResult.create(
            query="test",
            chunks=chunks,
            latency_ms=50.0,
            config_snapshot=None,
        )

        assert result.chunk_ids == ["chunk-3", "chunk-1", "chunk-2"]

    def test_top_k(self):
        """Test top_k method returns new result with truncated chunks."""
        chunks = [RetrievedChunk(chunk_id=f"chunk-{i}", score=1.0 - i * 0.1) for i in range(10)]

        result = RetrievalResult.create(
            query="test query",
            chunks=chunks,
            latency_ms=200.0,
            config_snapshot={"top_k": 10},
        )

        top_3 = result.top_k(3)

        assert len(top_3.chunks) == 3
        assert top_3.chunks[0].chunk_id == "chunk-0"
        assert top_3.chunks[1].chunk_id == "chunk-1"
        assert top_3.chunks[2].chunk_id == "chunk-2"
        assert top_3.query == result.query
        assert top_3.latency_ms == result.latency_ms
        assert top_3.config_snapshot == result.config_snapshot

    def test_top_k_larger_than_results(self):
        """Test top_k with k larger than number of chunks."""
        chunks = [
            RetrievedChunk(chunk_id="chunk-1", score=0.9),
            RetrievedChunk(chunk_id="chunk-2", score=0.8),
        ]

        result = RetrievalResult.create(
            query="test",
            chunks=chunks,
            latency_ms=50.0,
            config_snapshot=None,
        )

        top_10 = result.top_k(10)

        assert len(top_10.chunks) == 2
        assert top_10.chunks == result.chunks

    def test_retrieval_result_is_frozen(self):
        """Test that RetrievalResult is immutable."""
        result = RetrievalResult.create(
            query="test",
            chunks=[],
            latency_ms=10.0,
            config_snapshot=None,
        )

        with pytest.raises(AttributeError):
            result.query = "modified"
