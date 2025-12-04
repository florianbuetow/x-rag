"""Weaviate retriever for search queries.

Provides vector, BM25, and hybrid search capabilities over documents
stored in Weaviate.
"""

import logging
from typing import Any, Literal

import weaviate
from weaviate import WeaviateClient

logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a single search result."""

    def __init__(
        self,
        id: str,
        content: str,
        score: float,
        metadata: dict[str, Any],
    ) -> None:
        """Initialize search result.

        Args:
            id: Document chunk ID
            content: Chunk content
            score: Relevance score (higher is better)
            metadata: Additional metadata (doc_id, namespace, etc.)
        """
        self.id = id
        self.content = content
        self.score = score
        self.metadata = metadata

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


class WeaviateRetriever:
    """Retriever that queries Weaviate for relevant documents.

    Supports three search modes:
    - vector: Semantic similarity search using embeddings
    - bm25: Keyword-based lexical search
    - hybrid: Combination of vector and BM25 with configurable alpha
    """

    def __init__(
        self,
        weaviate_url: str,
        collection_name: str = "DocumentChunk",
    ) -> None:
        """Initialize Weaviate retriever.

        Args:
            weaviate_url: Weaviate server URL (e.g., "http://weaviate:8080")
            collection_name: Name of Weaviate collection to query
        """
        self.weaviate_url = weaviate_url
        self.collection_name = collection_name
        self.client: WeaviateClient | None = None

    def connect(self) -> None:
        """Establish connection to Weaviate."""
        logger.info(f"Connecting to Weaviate at {self.weaviate_url}")

        # Parse URL
        url = self.weaviate_url
        if "://" in url:
            url = url.split("://")[1]

        # Split host and port
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            port = int(port_str)
        else:
            host = url
            port = 8080

        # Connect
        self.client = weaviate.connect_to_custom(
            http_host=host,
            http_port=port,
            http_secure=False,
            grpc_host=host,
            grpc_port=50051,
            grpc_secure=False,
        )
        logger.info(f"✓ Connected to Weaviate at {host}:{port}")

    def close(self) -> None:
        """Close connection to Weaviate."""
        if self.client:
            self.client.close()
            self.client = None

    def search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        top_k: int = 10,
        mode: Literal["vector", "bm25", "hybrid"] = "hybrid",
        alpha: float = 0.5,
        namespace: str | None = None,
    ) -> list[SearchResult]:
        """Search for relevant documents.

        Args:
            query: Search query text
            query_embedding: Query embedding vector (required for vector/hybrid modes)
            top_k: Number of results to return
            mode: Search mode (vector, bm25, or hybrid)
            alpha: Hybrid search alpha (0.0=BM25 only, 1.0=vector only)
            namespace: Filter by namespace (optional)

        Returns:
            List of search results ordered by relevance

        Raises:
            RuntimeError: If client not connected
            ValueError: If query_embedding missing for vector/hybrid mode
        """
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Validate embedding for vector/hybrid modes
        if mode in ("vector", "hybrid") and not query_embedding:
            raise ValueError(f"query_embedding required for mode '{mode}'")

        try:
            collection = self.client.collections.get(self.collection_name)

            # Build namespace filter if specified
            filters = None
            if namespace:
                from weaviate.classes.query import Filter

                filters = Filter.by_property("namespace").equal(namespace)

            # Execute search based on mode
            if mode == "vector":
                if query_embedding is None:
                    raise RuntimeError("query_embedding required for vector mode")
                result = collection.query.near_vector(
                    near_vector=query_embedding,
                    limit=top_k,
                    return_metadata=["distance"],
                    filters=filters,
                )
            elif mode == "bm25":
                result = collection.query.bm25(
                    query=query,
                    limit=top_k,
                    return_metadata=["score"],
                    filters=filters,
                )
            elif mode == "hybrid":
                result = collection.query.hybrid(
                    query=query,
                    vector=query_embedding,
                    alpha=alpha,
                    limit=top_k,
                    return_metadata=["score"],
                    filters=filters,
                )
            else:
                raise ValueError(f"Invalid search mode: {mode}")

            # Convert Weaviate results to SearchResult objects
            search_results = []
            for obj in result.objects:
                # Extract score/distance
                if mode == "vector":
                    # Convert distance to similarity score (lower distance = higher score)
                    distance = obj.metadata.distance or 0.0
                    score = 1.0 / (1.0 + distance)  # Simple conversion
                else:
                    score = obj.metadata.score or 0.0

                # Build metadata
                metadata = {
                    "doc_id": obj.properties.get("doc_id", ""),
                    "chunk_index": obj.properties.get("chunk_index", 0),
                    "namespace": obj.properties.get("namespace", ""),
                    "source": obj.properties.get("source", ""),
                    "title": obj.properties.get("title", ""),
                }

                # Add custom metadata if present
                metadata_json = obj.properties.get("metadata_json", "")
                if metadata_json and isinstance(metadata_json, str):
                    try:
                        import json

                        custom_metadata = json.loads(metadata_json)
                        metadata.update(custom_metadata)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse metadata_json for chunk {obj.uuid}")

                # Get content as string
                content = obj.properties.get("content", "")
                content_str = str(content) if content is not None else ""

                search_results.append(
                    SearchResult(
                        id=str(obj.uuid),
                        content=content_str,
                        score=score,
                        metadata=metadata,
                    )
                )

            logger.info(f"Retrieved {len(search_results)} results using {mode} mode")
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def health_check(self) -> bool:
        """Check if Weaviate is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        if not self.client:
            return False

        try:
            # Try to access the collection
            collection = self.client.collections.get(self.collection_name)
            # Just check if we can get collection info
            _ = collection.config.get()
            return True
        except Exception as e:
            logger.warning(f"Weaviate health check failed: {e}")
            return False
