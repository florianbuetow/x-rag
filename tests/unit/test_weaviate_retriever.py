"""Tests for WeaviateRetriever."""

from unittest.mock import Mock, patch

import pytest

from src.retrievers.weaviate_retriever import SearchResult, WeaviateRetriever


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_initialization(self):
        """SearchResult initializes with all fields."""
        result = SearchResult(
            id="chunk-123",
            content="Test content",
            score=0.95,
            metadata={"doc_id": "doc-1", "namespace": "test"},
        )

        assert result.id == "chunk-123"
        assert result.content == "Test content"
        assert result.score == 0.95
        assert result.metadata["doc_id"] == "doc-1"

    def test_to_dict(self):
        """SearchResult converts to dictionary correctly."""
        result = SearchResult(
            id="chunk-123",
            content="Test content",
            score=0.95,
            metadata={"doc_id": "doc-1"},
        )

        result_dict = result.to_dict()

        assert result_dict["id"] == "chunk-123"
        assert result_dict["content"] == "Test content"
        assert result_dict["score"] == 0.95
        assert result_dict["metadata"]["doc_id"] == "doc-1"


class TestWeaviateRetrieverInit:
    """Tests for WeaviateRetriever initialization."""

    def test_initialization_with_url(self):
        """Retriever initializes with URL string."""
        retriever = WeaviateRetriever(
            weaviate_url="http://localhost:8080",
            collection_name="TestCollection",
        )

        assert retriever.weaviate_url == "http://localhost:8080"
        assert retriever.collection_name == "TestCollection"
        assert retriever.client is None

    def test_initialization_requires_collection_name(self):
        """Retriever requires collection_name parameter."""
        with pytest.raises(TypeError, match="collection_name"):
            WeaviateRetriever(weaviate_url="http://localhost:8080")


class TestWeaviateRetrieverConnection:
    """Tests for connection management."""

    @pytest.fixture
    def retriever(self):
        """Create a WeaviateRetriever for testing."""
        return WeaviateRetriever(
            weaviate_url="http://localhost:8080",
            collection_name="DocumentChunk",
        )

    def test_connect_parses_http_url(self, retriever):
        """connect() parses http:// URL correctly."""
        with patch("src.retrievers.weaviate_retriever.weaviate") as mock_weaviate:
            mock_client = Mock()
            mock_weaviate.connect_to_custom.return_value = mock_client

            retriever.connect()

            mock_weaviate.connect_to_custom.assert_called_once()
            call_kwargs = mock_weaviate.connect_to_custom.call_args[1]
            assert call_kwargs["http_host"] == "localhost"
            assert call_kwargs["http_port"] == 8080

    def test_connect_parses_url_without_protocol(self):
        """connect() handles URL without protocol."""
        retriever = WeaviateRetriever(
            weaviate_url="weaviate:8080",
            collection_name="DocumentChunk",
        )

        with patch("src.retrievers.weaviate_retriever.weaviate") as mock_weaviate:
            mock_client = Mock()
            mock_weaviate.connect_to_custom.return_value = mock_client

            retriever.connect()

            call_kwargs = mock_weaviate.connect_to_custom.call_args[1]
            assert call_kwargs["http_host"] == "weaviate"
            assert call_kwargs["http_port"] == 8080

    def test_connect_default_port(self):
        """connect() uses default port 8080 when not specified."""
        retriever = WeaviateRetriever(
            weaviate_url="http://weaviate",
            collection_name="DocumentChunk",
        )

        with patch("src.retrievers.weaviate_retriever.weaviate") as mock_weaviate:
            mock_client = Mock()
            mock_weaviate.connect_to_custom.return_value = mock_client

            retriever.connect()

            call_kwargs = mock_weaviate.connect_to_custom.call_args[1]
            assert call_kwargs["http_port"] == 8080

    def test_connect_stores_client(self, retriever):
        """connect() stores client reference."""
        with patch("src.retrievers.weaviate_retriever.weaviate") as mock_weaviate:
            mock_client = Mock()
            mock_weaviate.connect_to_custom.return_value = mock_client

            retriever.connect()

            assert retriever.client is mock_client

    def test_close_closes_client(self, retriever):
        """close() closes Weaviate client."""
        with patch("src.retrievers.weaviate_retriever.weaviate") as mock_weaviate:
            mock_client = Mock()
            mock_weaviate.connect_to_custom.return_value = mock_client

            retriever.connect()
            retriever.close()

            mock_client.close.assert_called_once()
            assert retriever.client is None

    def test_close_when_not_connected(self, retriever):
        """close() when not connected is safe."""
        # Should not raise
        retriever.close()
        assert retriever.client is None


