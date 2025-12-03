"""Tests for the document indexing pipeline."""

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.pipelines.indexing_pipeline import (
    BasicTextCleaner,
    DocumentChunk,
    IndexingPipeline,
    MinIODocumentLoader,
    WordBasedTextSplitter,
)


class TestDocumentChunk:
    """Tests for DocumentChunk class."""

    def test_create_chunk(self):
        """Test creating a document chunk."""
        chunk = DocumentChunk(
            content="Test content",
            doc_id="doc123",
            chunk_index=0,
            namespace="test",
            metadata={"source": "test.txt"},
        )

        assert chunk.content == "Test content"
        assert chunk.doc_id == "doc123"
        assert chunk.chunk_index == 0
        assert chunk.namespace == "test"
        assert chunk.metadata == {"source": "test.txt"}
        assert chunk.chunk_id is not None  # UUID generated

    def test_chunk_id_unique(self):
        """Test that each chunk gets a unique ID."""
        chunk1 = DocumentChunk(
            content="Content 1",
            doc_id="doc1",
            chunk_index=0,
            namespace="test",
            metadata={},
        )
        chunk2 = DocumentChunk(
            content="Content 2",
            doc_id="doc1",
            chunk_index=1,
            namespace="test",
            metadata={},
        )

        assert chunk1.chunk_id != chunk2.chunk_id


class TestBasicTextCleaner:
    """Tests for BasicTextCleaner."""

    def test_clean_text_strips_whitespace(self):
        """Test that cleaner strips leading/trailing whitespace."""
        cleaner = BasicTextCleaner()

        text = "  Test content  \n  "
        cleaned = cleaner.clean(text)

        assert cleaned == "Test content"

    def test_clean_text_removes_empty_lines(self):
        """Test that cleaner removes empty lines."""
        cleaner = BasicTextCleaner()

        text = "Line 1\n\n\nLine 2\n\nLine 3"
        cleaned = cleaner.clean(text)

        assert cleaned == "Line 1\nLine 2\nLine 3"

    def test_clean_text_normalizes_whitespace(self):
        """Test that cleaner normalizes internal whitespace."""
        cleaner = BasicTextCleaner()

        text = "Line 1  \nLine 2\t\n  Line 3"
        cleaned = cleaner.clean(text)

        assert cleaned == "Line 1\nLine 2\nLine 3"

    def test_clean_empty_text(self):
        """Test cleaning empty text."""
        cleaner = BasicTextCleaner()

        cleaned = cleaner.clean("")

        assert cleaned == ""


