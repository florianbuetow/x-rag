"""Weaviate retriever for search queries.

Provides vector, BM25, and hybrid search capabilities over documents
stored in Weaviate.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

import weaviate
from weaviate import WeaviateClient
from weaviate.classes.init import AdditionalConfig, Timeout
from weaviate.classes.query import Filter

if TYPE_CHECKING:
    from weaviate.collections.classes.filters import _Filters


logger = logging.getLogger(__name__)


class WeaviateObjectMetadata(Protocol):
    """Protocol for Weaviate object metadata."""

    @property
    def distance(self) -> float | None:
        """Distance metric for vector search."""
        ...

    @property
    def score(self) -> float | None:
        """Score metric for BM25/hybrid search."""
        ...


class WeaviateObject(Protocol):
    """Protocol for Weaviate result object."""

    @property
    def uuid(self) -> object:
        """Object UUID."""
        ...

    @property
    def properties(self) -> dict[str, object]:
        """Object properties."""
        ...

    @property
    def metadata(self) -> WeaviateObjectMetadata:
        """Object metadata."""
        ...


class WeaviateQueryResult(Protocol):
    """Protocol for Weaviate query results."""

    @property
    def objects(self) -> list[WeaviateObject]:
        """List of result objects."""
        ...


class WeaviateCollectionQuery(Protocol):
    """Protocol for Weaviate collection query interface."""

    def near_vector(
        self,
        near_vector: list[float] | None,
        limit: int,
        return_metadata: list[str],
        filters: "_Filters | None",
    ) -> WeaviateQueryResult:
        """Execute near vector query."""
        ...

    def bm25(
        self,
        query: str,
        limit: int,
        return_metadata: list[str],
        filters: "_Filters | None",
    ) -> WeaviateQueryResult:
        """Execute BM25 query."""
        ...

    def hybrid(
        self,
        query: str,
        vector: list[float] | None,
        alpha: float,
        limit: int,
        return_metadata: list[str],
        filters: "_Filters | None",
    ) -> WeaviateQueryResult:
        """Execute hybrid query."""
        ...


class WeaviateCollection(Protocol):
    """Protocol for Weaviate collection."""

    @property
    def query(self) -> WeaviateCollectionQuery:
        """Query interface for the collection."""
        ...


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
        collection_name: str,
        timeout_init: int,
        timeout_query: int,
        timeout_insert: int,
    ) -> None:
        """Initialize Weaviate retriever.

        Args:
            weaviate_url: Weaviate server URL (e.g., "http://weaviate:8080")
            collection_name: Name of Weaviate collection to query
            timeout_init: Weaviate init timeout in seconds
            timeout_query: Weaviate query timeout in seconds
            timeout_insert: Weaviate insert timeout in seconds
        """
        self.weaviate_url = weaviate_url
        self.collection_name = collection_name
        self.timeout_init = timeout_init
        self.timeout_query = timeout_query
        self.timeout_insert = timeout_insert
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

        # Connect with extended timeout for gRPC init
        self.client = weaviate.connect_to_custom(
            http_host=host,
            http_port=port,
            http_secure=False,
            grpc_host=host,
            grpc_port=50051,
            grpc_secure=False,
            additional_config=AdditionalConfig(
                timeout=Timeout(
                    init=self.timeout_init,
                    query=self.timeout_query,
                    insert=self.timeout_insert,
                ),
            ),
        )
        logger.info(f"✓ Connected to Weaviate at {host}:{port}")

    def close(self) -> None:
        """Close connection to Weaviate."""
        if self.client:
            self.client.close()
            self.client = None

    def _execute_query(
        self,
        collection: object,
        query: str,
        query_embedding: list[float] | None,
        top_k: int,
        mode: Literal["vector", "bm25", "hybrid"],
        alpha: float,
        filters: "_Filters | None",
    ) -> WeaviateQueryResult:
        """Execute the search query based on mode.

        Args:
            collection: Weaviate collection to query
            query: Search query text
            query_embedding: Query embedding vector
            top_k: Number of results
            mode: Search mode
            alpha: Hybrid search alpha
            filters: Optional namespace filter

        Returns:
            Weaviate query result
        """
        weaviate_collection = cast(WeaviateCollection, collection)
        if mode == "vector":
            return weaviate_collection.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                return_metadata=["distance"],
                filters=filters,
            )
        elif mode == "bm25":
            return weaviate_collection.query.bm25(
                query=query,
                limit=top_k,
                return_metadata=["score"],
                filters=filters,
            )
        elif mode == "hybrid":
            return weaviate_collection.query.hybrid(
                query=query,
                vector=query_embedding,
                alpha=alpha,
                limit=top_k,
                return_metadata=["score"],
                filters=filters,
            )
        else:
            raise ValueError(f"Invalid search mode: {mode}")

    def _convert_to_search_result(
        self,
        obj: object,
        mode: Literal["vector", "bm25", "hybrid"],
    ) -> SearchResult:
        """Convert a Weaviate object to a SearchResult.

        Args:
            obj: Weaviate result object
            mode: Search mode used (affects score extraction)

        Returns:
            SearchResult instance
        """
        # Extract score/distance based on mode (cast to Protocol for type safety)
        weaviate_obj = cast(WeaviateObject, obj)
        obj_metadata = weaviate_obj.metadata
        obj_uuid = weaviate_obj.uuid
        obj_properties = weaviate_obj.properties

        if mode == "vector":
            distance = obj_metadata.distance
            if distance is None:
                raise ValueError(f"Weaviate object {obj_uuid} missing required distance in vector mode")
            score = 1.0 / (1.0 + distance)
        else:
            score_val = obj_metadata.score
            if score_val is None:
                raise ValueError(f"Weaviate object {obj_uuid} missing required score in hybrid mode")
            score = score_val

        # Build metadata
        metadata = {
            "doc_id": obj_properties["doc_id"] if "doc_id" in obj_properties else "",
            "chunk_index": obj_properties["chunk_index"] if "chunk_index" in obj_properties else 0,
            "namespace": obj_properties["namespace"] if "namespace" in obj_properties else "",
            "source": obj_properties["source"] if "source" in obj_properties else "",
            "title": obj_properties["title"] if "title" in obj_properties else "",
        }

        # Add custom metadata if present
        metadata_json = obj_properties["metadata_json"]
        if metadata_json and isinstance(metadata_json, str):
            try:
                custom_metadata = json.loads(metadata_json)
                metadata.update(custom_metadata)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse metadata_json for chunk {obj_uuid}")

        content = obj_properties["content"]
        content_str = str(content) if content is not None else ""

        return SearchResult(id=str(obj_uuid), content=content_str, score=score, metadata=metadata)

    def search(
        self,
        query: str,
        query_embedding: list[float] | None,
        top_k: int,
        mode: Literal["vector", "bm25", "hybrid"],
        alpha: float,
        namespace: str | None,
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
            filters = Filter.by_property("namespace").equal(namespace) if namespace else None

            # Execute search and convert results
            result = self._execute_query(collection, query, query_embedding, top_k, mode, alpha, filters)
            search_results = [self._convert_to_search_result(obj, mode) for obj in result.objects]

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
