"""Document indexing pipeline.

Orchestrates the complete document indexing pipeline:
1. Load document from storage
2. Clean and preprocess text (using Haystack DocumentCleaner)
3. Split text into chunks (using Haystack DocumentSplitter)
4. Generate embeddings via Embedding Service
5. Store chunks in Weaviate

Uses Haystack library components for text preprocessing while maintaining
our existing gRPC and storage architecture.
"""

import json
import logging
from typing import Any, Literal, Protocol

from haystack import Document
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from minio import Minio

from src.common.metrics import track_latency
from src.common.tracing_utils import trace_storage_operation
from src.indexer.metrics import (
    get_minio_load_duration,
    get_text_cleaning_duration,
    get_text_splitting_duration,
)

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of a document.

    A document chunk is a segment of a larger document with associated metadata.
    Each chunk will be embedded and stored separately for retrieval.

    Chunk IDs are deterministic based on doc_id and chunk_index, enabling
    reproducible evaluation and testing.
    """

    def __init__(
        self,
        content: str,
        doc_id: str,
        chunk_index: int,
        namespace: str,
        metadata: dict[str, Any],
    ) -> None:
        """Initialize a document chunk.

        Args:
            content: Chunk text content
            doc_id: Parent document ID
            chunk_index: Index of this chunk in the document
            namespace: Namespace for multi-tenancy
            metadata: Additional metadata from parent document
        """
        # Deterministic chunk ID for reproducible evaluation
        self.chunk_id = f"{doc_id}-chunk-{chunk_index}"
        self.content = content
        self.doc_id = doc_id
        self.chunk_index = chunk_index
        self.namespace = namespace
        self.metadata = metadata


class DocumentLoader(Protocol):
    """Protocol for loading documents from storage."""

    def load(self, bucket: str, key: str) -> dict[str, Any]:
        """Load document from storage.

        Args:
            bucket: Storage bucket name
            key: Object key

        Returns:
            Document dictionary
        """
        ...


class TextCleaner(Protocol):
    """Protocol for cleaning document text."""

    def clean(self, text: str) -> str:
        """Clean and normalize text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        ...


class TextSplitter(Protocol):
    """Protocol for splitting text into chunks."""

    def split(self, text: str) -> list[str]:
        """Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        ...


class AbstractEmbedder(Protocol):
    """Abstract interface for embedding text into vectors."""

    def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        ...


class ChunkIngestionInterface(Protocol):
    """Abstract interface for ingesting document chunks into storage."""

    def store(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Store chunks with embeddings.

        Args:
            chunks: List of document chunks
            embeddings: Corresponding embedding vectors
        """
        ...


