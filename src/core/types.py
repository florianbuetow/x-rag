"""Core type definitions for the RAG platform.

Framework-agnostic data types for chunks, indexing, and retrieval operations.
These types follow the same patterns as CoreDocument and are used throughout
the system for type safety and clear API contracts.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Chunk:
    """Represents a chunk of a document before embedding.

    A chunk is a segment of a larger document with associated metadata.
    Chunk IDs are deterministic based on doc_id and chunk_index.
    """

    chunk_id: str
    doc_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    start_char: int | None = None
    end_char: int | None = None

    @staticmethod
    def generate_chunk_id(doc_id: str, chunk_index: int) -> str:
        """Generate a deterministic chunk ID.

        Args:
            doc_id: Parent document ID
            chunk_index: Index of this chunk in the document

        Returns:
            Deterministic chunk ID in format: {doc_id}-chunk-{chunk_index}
        """
        return f"{doc_id}-chunk-{chunk_index}"

    @classmethod
    def create(
        cls,
        doc_id: str,
        chunk_index: int,
        content: str,
        metadata: dict[str, Any] | None = None,
        start_char: int | None = None,
        end_char: int | None = None,
    ) -> "Chunk":
        """Factory method to create a chunk with a deterministic ID.

        Args:
            doc_id: Parent document ID
            chunk_index: Index of this chunk in the document
            content: Chunk text content
            metadata: Additional metadata
            start_char: Starting character position in source document
            end_char: Ending character position in source document

        Returns:
            New Chunk instance with deterministic chunk_id
        """
        return cls(
            chunk_id=cls.generate_chunk_id(doc_id, chunk_index),
            doc_id=doc_id,
            content=content,
            metadata=metadata or {},
            chunk_index=chunk_index,
            start_char=start_char,
            end_char=end_char,
        )


@dataclass(frozen=True)
class IndexedChunk:
    """Represents a chunk that has been embedded and is ready for indexing.

    An indexed chunk contains the embedding vector along with the chunk data.
    """

    chunk_id: str
    doc_id: str
    content: str
    vector: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_chunk(cls, chunk: Chunk, vector: list[float]) -> "IndexedChunk":
        """Create an indexed chunk from a chunk and its embedding.

        Args:
            chunk: Source chunk
            vector: Embedding vector

        Returns:
            New IndexedChunk instance
        """
        return cls(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            content=chunk.content,
            vector=tuple(vector),
            metadata=chunk.metadata,
        )


@dataclass(frozen=True)
class RetrievedChunk:
    """Represents a chunk retrieved from search with a relevance score.

    Retrieved chunks may not contain the full content if only IDs and scores
    were fetched from the index.
    """

    chunk_id: str
    score: float
    content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    doc_id: str | None = None

    def with_content(self, content: str) -> "RetrievedChunk":
        """Create a new retrieved chunk with content populated.

        Args:
            content: Chunk content

        Returns:
            New RetrievedChunk with content
        """
        return RetrievedChunk(
            chunk_id=self.chunk_id,
            score=self.score,
            content=content,
            metadata=self.metadata,
            doc_id=self.doc_id,
        )


@dataclass(frozen=True)
class RetrievalResult:
    """Result of a retrieval operation.

    Contains the retrieved chunks along with timing and configuration metadata
    for reproducibility and debugging.
    """

    query: str
    chunks: tuple[RetrievedChunk, ...]
    latency_ms: float
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        query: str,
        chunks: list[RetrievedChunk],
        latency_ms: float,
        config_snapshot: dict[str, Any] | None = None,
    ) -> "RetrievalResult":
        """Factory method to create a retrieval result.

        Args:
            query: Search query
            chunks: List of retrieved chunks
            latency_ms: Retrieval latency in milliseconds
            config_snapshot: Configuration used for this retrieval

        Returns:
            New RetrievalResult instance
        """
        return cls(
            query=query,
            chunks=tuple(chunks),
            latency_ms=latency_ms,
            config_snapshot=config_snapshot or {},
        )

    @property
    def chunk_ids(self) -> list[str]:
        """Get list of chunk IDs in retrieval order.

        Returns:
            List of chunk IDs
        """
        return [c.chunk_id for c in self.chunks]

    def top_k(self, k: int) -> "RetrievalResult":
        """Return a new result with only the top k chunks.

        Args:
            k: Number of top chunks to keep

        Returns:
            New RetrievalResult with top k chunks
        """
        return RetrievalResult(
            query=self.query,
            chunks=self.chunks[:k],
            latency_ms=self.latency_ms,
            config_snapshot=self.config_snapshot,
        )
