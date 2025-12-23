"""Tests for the indexer and its adapters."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.indexer.processor import (
    BatchEmbedder,
    DocumentIndexer,
    WeaviateBatchInserter,
)
from src.pipelines.indexing_pipeline import DocumentChunk


class TestBatchEmbedder:
    """Tests for BatchEmbedder adapter."""

    def test_initialization(self):
        """Test embedder initialization."""
        mock_client = Mock()
        embedder = BatchEmbedder(
            client=mock_client,
            model="text-embedding-3-small",
            namespace="test",
            batch_size=32,
        )

        assert embedder.client == mock_client
        assert embedder.model == "text-embedding-3-small"
        assert embedder.namespace == "test"
        assert embedder.batch_size == 32

    def test_generate_empty_input(self):
        """Test generating embeddings with empty input."""
        mock_client = Mock()
        embedder = BatchEmbedder(
            client=mock_client,
            model="test-model",
            namespace="test",
            batch_size=10,
        )

        embeddings = embedder.generate([])

        assert embeddings == []
        mock_client.embed_batch.assert_not_called()

    def test_generate_single_batch(self):
        """Test generating embeddings within single batch."""
        mock_client = Mock()
        mock_client.embed_batch.return_value = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]

        embedder = BatchEmbedder(
            client=mock_client,
            model="test-model",
            namespace="test",
            batch_size=10,
        )

        texts = ["text1", "text2"]
        embeddings = embedder.generate(texts)

        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]

        mock_client.embed_batch.assert_called_once_with(
            texts=texts,
            model="test-model",
            namespace="test",
        )

    def test_generate_multiple_batches(self):
        """Test generating embeddings across multiple batches."""
        mock_client = Mock()
        # Mock returns different embeddings for each batch
        mock_client.embed_batch.side_effect = [
            [[0.1, 0.2], [0.3, 0.4]],  # Batch 1
            [[0.5, 0.6], [0.7, 0.8]],  # Batch 2
            [[0.9, 1.0]],  # Batch 3
        ]

        embedder = BatchEmbedder(
            client=mock_client,
            model="test-model",
            namespace="test",
            batch_size=2,  # Small batch size to force multiple batches
        )

        texts = ["text1", "text2", "text3", "text4", "text5"]
        embeddings = embedder.generate(texts)

        # Should have all embeddings from all batches
        assert len(embeddings) == 5
        assert embeddings[0] == [0.1, 0.2]
        assert embeddings[1] == [0.3, 0.4]
        assert embeddings[2] == [0.5, 0.6]
        assert embeddings[3] == [0.7, 0.8]
        assert embeddings[4] == [0.9, 1.0]

        # Should have called embed_batch 3 times
        assert mock_client.embed_batch.call_count == 3

    def test_generate_batch_size_boundary(self):
        """Test generating embeddings at exact batch size boundary."""
        mock_client = Mock()
        mock_client.embed_batch.side_effect = [
            [[0.1], [0.2], [0.3]],
            [[0.4], [0.5], [0.6]],
        ]

        embedder = BatchEmbedder(
            client=mock_client,
            model="test-model",
            namespace="test",
            batch_size=3,
        )

        texts = ["t1", "t2", "t3", "t4", "t5", "t6"]
        embeddings = embedder.generate(texts)

        assert len(embeddings) == 6
        assert mock_client.embed_batch.call_count == 2


class TestWeaviateBatchInserter:
    """Tests for WeaviateBatchInserter adapter."""

    def test_initialization(self):
        """Test inserter initialization."""
        mock_client = Mock()
        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        assert inserter.client == mock_client
        assert inserter.collection_name == "TestCollection"

    def test_store_empty_chunks(self):
        """Test storing empty chunk list."""
        mock_client = Mock()
        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        # Should not raise error
        inserter.store(chunks=[], embeddings=[])

        # Should not access collection for empty input
        mock_client.collections.get.assert_not_called()

    def test_store_mismatched_lengths(self):
        """Test that mismatched chunks and embeddings raise error."""
        mock_client = Mock()
        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        chunks = [
            DocumentChunk(
                content="Test 1",
                doc_id="doc1",
                chunk_index=0,
                namespace="test",
                metadata={},
            )
        ]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]  # Mismatched!

        with pytest.raises(ValueError, match="Number of chunks and embeddings must match"):
            inserter.store(chunks=chunks, embeddings=embeddings)

    def test_store_success(self):
        """Test successfully storing chunks."""
        # Setup mocks
        mock_collection = Mock()
        mock_batch = MagicMock()
        mock_batch.__enter__ = Mock(return_value=mock_batch)
        mock_batch.__exit__ = Mock(return_value=False)
        mock_collection.batch.dynamic.return_value = mock_batch

        mock_client = Mock()
        mock_client.collections.get.return_value = mock_collection

        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        # Create test data
        chunks = [
            DocumentChunk(
                content="Test content 1",
                doc_id="doc123",
                chunk_index=0,
                namespace="test",
                metadata={"source_file": "test.txt", "title": "Test Doc"},
            ),
            DocumentChunk(
                content="Test content 2",
                doc_id="doc123",
                chunk_index=1,
                namespace="test",
                metadata={"source_file": "test.txt", "title": "Test Doc"},
            ),
        ]
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        # Store chunks
        inserter.store(chunks=chunks, embeddings=embeddings)

        # Verify collection was accessed
        mock_client.collections.get.assert_called_once_with("TestCollection")

        # Verify batch operations
        mock_collection.batch.dynamic.assert_called_once()
        assert mock_batch.add_object.call_count == 2

        # Verify first chunk data
        first_call = mock_batch.add_object.call_args_list[0]
        assert first_call[1]["properties"]["content"] == "Test content 1"
        assert first_call[1]["properties"]["doc_id"] == "doc123"
        assert first_call[1]["properties"]["chunk_index"] == 0
        assert first_call[1]["properties"]["namespace"] == "test"
        assert first_call[1]["properties"]["source"] == "test.txt"
        assert first_call[1]["properties"]["title"] == "Test Doc"
        assert first_call[1]["vector"] == [0.1, 0.2, 0.3]

    def test_store_metadata_serialization(self):
        """Test that metadata is properly serialized to JSON."""
        mock_collection = Mock()
        mock_batch = MagicMock()
        mock_batch.__enter__ = Mock(return_value=mock_batch)
        mock_batch.__exit__ = Mock(return_value=False)
        mock_collection.batch.dynamic.return_value = mock_batch

        mock_client = Mock()
        mock_client.collections.get.return_value = mock_collection

        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        chunks = [
            DocumentChunk(
                content="Test",
                doc_id="doc1",
                chunk_index=0,
                namespace="test",
                metadata={"key": "value", "nested": {"data": 123}},
            )
        ]
        embeddings = [[0.1, 0.2]]

        inserter.store(chunks=chunks, embeddings=embeddings)

        # Verify metadata_json is serialized
        call_args = mock_batch.add_object.call_args_list[0]
        metadata_json = call_args[1]["properties"]["metadata_json"]
        assert isinstance(metadata_json, str)
        parsed = json.loads(metadata_json)
        assert parsed == {"key": "value", "nested": {"data": 123}}


class TestDocumentIndexer:
    """Tests for DocumentIndexer class."""

    @pytest.fixture
    def indexer_config(self):
        """Create a valid IndexerConfig for testing."""
        from src.indexer.config import IndexerConfig

        return IndexerConfig(
            service_name="indexer-test",
            log_level="INFO",
            port=8080,
            environment="test",
            minio_endpoint="localhost:9000",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin123",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://weaviate:8080",
            weaviate_timeout_init=30,
            weaviate_timeout_query=60,
            weaviate_timeout_insert=120,
            embedding_service_addr="embedding-service:50051",
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            kafka_group_id="indexer-group",
            kafka_auto_offset_reset="earliest",
            datasets_config_path="config/test/datasets_config.yaml",
            batch_size=10,
            health_port=8081,
            embedding_service_timeout=30.0,
        )

    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    def test_initialization(self, mock_embedding_client_class, indexer_config):
        """Test indexer initialization."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        indexer = DocumentIndexer(config)

        # Verify components initialized
        assert indexer.config == config
        assert indexer.weaviate_client is None  # Lazy init
        assert indexer.embedding_client == mock_client_instance

        # Verify embedding client was connected
        mock_client_instance.connect.assert_called_once()

    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    def test_context_manager(self, mock_embedding_client_class, indexer_config):
        """Test indexer as context manager."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        with DocumentIndexer(config) as indexer:
            assert indexer is not None

        # Verify close was called
        mock_client_instance.close.assert_called_once()

    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    def test_get_weaviate_client_lazy_init(
        self,
        mock_embedding_client_class,
        mock_weaviate_connect,
        indexer_config,
    ):
        """Test lazy Weaviate client initialization."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        mock_weaviate_client = Mock()
        mock_weaviate_connect.return_value = mock_weaviate_client

        indexer = DocumentIndexer(config)

        # Initially None
        assert indexer.weaviate_client is None

        # Get client (triggers connection)
        client = indexer._get_weaviate_client()

        # Verify connection was made
        assert client == mock_weaviate_client
        assert indexer.weaviate_client == mock_weaviate_client
        mock_weaviate_connect.assert_called_once()
        call_kwargs = mock_weaviate_connect.call_args.kwargs
        assert call_kwargs["http_host"] == "weaviate"
        assert call_kwargs["http_port"] == 8080
        assert call_kwargs["http_secure"] is False
        assert call_kwargs["grpc_host"] == "weaviate"
        assert call_kwargs["grpc_port"] == 50051
        assert call_kwargs["grpc_secure"] is False
        assert "additional_config" in call_kwargs

        # Second call should not reconnect
        client2 = indexer._get_weaviate_client()
        assert client2 == mock_weaviate_client
        assert mock_weaviate_connect.call_count == 1  # Still only 1 call

    @patch("src.indexer.processor.asyncio.to_thread")
    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_document_already_indexed(
        self, mock_embedding_client_class, mock_weaviate_connect, mock_to_thread, indexer_config
    ):
        """Test processing event for already indexed document."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        # Setup Weaviate mock with existing document
        mock_collection = Mock()
        mock_existing_result = Mock()
        mock_existing_result.objects = [Mock()]  # Document exists
        mock_collection.query.fetch_objects.return_value = mock_existing_result

        mock_weaviate_client = Mock()
        mock_weaviate_client.collections.get.return_value = mock_collection
        mock_weaviate_connect.return_value = mock_weaviate_client

        # Make to_thread execute synchronously for testing
        async def async_execute(func, *args, **kwargs):
            return func(*args, **kwargs)

        mock_to_thread.side_effect = async_execute

        indexer = DocumentIndexer(config)

        # Process event for document that already exists
        event = {
            "event_type": "document.ingested",
            "document_id": "doc123",
            "namespace": "test-ns",
            "minio_bucket": "documents",
            "minio_key": "doc123.json",
        }

        await indexer.process_event(event)

        # Verify that it checked for existing document and skipped processing
        mock_collection.query.fetch_objects.assert_called_once()

    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_unknown_type(self, mock_embedding_client_class, indexer_config):
        """Test processing event with unknown event type."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        indexer = DocumentIndexer(config)

        # Process event with unknown type
        event = {
            "event_type": "unknown.event.type",
            "document_id": "doc123",
            "namespace": "test-ns",
        }

        # Should return early without error
        result = await indexer.process_event(event)
        assert result["skipped"] is True
        assert result["reason"] == "unknown_event_type"

        # No Weaviate connection should be made
        assert indexer.weaviate_client is None

    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    def test_get_weaviate_client_url_without_port(
        self,
        mock_embedding_client_class,
        mock_weaviate_connect,
    ):
        """Test Weaviate client initialization with URL without port."""
        from src.indexer.config import IndexerConfig

        # Create config with URL without port
        config = IndexerConfig(
            service_name="indexer-test",
            log_level="INFO",
            port=8080,
            environment="test",
            minio_endpoint="localhost:9000",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin123",
            minio_bucket="test-bucket",
            minio_secure=False,
            weaviate_url="http://weaviate",  # No port!
            weaviate_timeout_init=30,
            weaviate_timeout_query=60,
            weaviate_timeout_insert=120,
            embedding_service_addr="embedding-service:50051",
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            kafka_group_id="indexer-group",
            kafka_auto_offset_reset="earliest",
            datasets_config_path="config/test/datasets_config.yaml",
            batch_size=10,
            health_port=8081,
            embedding_service_timeout=30.0,
        )

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        mock_weaviate_client = Mock()
        mock_weaviate_connect.return_value = mock_weaviate_client

        indexer = DocumentIndexer(config)
        client = indexer._get_weaviate_client()

        # Verify client was returned
        assert client == mock_weaviate_client

        # Verify default port 8080 is used
        mock_weaviate_connect.assert_called_once()
        call_kwargs = mock_weaviate_connect.call_args.kwargs
        assert call_kwargs["http_host"] == "weaviate"
        assert call_kwargs["http_port"] == 8080
        assert call_kwargs["http_secure"] is False
        assert call_kwargs["grpc_host"] == "weaviate"
        assert call_kwargs["grpc_port"] == 50051
        assert call_kwargs["grpc_secure"] is False
        assert "additional_config" in call_kwargs

    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    def test_close_with_weaviate_client(self, mock_embedding_client_class, mock_weaviate_connect, indexer_config):
        """Test closing indexer with Weaviate client connected."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        mock_weaviate_client = Mock()
        mock_weaviate_connect.return_value = mock_weaviate_client

        indexer = DocumentIndexer(config)

        # Connect to Weaviate
        client = indexer._get_weaviate_client()
        assert client == mock_weaviate_client

        # Close indexer
        indexer.close()

        # Verify both clients are closed
        mock_client_instance.close.assert_called_once()
        mock_weaviate_client.close.assert_called_once()

    @patch("src.indexer.processor.IndexingPipeline")
    @patch("src.indexer.processor.asyncio.to_thread")
    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_new_document(
        self, mock_embedding_client_class, mock_weaviate_connect, mock_to_thread, mock_pipeline_class, indexer_config
    ):
        """Test processing event for new document."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        # Setup Weaviate mock with no existing document
        mock_collection = Mock()
        mock_existing_result = Mock()
        mock_existing_result.objects = []  # No existing document
        mock_collection.query.fetch_objects.return_value = mock_existing_result

        mock_weaviate_client = Mock()
        mock_weaviate_client.collections.get.return_value = mock_collection
        mock_weaviate_connect.return_value = mock_weaviate_client

        # Make to_thread execute synchronously for testing
        call_count = 0

        async def async_execute(func, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call is fetch_objects
                return func(*args, **kwargs)
            else:
                # Second call is pipeline.process_document
                return 5  # Number of chunks

        mock_to_thread.side_effect = async_execute

        # Setup pipeline mock
        mock_pipeline = Mock()
        mock_pipeline.process_document.return_value = 5
        mock_pipeline_class.return_value = mock_pipeline

        indexer = DocumentIndexer(config)

        # Process event for new document
        event = {
            "event_type": "document.ingested",
            "document_id": "doc123",
            "namespace": "test-ns",
            "minio_bucket": "documents",
            "minio_key": "doc123.json",
        }

        await indexer.process_event(event)

        # Verify document was processed
        assert mock_to_thread.call_count == 2

    @patch("src.indexer.processor.asyncio.to_thread")
    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_raises_on_error(self, mock_embedding_client_class, mock_weaviate_connect, mock_to_thread, indexer_config):
        """Test processing event raises error on failure."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        # Setup Weaviate mock
        mock_weaviate_client = Mock()
        mock_weaviate_connect.return_value = mock_weaviate_client

        # Make to_thread raise an exception
        async def raise_error(func, *args, **kwargs):
            raise RuntimeError("Processing failed")

        mock_to_thread.side_effect = raise_error

        indexer = DocumentIndexer(config)

        event = {
            "event_type": "document.ingested",
            "document_id": "doc123",
            "namespace": "test-ns",
            "minio_bucket": "documents",
            "minio_key": "doc123.json",
        }

        with pytest.raises(RuntimeError, match="Processing failed"):
            await indexer.process_event(event)

    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_missing_namespace(self, mock_embedding_client_class, indexer_config):
        """Test processing event with missing namespace field."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        indexer = DocumentIndexer(config)

        # Process event without namespace field
        event = {
            "event_type": "document.ingested",
            "document_id": "doc123",
            # Missing "namespace" field
            "minio_bucket": "documents",
            "minio_key": "doc123.json",
        }

        with pytest.raises(ValueError, match="Event missing required 'namespace' field"):
            await indexer.process_event(event)

    @patch("src.indexer.processor.asyncio.to_thread")
    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_unknown_namespace(
        self, mock_embedding_client_class, mock_weaviate_connect, mock_to_thread, indexer_config
    ):
        """Test processing event with unknown namespace."""
        config = indexer_config

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        mock_weaviate_client = Mock()
        mock_weaviate_connect.return_value = mock_weaviate_client

        indexer = DocumentIndexer(config)

        # Process event with unknown namespace
        event = {
            "event_type": "document.ingested",
            "document_id": "doc123",
            "namespace": "unknown_namespace_that_does_not_exist",
            "minio_bucket": "documents",
            "minio_key": "doc123.json",
        }

        with pytest.raises(ValueError, match="Unknown namespace"):
            await indexer.process_event(event)


class TestWeaviateBatchInserterEdgeCases:
    """Tests for WeaviateBatchInserter edge cases."""

    def test_store_missing_source_metadata(self):
        """Test storing chunks with missing source_file metadata."""
        mock_collection = Mock()
        mock_batch = MagicMock()
        mock_batch.__enter__ = Mock(return_value=mock_batch)
        mock_batch.__exit__ = Mock(return_value=False)
        mock_collection.batch.dynamic.return_value = mock_batch

        mock_client = Mock()
        mock_client.collections.get.return_value = mock_collection

        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        # Create chunk without source_file in metadata
        chunks = [
            DocumentChunk(
                content="Test content",
                doc_id="doc123",
                chunk_index=0,
                namespace="test",
                metadata={"title": "Test Doc"},  # No source_file
            )
        ]
        embeddings = [[0.1, 0.2, 0.3]]

        inserter.store(chunks=chunks, embeddings=embeddings)

        # Verify source is empty string when missing
        call_args = mock_batch.add_object.call_args_list[0]
        assert call_args[1]["properties"]["source"] == ""
        assert call_args[1]["properties"]["title"] == "Test Doc"

    def test_store_missing_title_metadata(self):
        """Test storing chunks with missing title metadata."""
        mock_collection = Mock()
        mock_batch = MagicMock()
        mock_batch.__enter__ = Mock(return_value=mock_batch)
        mock_batch.__exit__ = Mock(return_value=False)
        mock_collection.batch.dynamic.return_value = mock_batch

        mock_client = Mock()
        mock_client.collections.get.return_value = mock_collection

        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        # Create chunk without title in metadata
        chunks = [
            DocumentChunk(
                content="Test content",
                doc_id="doc123",
                chunk_index=0,
                namespace="test",
                metadata={"source_file": "test.txt"},  # No title
            )
        ]
        embeddings = [[0.1, 0.2, 0.3]]

        inserter.store(chunks=chunks, embeddings=embeddings)

        # Verify title is empty string when missing
        call_args = mock_batch.add_object.call_args_list[0]
        assert call_args[1]["properties"]["source"] == "test.txt"
        assert call_args[1]["properties"]["title"] == ""

    def test_store_missing_both_metadata_fields(self):
        """Test storing chunks with both source_file and title missing."""
        mock_collection = Mock()
        mock_batch = MagicMock()
        mock_batch.__enter__ = Mock(return_value=mock_batch)
        mock_batch.__exit__ = Mock(return_value=False)
        mock_collection.batch.dynamic.return_value = mock_batch

        mock_client = Mock()
        mock_client.collections.get.return_value = mock_collection

        inserter = WeaviateBatchInserter(
            client=mock_client,
            collection_name="TestCollection",
        )

        # Create chunk with minimal metadata
        chunks = [
            DocumentChunk(
                content="Test content",
                doc_id="doc123",
                chunk_index=0,
                namespace="test",
                metadata={},  # Empty metadata
            )
        ]
        embeddings = [[0.1, 0.2, 0.3]]

        inserter.store(chunks=chunks, embeddings=embeddings)

        # Verify both fields are empty strings when missing
        call_args = mock_batch.add_object.call_args_list[0]
        assert call_args[1]["properties"]["source"] == ""
        assert call_args[1]["properties"]["title"] == ""