class MinIODocumentLoader:
    """Loads documents from MinIO object storage."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool,
    ) -> None:
        """Initialize MinIO document loader.

        Args:
            endpoint: MinIO endpoint (host:port)
            access_key: Access key
            secret_key: Secret key
            secure: Whether to use HTTPS
        """
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        logger.info(f"✓ MinIO loader initialized (endpoint={endpoint})")

    def load(self, bucket: str, key: str) -> dict[str, Any]:
        """Load document from MinIO.

        Args:
            bucket: MinIO bucket name
            key: Object key

        Returns:
            Document dictionary

        Raises:
            Exception: If document cannot be loaded
        """
        with trace_storage_operation("download", bucket, key) as storage_span:
            try:
                logger.debug(f"Loading document from MinIO: {bucket}/{key}")
                response = self.client.get_object(bucket, key)
                try:
                    data = response.read()
                    storage_span.set_attribute("storage.bytes", len(data))
                    document: dict[str, Any] = json.loads(data.decode("utf-8"))
                    doc_id_log = document["id"] if "id" in document else "unknown"
                    logger.debug(f"✓ Loaded document: {doc_id_log}")
                    return document
                finally:
                    response.close()
                    response.release_conn()

            except Exception as e:
                logger.error(f"Failed to load document {bucket}/{key}: {e}")
                raise


class HaystackTextCleaner:
    """Text cleaning using Haystack's DocumentCleaner.

    Wraps Haystack's DocumentCleaner to provide:
    - Unicode normalization
    - Whitespace normalization
    - Empty line removal

    This is a thin adapter that maintains our TextCleaner protocol interface
    while delegating to Haystack for the actual cleaning.
    """

    def __init__(
        self,
        remove_empty_lines: bool,
        remove_extra_whitespaces: bool,
        unicode_normalization: Literal["NFC", "NFKC", "NFD", "NFKD"] | None,
    ) -> None:
        """Initialize the Haystack-based text cleaner.

        Args:
            remove_empty_lines: Whether to remove empty lines
            remove_extra_whitespaces: Whether to remove extra whitespaces
            unicode_normalization: Unicode normalization form (NFC, NFKC, NFD, NFKD)
        """
        self._cleaner = DocumentCleaner(
            remove_empty_lines=remove_empty_lines,
            remove_extra_whitespaces=remove_extra_whitespaces,
            unicode_normalization=unicode_normalization,
        )
        logger.info("✓ Haystack text cleaner initialized")

    def clean(self, text: str) -> str:
        """Clean and normalize text using Haystack.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Create a Haystack Document, clean it, extract the content
        doc = Document(content=text)
        result = self._cleaner.run(documents=[doc])
        cleaned_docs = result["documents"] if "documents" in result else []

        if not cleaned_docs:
            return ""

        cleaned = cleaned_docs[0].content or ""
        logger.debug(f"Cleaned text: {len(text)} -> {len(cleaned)} chars")
        return cleaned


# Backward compatibility alias
BasicTextCleaner = HaystackTextCleaner


