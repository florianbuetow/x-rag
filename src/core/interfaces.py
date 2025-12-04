"""Core interfaces for the RAG platform.

These Protocol classes define the contracts for key components.
They are compatible with Haystack and allow for dependency injection.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Literal, Protocol, runtime_checkable

from src.core.document import CoreDocument

SearchMode = Literal["vector", "bm25", "hybrid"]


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