class TestWordBasedTextSplitter:
    """Tests for WordBasedTextSplitter."""

    def test_split_short_text(self):
        """Test that short text is not split."""
        splitter = WordBasedTextSplitter(chunk_size_words=10)

        text = "This is a short text"
        chunks = splitter.split(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_long_text(self):
        """Test that long text is split into chunks."""
        splitter = WordBasedTextSplitter(chunk_size_words=5)

        # 15 words -> should create 3 chunks
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15"
        chunks = splitter.split(text)

        assert len(chunks) == 3
        assert chunks[0] == "word1 word2 word3 word4 word5"
        assert chunks[1] == "word6 word7 word8 word9 word10"
        assert chunks[2] == "word11 word12 word13 word14 word15"

    def test_split_uneven_chunks(self):
        """Test that uneven text is split correctly."""
        splitter = WordBasedTextSplitter(chunk_size_words=5)

        # 12 words -> should create 3 chunks (5, 5, 2)
        text = "one two three four five six seven eight nine ten eleven twelve"
        chunks = splitter.split(text)

        assert len(chunks) == 3
        assert chunks[0] == "one two three four five"
        assert chunks[1] == "six seven eight nine ten"
        assert chunks[2] == "eleven twelve"

    def test_invalid_chunk_size(self):
        """Test that invalid chunk size raises error."""
        with pytest.raises(ValueError, match="chunk_size_words must be positive"):
            WordBasedTextSplitter(chunk_size_words=0)

        with pytest.raises(ValueError, match="chunk_size_words must be positive"):
            WordBasedTextSplitter(chunk_size_words=-1)


class TestMinIODocumentLoader:
    """Tests for MinIODocumentLoader."""

    @patch("src.pipelines.indexing_pipeline.Minio")
    def test_loader_initialization(self, mock_minio):
        """Test loader initialization."""
        loader = MinIODocumentLoader(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin123",
            secure=False,
        )

        mock_minio.assert_called_once_with(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin123",
            secure=False,
        )

    @patch("src.pipelines.indexing_pipeline.Minio")
    def test_load_document_success(self, mock_minio):
        """Test loading a document successfully."""
        # Setup mock
        mock_response = MagicMock()
        document_data = {
            "id": "doc123",
            "text": "Test document content",
            "metadata": {"source": "test.txt"},
        }
        mock_response.read.return_value = json.dumps(document_data).encode("utf-8")

        mock_client = Mock()
        mock_client.get_object.return_value = mock_response
        mock_minio.return_value = mock_client

        # Test
        loader = MinIODocumentLoader(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin123",
        )
        document = loader.load(bucket="test-bucket", key="test-key")

        # Assertions
        assert document == document_data
        mock_client.get_object.assert_called_once_with("test-bucket", "test-key")
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()

    @patch("src.pipelines.indexing_pipeline.Minio")
    def test_load_document_failure(self, mock_minio):
        """Test loading a document that fails."""
        mock_client = Mock()
        mock_client.get_object.side_effect = Exception("Connection error")
        mock_minio.return_value = mock_client

        loader = MinIODocumentLoader(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin123",
        )

        with pytest.raises(Exception, match="Connection error"):
            loader.load(bucket="test-bucket", key="test-key")


class TestIndexingPipeline:
    """Tests for IndexingPipeline."""

    def test_pipeline_initialization(self):
        """Test pipeline initialization with components."""
        # Create mock components
        loader = Mock()
        cleaner = Mock()
        splitter = Mock()
        embedding_generator = Mock()
        chunk_store = Mock()

        # Initialize pipeline
        pipeline = IndexingPipeline(
            loader=loader,
            cleaner=cleaner,
            splitter=splitter,
            embedding_generator=embedding_generator,
            chunk_store=chunk_store,
        )

        # Verify components are stored
        assert pipeline.loader == loader
        assert pipeline.cleaner == cleaner
        assert pipeline.splitter == splitter
        assert pipeline.embedding_generator == embedding_generator
        assert pipeline.chunk_store == chunk_store

    def test_process_document_success(self):
        """Test processing a document through the pipeline."""
        # Setup mock components
        loader = Mock()
        document = {
            "id": "doc123",
            "text": "This is test content for the document",
            "namespace": "test",
            "metadata": {"source": "test.txt"},
        }
        loader.load.return_value = document

        cleaner = Mock()
        cleaner.clean.return_value = "This is test content for the document"

        splitter = Mock()
        splitter.split.return_value = ["This is test", "content for the", "document"]

        embedding_generator = Mock()
        embedding_generator.generate.return_value = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ]

        chunk_store = Mock()

        # Create pipeline
        pipeline = IndexingPipeline(
            loader=loader,
            cleaner=cleaner,
            splitter=splitter,
            embedding_generator=embedding_generator,
            chunk_store=chunk_store,
        )

        # Process document
        num_chunks = pipeline.process_document(bucket="test-bucket", key="test-key")

        # Verify pipeline steps
        loader.load.assert_called_once_with("test-bucket", "test-key")
        cleaner.clean.assert_called_once_with("This is test content for the document")
        splitter.split.assert_called_once_with("This is test content for the document")
        embedding_generator.generate.assert_called_once()
        chunk_store.store.assert_called_once()

        # Verify result
        assert num_chunks == 3

        # Verify chunks created correctly
        stored_chunks, stored_embeddings = chunk_store.store.call_args[0]
        assert len(stored_chunks) == 3
        assert len(stored_embeddings) == 3

        # Check first chunk
        assert stored_chunks[0].content == "This is test"
        assert stored_chunks[0].doc_id == "doc123"
        assert stored_chunks[0].chunk_index == 0
        assert stored_chunks[0].namespace == "test"

    def test_process_document_empty_text(self):
        """Test processing a document with empty text."""
        # Setup mock components
        loader = Mock()
        document = {
            "id": "doc123",
            "text": "",
            "namespace": "test",
            "metadata": {},
        }
        loader.load.return_value = document

        cleaner = Mock()
        cleaner.clean.return_value = ""

        splitter = Mock()
        splitter.split.return_value = []

        embedding_generator = Mock()
        embedding_generator.generate.return_value = []

        chunk_store = Mock()

        # Create pipeline
        pipeline = IndexingPipeline(
            loader=loader,
            cleaner=cleaner,
            splitter=splitter,
            embedding_generator=embedding_generator,
            chunk_store=chunk_store,
        )

        # Process document
        num_chunks = pipeline.process_document(bucket="test-bucket", key="test-key")

        # Verify result
        assert num_chunks == 0
        chunk_store.store.assert_called_once()

    def test_process_document_embedding_mismatch(self):
        """Test that mismatched embeddings raise an error."""
        # Setup mock components
        loader = Mock()
        loader.load.return_value = {
            "id": "doc123",
            "text": "Test content",
            "namespace": "test",
            "metadata": {},
        }

        cleaner = Mock()
        cleaner.clean.return_value = "Test content"

        splitter = Mock()
        splitter.split.return_value = ["Test", "content"]

        embedding_generator = Mock()
        # Return wrong number of embeddings
        embedding_generator.generate.return_value = [[0.1, 0.2, 0.3]]

        chunk_store = Mock()

        # Create pipeline
        pipeline = IndexingPipeline(
            loader=loader,
            cleaner=cleaner,
            splitter=splitter,
            embedding_generator=embedding_generator,
            chunk_store=chunk_store,
        )

        # Should raise error due to mismatch
        with pytest.raises(ValueError, match="Expected 2 embeddings, got 1"):
            pipeline.process_document(bucket="test-bucket", key="test-key")

    def test_process_document_no_text_field(self):
        """Test processing a document without text field."""
        # Setup mock components
        loader = Mock()
        document = {
            "id": "doc123",
            "namespace": "test",
            "metadata": {},
            # Missing "text" field
        }
        loader.load.return_value = document

        cleaner = Mock()
        cleaner.clean.return_value = ""

        splitter = Mock()
        splitter.split.return_value = []

        embedding_generator = Mock()
        embedding_generator.generate.return_value = []

        chunk_store = Mock()

        # Create pipeline
        pipeline = IndexingPipeline(
            loader=loader,
            cleaner=cleaner,
            splitter=splitter,
            embedding_generator=embedding_generator,
            chunk_store=chunk_store,
        )

        # Process document (should handle missing text gracefully)
        num_chunks = pipeline.process_document(bucket="test-bucket", key="test-key")

        # Verify result
        assert num_chunks == 0