class TestWeaviateRetrieverSearch:
    """Tests for search functionality."""

    @pytest.fixture
    def retriever(self):
        """Create a connected WeaviateRetriever for testing."""
        retriever = WeaviateRetriever(
            weaviate_url="http://localhost:8080",
            collection_name="DocumentChunk",
        )
        return retriever

    @pytest.fixture
    def mock_weaviate_result(self):
        """Create a mock Weaviate search result."""
        mock_obj = Mock()
        mock_obj.uuid = "chunk-uuid-123"
        mock_obj.properties = {
            "content": "Test document content",
            "doc_id": "doc-123",
            "chunk_index": 0,
            "namespace": "default",
            "source": "test.txt",
            "title": "Test Document",
            "metadata_json": '{"custom": "value"}',
        }
        mock_obj.metadata = Mock()
        mock_obj.metadata.distance = 0.1
        mock_obj.metadata.score = 0.9

        mock_result = Mock()
        mock_result.objects = [mock_obj]
        return mock_result

    def test_search_not_connected_raises(self, retriever):
        """search() before connect() raises RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            retriever.search(
                query="test",
                query_embedding=[0.1, 0.2],
                top_k=10,
                mode="vector",
                alpha=0.5,
                namespace=None,
            )

        assert "Client not connected" in str(exc_info.value)

    def test_search_vector_mode_requires_embedding(self, retriever):
        """Vector mode without embedding raises ValueError."""
        retriever.client = Mock()

        with pytest.raises(ValueError) as exc_info:
            retriever.search(
                query="test",
                query_embedding=None,
                top_k=10,
                mode="vector",
                alpha=0.5,
                namespace=None,
            )

        assert "query_embedding required" in str(exc_info.value)

    def test_search_hybrid_mode_requires_embedding(self, retriever):
        """Hybrid mode without embedding raises ValueError."""
        retriever.client = Mock()

        with pytest.raises(ValueError) as exc_info:
            retriever.search(
                query="test",
                query_embedding=None,
                top_k=10,
                mode="hybrid",
                alpha=0.5,
                namespace=None,
            )

        assert "query_embedding required" in str(exc_info.value)

    def test_search_bm25_mode_no_embedding_required(self, retriever, mock_weaviate_result):
        """BM25 mode works without embedding."""
        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        results = retriever.search(
            query="test query",
            query_embedding=None,
            top_k=10,
            mode="bm25",
            alpha=0.5,
            namespace=None,
        )

        assert len(results) == 1
        mock_collection.query.bm25.assert_called_once()

    def test_search_invalid_mode_raises(self, retriever):
        """Invalid mode raises ValueError."""
        retriever.client = Mock()
        mock_collection = Mock()
        retriever.client.collections.get.return_value = mock_collection

        with pytest.raises(ValueError) as exc_info:
            retriever.search(
                query="test",
                query_embedding=[0.1],
                top_k=10,
                mode="invalid",
                alpha=0.5,
                namespace=None,
            )

        assert "Invalid search mode" in str(exc_info.value)

    def test_search_vector_mode_success(self, retriever, mock_weaviate_result):
        """Vector search returns documents with scores."""
        mock_collection = Mock()
        mock_collection.query.near_vector.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        query_embedding = [0.1, 0.2, 0.3]
        results = retriever.search(
            query="test",
            query_embedding=query_embedding,
            top_k=10,
            mode="vector",
            alpha=0.5,
            namespace=None,
        )

        assert len(results) == 1
        mock_collection.query.near_vector.assert_called_once()
        call_kwargs = mock_collection.query.near_vector.call_args[1]
        assert call_kwargs["near_vector"] == query_embedding
        assert call_kwargs["limit"] == 10

    def test_search_bm25_mode_success(self, retriever, mock_weaviate_result):
        """BM25 search returns documents."""
        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        results = retriever.search(
            query="search terms",
            query_embedding=None,
            top_k=5,
            mode="bm25",
            alpha=0.5,
            namespace=None,
        )

        assert len(results) == 1
        call_kwargs = mock_collection.query.bm25.call_args[1]
        assert call_kwargs["query"] == "search terms"
        assert call_kwargs["limit"] == 5

    def test_search_hybrid_mode_success(self, retriever, mock_weaviate_result):
        """Hybrid search with alpha parameter."""
        mock_collection = Mock()
        mock_collection.query.hybrid.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        query_embedding = [0.1, 0.2, 0.3]
        results = retriever.search(
            query="test query",
            query_embedding=query_embedding,
            top_k=10,
            mode="hybrid",
            alpha=0.7,
            namespace=None,
        )

        assert len(results) == 1
        call_kwargs = mock_collection.query.hybrid.call_args[1]
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["vector"] == query_embedding
        assert call_kwargs["alpha"] == 0.7

    def test_search_with_namespace_filter(self, retriever, mock_weaviate_result):
        """Search applies namespace filter."""
        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        # Filter is imported inside the function, so we patch it at weaviate.classes.query
        with patch("weaviate.classes.query.Filter") as mock_filter:
            mock_filter_instance = Mock()
            mock_filter.by_property.return_value.equal.return_value = mock_filter_instance

            retriever.search(
                query="test",
                query_embedding=None,
                top_k=10,
                mode="bm25",
                alpha=0.5,
                namespace="custom-namespace",
            )

            # Verify filter was applied
            call_kwargs = mock_collection.query.bm25.call_args[1]
            assert call_kwargs["filters"] is not None

    def test_search_result_conversion(self, retriever, mock_weaviate_result):
        """Weaviate results converted to SearchResult."""
        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        results = retriever.search(
            query="test",
            query_embedding=None,
            top_k=10,
            mode="bm25",
            alpha=0.5,
            namespace=None,
        )

        assert len(results) == 1
        result = results[0]
        assert result.id == "chunk-uuid-123"
        assert result.content == "Test document content"
        assert result.metadata["doc_id"] == "doc-123"
        assert result.metadata["namespace"] == "default"

    def test_search_vector_mode_distance_to_score(self, retriever, mock_weaviate_result):
        """Vector mode converts distance to similarity score."""
        mock_weaviate_result.objects[0].metadata.distance = 0.1

        mock_collection = Mock()
        mock_collection.query.near_vector.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        results = retriever.search(
            query="test",
            query_embedding=[0.1, 0.2],
            top_k=10,
            mode="vector",
            alpha=0.5,
            namespace=None,
        )

        # Score = 1 / (1 + distance) = 1 / 1.1 ≈ 0.909
        assert results[0].score == pytest.approx(0.909, rel=0.01)

    def test_search_metadata_json_deserialization(self, retriever, mock_weaviate_result):
        """metadata_json field deserialized correctly."""
        mock_weaviate_result.objects[0].properties["metadata_json"] = '{"custom_field": "custom_value"}'

        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        results = retriever.search(
            query="test",
            query_embedding=None,
            top_k=10,
            mode="bm25",
            alpha=0.5,
            namespace=None,
        )

        assert results[0].metadata["custom_field"] == "custom_value"

    def test_search_metadata_json_invalid_json(self, retriever, mock_weaviate_result):
        """Invalid metadata_json is handled gracefully."""
        mock_weaviate_result.objects[0].properties["metadata_json"] = "not valid json"

        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        # Should not raise, just log warning
        results = retriever.search(
            query="test",
            query_embedding=None,
            top_k=10,
            mode="bm25",
            alpha=0.5,
            namespace=None,
        )
        assert len(results) == 1

    def test_search_respects_top_k(self, retriever, mock_weaviate_result):
        """Search limits results to top_k."""
        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_weaviate_result

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        retriever.search(
            query="test",
            query_embedding=None,
            top_k=25,
            mode="bm25",
            alpha=0.5,
            namespace=None,
        )

        call_kwargs = mock_collection.query.bm25.call_args[1]
        assert call_kwargs["limit"] == 25

    def test_search_exception_propagates(self, retriever):
        """Search exceptions are logged and re-raised."""
        mock_collection = Mock()
        mock_collection.query.bm25.side_effect = RuntimeError("Connection lost")

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        with pytest.raises(RuntimeError) as exc_info:
            retriever.search(
                query="test",
                query_embedding=None,
                top_k=10,
                mode="bm25",
                alpha=0.5,
                namespace=None,
            )

        assert "Connection lost" in str(exc_info.value)


class TestWeaviateRetrieverHealth:
    """Tests for health check."""

    @pytest.fixture
    def retriever(self):
        """Create a WeaviateRetriever for testing."""
        return WeaviateRetriever(
            weaviate_url="http://localhost:8080",
            collection_name="DocumentChunk",
        )

    def test_health_check_not_connected(self, retriever):
        """health_check() returns False when not connected."""
        assert retriever.health_check() is False

    def test_health_check_connected_healthy(self, retriever):
        """health_check() returns True when connected."""
        mock_collection = Mock()
        mock_config = Mock()
        mock_collection.config.get.return_value = mock_config

        retriever.client = Mock()
        retriever.client.collections.get.return_value = mock_collection

        assert retriever.health_check() is True

    def test_health_check_connection_error(self, retriever):
        """health_check() returns False on connection error."""
        retriever.client = Mock()
        retriever.client.collections.get.side_effect = RuntimeError("Connection refused")

        assert retriever.health_check() is False


class TestHelperMethods:
    """Tests for private helper methods extracted during refactoring."""

    @pytest.fixture
    def retriever(self):
        """Create a WeaviateRetriever for testing."""
        retriever = WeaviateRetriever(
            weaviate_url="http://localhost:8080",
            collection_name="DocumentChunk",
        )
        retriever.client = Mock()
        return retriever

    @pytest.fixture
    def mock_collection(self):
        """Create a mock Weaviate collection."""
        return Mock()

    @pytest.fixture
    def mock_weaviate_object(self):
        """Create a mock Weaviate result object."""
        obj = Mock()
        obj.uuid = "test-uuid-123"
        obj.properties = {
            "content": "Test content",
            "doc_id": "doc-123",
            "chunk_index": 0,
            "namespace": "default",
            "source": "test.txt",
            "title": "Test Document",
            "metadata_json": '{"custom": "value"}',
        }
        obj.metadata = Mock()
        obj.metadata.distance = 0.1
        obj.metadata.score = 0.9
        return obj

    # Tests for _execute_query
    def test_execute_query_vector_mode(self, retriever, mock_collection):
        """_execute_query uses near_vector for vector mode."""
        mock_result = Mock()
        mock_collection.query.near_vector.return_value = mock_result

        query_embedding = [0.1, 0.2, 0.3]
        result = retriever._execute_query(
            collection=mock_collection,
            query="test",
            query_embedding=query_embedding,
            top_k=10,
            mode="vector",
            alpha=0.5,
            filters=None,
        )

        assert result is mock_result
        mock_collection.query.near_vector.assert_called_once()
        call_kwargs = mock_collection.query.near_vector.call_args[1]
        assert call_kwargs["near_vector"] == query_embedding
        assert call_kwargs["limit"] == 10

    def test_execute_query_bm25_mode(self, retriever, mock_collection):
        """_execute_query uses bm25 for bm25 mode."""
        mock_result = Mock()
        mock_collection.query.bm25.return_value = mock_result

        result = retriever._execute_query(
            collection=mock_collection,
            query="search terms",
            query_embedding=None,
            top_k=5,
            mode="bm25",
            alpha=0.5,
            filters=None,
        )

        assert result is mock_result
        mock_collection.query.bm25.assert_called_once()
        call_kwargs = mock_collection.query.bm25.call_args[1]
        assert call_kwargs["query"] == "search terms"
        assert call_kwargs["limit"] == 5

    def test_execute_query_hybrid_mode(self, retriever, mock_collection):
        """_execute_query uses hybrid for hybrid mode."""
        mock_result = Mock()
        mock_collection.query.hybrid.return_value = mock_result

        query_embedding = [0.1, 0.2, 0.3]
        result = retriever._execute_query(
            collection=mock_collection,
            query="test query",
            query_embedding=query_embedding,
            top_k=10,
            mode="hybrid",
            alpha=0.7,
            filters=None,
        )

        assert result is mock_result
        mock_collection.query.hybrid.assert_called_once()
        call_kwargs = mock_collection.query.hybrid.call_args[1]
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["vector"] == query_embedding
        assert call_kwargs["alpha"] == 0.7

    def test_execute_query_invalid_mode(self, retriever, mock_collection):
        """_execute_query raises ValueError for invalid mode."""
        with pytest.raises(ValueError) as exc_info:
            retriever._execute_query(
                collection=mock_collection,
                query="test",
                query_embedding=[0.1],
                top_k=10,
                mode="invalid",
                alpha=0.5,
                filters=None,
            )

        assert "Invalid search mode" in str(exc_info.value)

    def test_execute_query_with_filters(self, retriever, mock_collection):
        """_execute_query passes filters to query."""
        mock_result = Mock()
        mock_collection.query.bm25.return_value = mock_result
        mock_filter = Mock()

        retriever._execute_query(
            collection=mock_collection,
            query="test",
            query_embedding=None,
            top_k=10,
            mode="bm25",
            alpha=0.5,
            filters=mock_filter,
        )

        call_kwargs = mock_collection.query.bm25.call_args[1]
        assert call_kwargs["filters"] is mock_filter

    # Tests for _convert_to_search_result
    def test_convert_to_search_result_vector_mode(self, retriever, mock_weaviate_object):
        """_convert_to_search_result calculates score from distance in vector mode."""
        mock_weaviate_object.metadata.distance = 0.1

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="vector")

        assert result.id == "test-uuid-123"
        assert result.content == "Test content"
        # Score = 1 / (1 + 0.1) = 0.909...
        assert result.score == pytest.approx(0.909, rel=0.01)

    def test_convert_to_search_result_bm25_mode(self, retriever, mock_weaviate_object):
        """_convert_to_search_result uses score directly in bm25 mode."""
        mock_weaviate_object.metadata.score = 0.85

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        assert result.score == 0.85

    def test_convert_to_search_result_hybrid_mode(self, retriever, mock_weaviate_object):
        """_convert_to_search_result uses score directly in hybrid mode."""
        mock_weaviate_object.metadata.score = 0.75

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="hybrid")

        assert result.score == 0.75

    def test_convert_to_search_result_extracts_metadata(self, retriever, mock_weaviate_object):
        """_convert_to_search_result extracts all metadata fields."""
        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        assert result.metadata["doc_id"] == "doc-123"
        assert result.metadata["chunk_index"] == 0
        assert result.metadata["namespace"] == "default"
        assert result.metadata["source"] == "test.txt"
        assert result.metadata["title"] == "Test Document"

    def test_convert_to_search_result_parses_metadata_json(self, retriever, mock_weaviate_object):
        """_convert_to_search_result parses metadata_json field."""
        mock_weaviate_object.properties["metadata_json"] = '{"key1": "value1", "key2": 42}'

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        assert result.metadata["key1"] == "value1"
        assert result.metadata["key2"] == 42

    def test_convert_to_search_result_handles_invalid_json(self, retriever, mock_weaviate_object):
        """_convert_to_search_result handles invalid metadata_json gracefully."""
        mock_weaviate_object.properties["metadata_json"] = "not valid json"

        # Should not raise
        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        assert result.id == "test-uuid-123"
        # Invalid JSON is skipped, but base metadata still works
        assert result.metadata["doc_id"] == "doc-123"

    def test_convert_to_search_result_handles_empty_metadata_json(self, retriever, mock_weaviate_object):
        """_convert_to_search_result handles empty metadata_json."""
        mock_weaviate_object.properties["metadata_json"] = ""

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        assert result.id == "test-uuid-123"

    def test_convert_to_search_result_handles_none_content(self, retriever, mock_weaviate_object):
        """_convert_to_search_result handles None content."""
        mock_weaviate_object.properties["content"] = None

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        assert result.content == ""

    def test_convert_to_search_result_handles_missing_optional_fields(self, retriever, mock_weaviate_object):
        """_convert_to_search_result handles missing optional properties."""
        mock_weaviate_object.properties = {
            "content": "Minimal content",
        }

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        assert result.content == "Minimal content"
        assert result.metadata["doc_id"] == ""
        assert result.metadata["chunk_index"] == 0
        assert result.metadata["namespace"] == ""

    def test_convert_to_search_result_zero_distance(self, retriever, mock_weaviate_object):
        """_convert_to_search_result handles zero distance (exact match)."""
        mock_weaviate_object.metadata.distance = 0.0

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="vector")

        # Score = 1 / (1 + 0) = 1.0
        assert result.score == 1.0

    def test_convert_to_search_result_none_distance(self, retriever, mock_weaviate_object):
        """_convert_to_search_result handles None distance."""
        mock_weaviate_object.metadata.distance = None

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="vector")

        # Score = 1 / (1 + 0) = 1.0 (None treated as 0)
        assert result.score == 1.0

    def test_convert_to_search_result_none_score(self, retriever, mock_weaviate_object):
        """_convert_to_search_result handles None score."""
        mock_weaviate_object.metadata.score = None

        result = retriever._convert_to_search_result(mock_weaviate_object, mode="bm25")

        # None treated as 0.0
        assert result.score == 0.0
