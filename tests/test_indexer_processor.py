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
            batch_size=32,
        )

        assert embedder.client == mock_client
        assert embedder.model == "text-embedding-3-small"
        assert embedder.batch_size == 32

    def test_generate_empty_input(self):
        """Test generating embeddings with empty input."""
        mock_client = Mock()
        embedder = BatchEmbedder(
            client=mock_client,
            model="test-model",
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

    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    def test_initialization(self, mock_embedding_client_class):
        """Test indexer initialization."""
        from src.indexer.config import IndexerConfig

        config = IndexerConfig(
            minio_endpoint="localhost:9000",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin123",
            minio_secure=False,
            weaviate_url="http://weaviate:8080",
            weaviate_class="TestCollection",
            embedding_service_addr="embedding-service:50051",
            embedding_model="test-model",
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            batch_size=10,
            chunk_size=500,
        )

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
    def test_context_manager(self, mock_embedding_client_class):
        """Test indexer as context manager."""
        from src.indexer.config import IndexerConfig

        config = IndexerConfig(
            minio_endpoint="localhost:9000",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin123",
            minio_secure=False,
            weaviate_url="http://weaviate:8080",
            weaviate_class="TestCollection",
            embedding_service_addr="embedding-service:50051",
            embedding_model="test-model",
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            batch_size=10,
            chunk_size=500,
        )

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
    ):
        """Test lazy Weaviate client initialization."""
        from src.indexer.config import IndexerConfig

        config = IndexerConfig(
            minio_endpoint="localhost:9000",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin123",
            minio_secure=False,
            weaviate_url="http://weaviate:8080",
            weaviate_class="TestCollection",
            embedding_service_addr="embedding-service:50051",
            embedding_model="test-model",
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            batch_size=10,
            chunk_size=500,
        )

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
        mock_weaviate_connect.assert_called_once_with(
            http_host="weaviate",
            http_port=8080,
            http_secure=False,
            grpc_host="weaviate",
            grpc_port=50051,
            grpc_secure=False,
        )

        # Second call should not reconnect
        client2 = indexer._get_weaviate_client()
        assert client2 == mock_weaviate_client
        assert mock_weaviate_connect.call_count == 1  # Still only 1 call

    @patch("src.indexer.processor.asyncio.to_thread")
    @patch("src.indexer.processor.weaviate.connect_to_custom")
    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_document_already_indexed(
        self,
        mock_embedding_client_class,
        mock_weaviate_connect,
        mock_to_thread,
    ):
        """Test processing event for already indexed document."""
        from src.indexer.config import IndexerConfig

        config = IndexerConfig(
            minio_endpoint="localhost:9000",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin123",
            minio_secure=False,
            weaviate_url="http://weaviate:8080",
            weaviate_class="TestCollection",
            embedding_service_addr="embedding-service:50051",
            embedding_model="test-model",
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            batch_size=10,
            chunk_size=500,
        )

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
            "namespace": "test",
            "minio_bucket": "documents",
            "minio_key": "doc123.json",
        }

        await indexer.process_event(event)

        # Verify that it checked for existing document and skipped processing
        mock_collection.query.fetch_objects.assert_called_once()

    @patch("src.indexer.processor.GrpcEmbeddingServiceClient")
    @pytest.mark.asyncio
    async def test_process_event_unknown_type(
        self,
        mock_embedding_client_class,
    ):
        """Test processing event with unknown event type."""
        from src.indexer.config import IndexerConfig

        config = IndexerConfig(
            minio_endpoint="localhost:9000",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin123",
            minio_secure=False,
            weaviate_url="http://weaviate:8080",
            weaviate_class="TestCollection",
            embedding_service_addr="embedding-service:50051",
            embedding_model="test-model",
            kafka_bootstrap="kafka:9092",
            kafka_topic="test-topic",
            batch_size=10,
            chunk_size=500,
        )

        mock_client_instance = Mock()
        mock_embedding_client_class.return_value = mock_client_instance

        indexer = DocumentIndexer(config)

        # Process event with unknown type
        event = {
            "event_type": "unknown.event.type",
            "document_id": "doc123",
        }

        # Should return early without error
        await indexer.process_event(event)

        # No Weaviate connection should be made
        assert indexer.weaviate_client is None