class HaystackTextSplitter:
    """Splits text into chunks using Haystack's DocumentSplitter.

    Uses Haystack's DocumentSplitter for word-based chunking with
    configurable overlap support (which was missing in the original
    implementation).

    This is a thin adapter that maintains our TextSplitter protocol interface
    while delegating to Haystack for the actual splitting.
    """

    def __init__(
        self,
        chunk_size_words: int,
        chunk_overlap_words: int,
    ) -> None:
        """Initialize the Haystack-based text splitter.

        Args:
            chunk_size_words: Target number of words per chunk
            chunk_overlap_words: Number of words to overlap between chunks

        Raises:
            ValueError: If chunk_size_words is not positive
        """
        if chunk_size_words <= 0:
            raise ValueError("chunk_size_words must be positive")

        self.chunk_size_words = chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words

        self._splitter = DocumentSplitter(
            split_by="word",
            split_length=chunk_size_words,
            split_overlap=chunk_overlap_words,
        )
        logger.info(f"✓ Haystack text splitter initialized (chunk_size={chunk_size_words} words, overlap={chunk_overlap_words} words)")

    def split(self, text: str) -> list[str]:
        """Split text into word-based chunks using Haystack.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []

        # Create a Haystack Document, split it, extract the contents
        doc = Document(content=text)
        result = self._splitter.run(documents=[doc])
        split_docs = result["documents"] if "documents" in result else []

        chunks = [d.content for d in split_docs if d.content]

        logger.debug(f"Split text into {len(chunks)} chunks")
        return chunks


# Backward compatibility alias
WordBasedTextSplitter = HaystackTextSplitter


class IndexingPipeline:
    """Document indexing pipeline.

    Coordinates all steps of document indexing:
    1. Load document from storage
    2. Clean text
    3. Split into chunks
    4. Generate embeddings
    5. Store in vector database

    This pipeline follows the Dependency Inversion Principle - it depends
    on abstractions (protocols) rather than concrete implementations.
    """

    def __init__(
        self,
        loader: DocumentLoader,
        cleaner: TextCleaner,
        splitter: TextSplitter,
        embedder: AbstractEmbedder,
        chunk_ingester: ChunkIngestionInterface,
    ) -> None:
        """Initialize indexing pipeline.

        Args:
            loader: Document loader implementation
            cleaner: Text cleaner implementation
            splitter: Text splitter implementation
            embedder: Embedder implementation
            chunk_ingester: Chunk ingestion implementation
        """
        self.loader = loader
        self.cleaner = cleaner
        self.splitter = splitter
        self.embedder = embedder
        self.chunk_ingester = chunk_ingester

        logger.info("✓ Indexing pipeline initialized")

    def process_document(
        self,
        bucket: str,
        key: str,
    ) -> int:
        """Process a document through the indexing pipeline.

        Args:
            bucket: Storage bucket name
            key: Document key in bucket

        Returns:
            Number of chunks created

        Raises:
            Exception: If any pipeline step fails
        """
        # Step 1: Load document
        document = self._load_document(bucket, key)

        # Step 2: Extract and clean text
        cleaned_text = self._clean_text(document)

        # Step 3: Split into chunks
        text_chunks = self._split_text(cleaned_text)

        # Step 4: Create chunk objects
        chunks = self._create_chunks(document, text_chunks)

        # Step 5: Generate embeddings
        embeddings = self._generate_embeddings(chunks)

        # Step 6: Store chunks
        self._store_chunks(chunks, embeddings)

        doc_id_result = document["id"] if "id" in document else "unknown"
        logger.info(f"✓ Processed document {doc_id_result}: {len(chunks)} chunks created")
        return len(chunks)

    def _load_document(self, bucket: str, key: str) -> dict[str, Any]:
        """Load document from storage.

        Args:
            bucket: Storage bucket
            key: Document key

        Returns:
            Document dictionary
        """
        logger.info(f"Loading document: {bucket}/{key}")
        with track_latency(get_minio_load_duration(), None):
            return self.loader.load(bucket, key)

    def _clean_text(self, document: dict[str, Any]) -> str:
        """Extract and clean text from document.

        Args:
            document: Document dictionary

        Returns:
            Cleaned text
        """
        raw_text = document["text"] if "text" in document else ""
        if not raw_text:
            doc_id_for_log = document["id"] if "id" in document else "unknown"
            logger.warning(f"Document {doc_id_for_log} has no text content")
            return ""

        logger.debug("Cleaning document text")
        with track_latency(get_text_cleaning_duration(), None):
            return self.cleaner.clean(raw_text)

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        logger.debug("Splitting text into chunks")
        with track_latency(get_text_splitting_duration(), None):
            return self.splitter.split(text)

    def _create_chunks(
        self,
        document: dict[str, Any],
        text_chunks: list[str],
    ) -> list[DocumentChunk]:
        """Create DocumentChunk objects from text chunks.

        Args:
            document: Original document
            text_chunks: List of text chunks

        Returns:
            List of DocumentChunk objects
        """
        doc_id = document["id"] if "id" in document else "unknown"
        namespace = document["namespace"] if "namespace" in document else "default"
        metadata = document["metadata"] if "metadata" in document else {}

        chunks = [
            DocumentChunk(
                content=text,
                doc_id=doc_id,
                chunk_index=i,
                namespace=namespace,
                metadata=metadata,
            )
            for i, text in enumerate(text_chunks)
        ]

        logger.debug(f"Created {len(chunks)} chunk objects")
        return chunks

    def _generate_embeddings(self, chunks: list[DocumentChunk]) -> list[list[float]]:
        """Generate embeddings for chunks.

        Args:
            chunks: List of document chunks

        Returns:
            List of embedding vectors
        """
        if not chunks:
            return []

        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedder.generate(texts)

        if len(embeddings) != len(chunks):
            raise ValueError(f"Expected {len(chunks)} embeddings, got {len(embeddings)}")

        logger.info(f"✓ Generated {len(embeddings)} embeddings")
        return embeddings

    def _store_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Store chunks and embeddings.

        Args:
            chunks: Document chunks
            embeddings: Embedding vectors
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        logger.info(f"Storing {len(chunks)} chunks")
        self.chunk_ingester.store(chunks, embeddings)
        logger.info(f"✓ Stored {len(chunks)} chunks")
