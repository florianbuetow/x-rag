"""Core interfaces for the RAG platform.

These Protocol classes define the contracts for key components.
They are compatible with Haystack and allow for dependency injection.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Literal, Protocol, runtime_checkable

from src.core.document import CoreDocument
from src.core.types import Chunk, IndexedChunk, RetrievedChunk

SearchMode = Literal["vector", "bm25", "hybrid"]


# =============================================================================
# Document Processing Protocols
# =============================================================================


@runtime_checkable
class DocumentLoader(Protocol):
    """Protocol for loading documents from storage."""

    @abstractmethod
    def load(self, bucket: str, key: str) -> dict[str, Any]:
        """Load document from storage.

        Args:
            bucket: Storage bucket name
            key: Object key

        Returns:
            Document dictionary with at least 'id', 'text', and optional 'metadata'
        """
        ...


@runtime_checkable
class Chunker(Protocol):
    """Protocol for splitting text into chunks."""

    @abstractmethod
    def chunk(self, text: str, doc_id: str, metadata: dict[str, Any] | None = None) -> list[Chunk]:
        """Split text into chunks with deterministic IDs.

        Args:
            text: Text to split
            doc_id: Parent document ID for generating chunk IDs
            metadata: Optional metadata to attach to chunks

        Returns:
            List of Chunk objects with deterministic chunk_ids
        """
        ...


@runtime_checkable
class TextSplitter(Protocol):
    """Protocol for splitting text into raw text chunks (legacy interface)."""

    @abstractmethod
    def split(self, text: str) -> list[str]:
        """Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        ...


@runtime_checkable
class TextCleaner(Protocol):
    """Protocol for cleaning document text."""

    @abstractmethod
    def clean(self, text: str) -> str:
        """Clean and normalize text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        ...


# =============================================================================
# Embedding Protocols
# =============================================================================


@runtime_checkable
class EmbeddingClient(Protocol):
    """Protocol for generating embeddings."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        ...

    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Embedding vector dimension
        """
        ...


# =============================================================================
# Index Protocols
# =============================================================================


@runtime_checkable
class IndexClient(Protocol):
    """Protocol for vector index operations.

    This protocol abstracts vector database operations, allowing different
    backends (Weaviate, Pinecone, Qdrant, etc.) to be swapped.
    """

    @abstractmethod
    def create_collection(
        self,
        name: str,
        dimensions: int,
        distance_metric: Literal["cosine", "l2", "dot"] = "cosine",
    ) -> None:
        """Create a new collection/index.

        Args:
            name: Collection name
            dimensions: Embedding vector dimensions
            distance_metric: Distance metric for similarity search
        """
        ...

    @abstractmethod
    def delete_collection(self, name: str) -> None:
        """Delete a collection.

        Args:
            name: Collection name
        """
        ...

    @abstractmethod
    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists.

        Args:
            name: Collection name

        Returns:
            True if collection exists
        """
        ...

    @abstractmethod
    def insert_batch(
        self,
        collection: str,
        chunks: list[IndexedChunk],
    ) -> int:
        """Insert a batch of indexed chunks.

        Args:
            collection: Collection name
            chunks: List of indexed chunks to insert

        Returns:
            Number of chunks inserted
        """
        ...

    @abstractmethod
    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Vector similarity search.

        Args:
            collection: Collection name
            vector: Query vector
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of retrieved chunks with scores
        """
        ...

    @abstractmethod
    def hybrid_search(
        self,
        collection: str,
        query: str,
        vector: list[float],
        top_k: int = 10,
        alpha: float = 0.5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Hybrid search combining vector and keyword search.

        Args:
            collection: Collection name
            query: Text query for keyword search
            vector: Query vector for similarity search
            top_k: Number of results to return
            alpha: Weight for vector vs keyword (0=keyword only, 1=vector only)
            filters: Optional metadata filters

        Returns:
            List of retrieved chunks with scores
        """
        ...


@runtime_checkable
class Retriever(Protocol):
    """Protocol for document retrieval."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        mode: SearchMode = "hybrid",
        namespace: str = "default",
    ) -> list[CoreDocument]:
        """Retrieve documents relevant to the query.

        Args:
            query: Search query text
            top_k: Maximum number of documents to return
            mode: Search mode (vector, bm25, or hybrid)
            namespace: Namespace for multi-tenancy

        Returns:
            List of relevant documents with scores
        """
        ...


@runtime_checkable
class GraphRetriever(Protocol):
    """Protocol for graph-based retrieval."""

    @abstractmethod
    def neighbors(
        self,
        doc_ids: list[str],
        top_k: int = 10,
        namespace: str = "default",
    ) -> list[CoreDocument]:
        """Find neighboring documents in the graph.

        Args:
            doc_ids: Source document IDs
            top_k: Maximum number of neighbors to return
            namespace: Namespace for multi-tenancy

        Returns:
            List of neighboring documents
        """
        ...


@runtime_checkable
class Reranker(Protocol):
    """Protocol for document reranking."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[CoreDocument],
        top_k: int | None = None,
    ) -> list[CoreDocument]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query text
            documents: Documents to rerank
            top_k: Number of top documents to return (None = all)

        Returns:
            Reranked documents with updated scores
        """
        ...


@runtime_checkable
class AnswerGenerator(Protocol):
    """Protocol for generating answers from documents."""

    @abstractmethod
    def generate(
        self,
        query: str,
        documents: list[CoreDocument],
    ) -> str:
        """Generate an answer from retrieved documents.

        Args:
            query: User's question
            documents: Context documents

        Returns:
            Generated answer text
        """
        ...


@runtime_checkable
class Cache(Protocol):
    """Protocol for caching."""

    @abstractmethod
    def get(self, key: str) -> object | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        ...

    @abstractmethod
    def set(self, key: str, value: object, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
        """
        ...
