"""Document processing and indexing logic."""

import asyncio
import json
import logging
import threading
import uuid
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Dict, Generator, List

import redis
import weaviate
from minio import Minio

from src.indexer.config import IndexerConfig
from src.indexer.grpc_clients import EmbeddingServiceClient

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of a document."""

    def __init__(
        self,
        content: str,
        doc_id: str,
        chunk_index: int,
        namespace: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Initialize a document chunk.

        Args:
            content: Chunk text content
            doc_id: Parent document ID
            chunk_index: Index of this chunk in the document
            namespace: Namespace for multi-tenancy
            metadata: Additional metadata
        """
        self.chunk_id = str(uuid.uuid4())
        self.content = content
        self.doc_id = doc_id
        self.chunk_index = chunk_index
        self.namespace = namespace
        self.metadata = metadata


class DocumentProcessor:
    """Processes documents: chunking, embedding, and storing.

    This class handles the complete document processing pipeline:
    1. Load document from MinIO
    2. Chunk the document text
    3. Generate embeddings via Embedding Service
    4. Store chunks and embeddings in Weaviate
    """

    def __init__(self, config: IndexerConfig) -> None:
        """Initialize the document processor.

        Args:
            config: Indexer configuration
        """
        self.config = config

        # Initialize MinIO client
        self.minio_client = Minio(
            endpoint=config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=config.minio_secure,
        )

        # Weaviate client (initialized lazily)
        self.weaviate_client = None
        self._weaviate_lock = threading.Lock()  # Thread-safe lazy init

        # Initialize Redis client for distributed locking
        self.redis_client = redis.Redis.from_url(
            config.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )

        # Initialize Embedding Service client
        self.embedding_client = EmbeddingServiceClient(address=config.embedding_service_addr)
        self.embedding_client.connect()

        logger.info("✓ Document processor initialized")

    def __enter__(self) -> "DocumentProcessor":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit."""
        self.close()

    def _ensure_weaviate_connected(self) -> None:
        """Ensure Weaviate client is connected (thread-safe lazy initialization)."""
        # Fast path: check without lock (common case)
        if self.weaviate_client is not None:
            return

        # Slow path: acquire lock and connect
        with self._weaviate_lock:
            # Double-check inside lock (another thread may have connected)
            if self.weaviate_client is not None:
                return

            logger.info("Connecting to Weaviate...")

            # Parse URL correctly
            url = self.config.weaviate_url
            if "://" in url:
                url = url.split("://")[1]  # Remove protocol

            # Split host and port if present
            if ":" in url:
                host, port_str = url.rsplit(":", 1)
                port = int(port_str)
            else:
                host = url
                port = 8080

            # Connect (only one thread will reach here)
            self.weaviate_client = weaviate.connect_to_custom(
                http_host=host,
                http_port=port,
                http_secure=False,
                grpc_host=host,
                grpc_port=50051,
                grpc_secure=False,
            )
            logger.info(f"✓ Connected to Weaviate at {host}:{port}")

    @contextmanager
    def document_lock(self, document_id: str) -> Generator[None, None, None]:
        """Acquire distributed lock for document processing.

        Uses Redis to ensure only one indexer replica processes a document at a time.

        Args:
            document_id: Document ID to lock

        Yields:
            None

        Raises:
            TimeoutError: If lock cannot be acquired within timeout
        """
        lock_key = f"indexer:lock:{document_id}"
        lock = self.redis_client.lock(
            lock_key,
            timeout=self.config.redis_lock_timeout,
            blocking_timeout=10,
        )

        acquired = lock.acquire(blocking=True)
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for document {document_id} within 10 seconds")

        try:
            logger.debug(f"Acquired lock for document {document_id}")
            yield
        finally:
            try:
                lock.release()
                logger.debug(f"Released lock for document {document_id}")
            except redis.exceptions.LockError:
                # Lock already released or expired
                logger.warning(f"Lock for document {document_id} already released")

    def close(self) -> None:
        """Close connections."""
        if self.embedding_client:
            self.embedding_client.close()
        if self.weaviate_client:
            self.weaviate_client.close()

    def load_document(self, bucket: str, key: str) -> Dict[str, Any]:
        """Load document from MinIO.

        Args:
            bucket: MinIO bucket name
            key: Object key

        Returns:
            Document dictionary

        Raises:
            Exception: If document cannot be loaded
        """
        try:
            logger.info(f"Loading document: {bucket}/{key}")
            response = self.minio_client.get_object(bucket, key)
            try:
                data = response.read()
                document = json.loads(data.decode("utf-8"))
                logger.info(f"✓ Loaded document: {document.get('id')}")
                return document
            finally:
                # Always clean up connection
                response.close()
                response.release_conn()

        except Exception as e:
            logger.error(f"Failed to load document {bucket}/{key}: {e}")
            raise

    def chunk_text(self, text: str) -> List[str]:
        """Chunk text into segments based on word count.

        Uses a simple word-based chunking strategy: splits text into chunks
        of approximately 100 words each (configurable via chunk_size).

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        # Split text into words (whitespace-separated)
        words = text.split()

        # Use chunk_size as word count (default 500 chars ~= 100 words)
        # Rough estimate: 1 word = ~5 characters
        chunk_word_count = max(1, self.config.chunk_size // 5)

        if len(words) <= chunk_word_count:
            return [text]

        chunks = []
        for i in range(0, len(words), chunk_word_count):
            chunk_words = words[i : i + chunk_word_count]
            chunk = " ".join(chunk_words)
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} chunks from {len(words)} words ({chunk_word_count} words per chunk)")
        return chunks

    def create_chunks(self, document: Dict[str, Any]) -> List[DocumentChunk]:
        """Create document chunks.

        Args:
            document: Document dictionary

        Returns:
            List of DocumentChunk objects
        """
        text = document.get("text", "")
        doc_id = document.get("id")
        namespace = document.get("namespace", "default")
        metadata = document.get("metadata", {})

        text_chunks = self.chunk_text(text)

        chunks = [
            DocumentChunk(
                content=chunk_text,
                doc_id=doc_id,
                chunk_index=i,
                namespace=namespace,
                metadata=metadata,
            )
            for i, chunk_text in enumerate(text_chunks)
        ]

        logger.info(f"Created {len(chunks)} chunks for document {doc_id}")
        return chunks

    def embed_chunks(self, chunks: List[DocumentChunk]) -> List[List[float]]:
        """Generate embeddings for chunks.

        Args:
            chunks: List of document chunks

        Returns:
            List of embedding vectors
        """
        texts = [chunk.content for chunk in chunks]

        # Process in batches
        batch_size = self.config.batch_size
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            logger.info(f"Generating embeddings for batch {i // batch_size + 1} ({len(batch)} chunks)")

            embeddings = self.embedding_client.embed_batch(
                texts=batch,
                model=self.config.embedding_model,
            )
            all_embeddings.extend(embeddings)

        logger.info(f"✓ Generated {len(all_embeddings)} embeddings")
        return all_embeddings

    def store_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        """Store chunks and embeddings in Weaviate.

        Args:
            chunks: List of document chunks
            embeddings: List of embedding vectors
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        # Ensure Weaviate is connected
        self._ensure_weaviate_connected()

        collection = self.weaviate_client.collections.get(self.config.weaviate_class)

        # Prepare objects for batch insertion
        objects = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            obj = {
                "content": chunk.content,
                "doc_id": chunk.doc_id,
                "chunk_index": chunk.chunk_index,
                "namespace": chunk.namespace,
                "source": chunk.metadata.get("source_file", ""),
                "title": chunk.metadata.get("title", ""),
                "metadata_json": json.dumps(chunk.metadata),
            }
            objects.append((obj, embedding))

        # Batch insert
        logger.info(f"Storing {len(objects)} chunks in Weaviate...")
        with collection.batch.dynamic() as batch:
            for obj, vector in objects:
                batch.add_object(properties=obj, vector=vector)

        logger.info(f"✓ Stored {len(objects)} chunks in Weaviate")

    async def process_event(self, event: Dict[str, Any]) -> None:
        """Process a document ingestion event.

        Args:
            event: Event dictionary from Kafka

        Raises:
            Exception: If processing fails
        """
        event_type = event.get("event_type")
        document_id = event.get("document_id")
        namespace = event.get("namespace", "default")
        minio_bucket = event.get("minio_bucket")
        minio_key = event.get("minio_key")

        logger.info(f"Processing event: type={event_type}, doc_id={document_id}, namespace={namespace}")

        if event_type != "document.ingested":
            logger.warning(f"Unknown event type: {event_type}")
            return

        try:
            # Acquire distributed lock to prevent concurrent processing
            with self.document_lock(document_id):
                # Check if document already exists in Weaviate (duplicate detection)
                self._ensure_weaviate_connected()
                collection = self.weaviate_client.collections.get(self.config.weaviate_class)

                # Query for existing chunks with this doc_id (async)
                existing = await asyncio.to_thread(
                    collection.query.fetch_objects, filters=weaviate.classes.query.Filter.by_property("doc_id").equal(document_id), limit=1
                )

                if len(existing.objects) > 0:
                    logger.info(f"Document {document_id} already indexed ({len(existing.objects)} chunks found), skipping...")
                    return

                # 1. Load document from MinIO (async)
                document = await asyncio.to_thread(self.load_document, minio_bucket, minio_key)

                # 2. Create chunks (async - CPU-bound operation)
                chunks = await asyncio.to_thread(self.create_chunks, document)

                # 3. Generate embeddings (async - gRPC I/O)
                embeddings = await asyncio.to_thread(self.embed_chunks, chunks)

                # 4. Store in Weaviate (async)
                await asyncio.to_thread(self.store_chunks, chunks, embeddings)

                logger.info(f"✓ Successfully processed document {document_id}")

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
            raise
