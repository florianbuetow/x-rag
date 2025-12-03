"""Document processing and indexing logic.

Integrates the indexing pipeline with Weaviate storage, distributed locking,
and Kafka event processing.
"""

import asyncio
import json
import logging
import threading
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Dict, Generator, List, cast

import redis
import weaviate
from weaviate import WeaviateClient

from src.indexer.config import IndexerConfig
from src.indexer.grpc_clients import EmbeddingServiceClient
from src.pipelines.indexing_pipeline import (
    BasicTextCleaner,
    DocumentChunk,
    IndexingPipeline,
    MinIODocumentLoader,
    WordBasedTextSplitter,
)

logger = logging.getLogger(__name__)


class GrpcEmbeddingGenerator:
    """Generates embeddings via gRPC Embedding Service.

    Implements the EmbeddingGenerator protocol for the indexing pipeline.
    """

    def __init__(
        self,
        client: EmbeddingServiceClient,
        model: str,
        batch_size: int = 32,
    ) -> None:
        """Initialize gRPC embedding generator.

        Args:
            client: Connected Embedding Service client
            model: Embedding model name
            batch_size: Batch size for embedding generation
        """
        self.client = client
        self.model = model
        self.batch_size = batch_size
        logger.info(f"✓ gRPC embedding generator initialized (model={model}, batch_size={batch_size})")

    def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            logger.debug(f"Generating embeddings for batch {i // self.batch_size + 1} ({len(batch)} texts)")

            embeddings = self.client.embed_batch(
                texts=batch,
                model=self.model,
            )
            all_embeddings.extend(embeddings)

        return all_embeddings


class WeaviateChunkStore:
    """Stores document chunks in Weaviate.

    Implements the ChunkStore protocol for the indexing pipeline.
    """

    def __init__(
        self,
        client: WeaviateClient,
        collection_name: str,
    ) -> None:
        """Initialize Weaviate chunk store.

        Args:
            client: Connected Weaviate client
            collection_name: Name of Weaviate collection
        """
        self.client = client
        self.collection_name = collection_name
        logger.info(f"✓ Weaviate chunk store initialized (collection={collection_name})")

    def store(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        """Store chunks and embeddings in Weaviate.

        Args:
            chunks: List of document chunks
            embeddings: List of embedding vectors
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        if not chunks:
            logger.warning("No chunks to store")
            return

        collection = self.client.collections.get(self.collection_name)

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
        logger.debug(f"Inserting {len(objects)} chunks into Weaviate collection {self.collection_name}")
        with collection.batch.dynamic() as batch:
            for obj, vector in objects:
                batch.add_object(properties=obj, vector=vector)


class DocumentProcessor:
    """Processes documents using the indexing pipeline.

    Integrates the indexing pipeline with:
    - Distributed locking via Redis (prevents duplicate processing)
    - Duplicate detection via Weaviate
    - Lazy Weaviate connection management
    - Async event processing from Kafka
    """

    def __init__(self, config: IndexerConfig) -> None:
        """Initialize the document processor.

        Args:
            config: Indexer configuration
        """
        self.config = config

        # Weaviate client (initialized lazily for thread safety)
        self.weaviate_client: WeaviateClient | None = None
        self._weaviate_lock = threading.Lock()

        # Initialize Redis client for distributed locking
        self.redis_client = redis.Redis.from_url(
            config.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )

        # Initialize Embedding Service client
        self.embedding_client = EmbeddingServiceClient(address=config.embedding_service_addr)
        self.embedding_client.connect()

        # Initialize indexing pipeline components
        self._init_pipeline()

        logger.info("✓ Document processor initialized")

    def _init_pipeline(self) -> None:
        """Initialize the indexing pipeline and its components."""
        # Document loader
        loader = MinIODocumentLoader(
            endpoint=self.config.minio_endpoint,
            access_key=self.config.minio_access_key,
            secret_key=self.config.minio_secret_key,
            secure=self.config.minio_secure,
        )

        # Text cleaner
        cleaner = BasicTextCleaner()

        # Text splitter (convert char-based chunk_size to word count)
        chunk_size_words = max(1, self.config.chunk_size // 5)
        splitter = WordBasedTextSplitter(chunk_size_words=chunk_size_words)

        # Embedding generator
        embedding_generator = GrpcEmbeddingGenerator(
            client=self.embedding_client,
            model=self.config.embedding_model,
            batch_size=self.config.batch_size,
        )

        # Chunk store (initialized lazily, uses _ensure_weaviate_connected)
        # We'll create this on-demand when processing
        self._chunk_store_factory = lambda: WeaviateChunkStore(
            client=self._get_weaviate_client(),
            collection_name=self.config.weaviate_class,
        )

        # Create the pipeline
        # Note: We can't initialize chunk_store yet because Weaviate is lazy
        # We'll recreate the pipeline in process_event after ensuring connection
        self._pipeline_components = {
            "loader": loader,
            "cleaner": cleaner,
            "splitter": splitter,
            "embedding_generator": embedding_generator,
        }

        logger.info("✓ Indexing pipeline components initialized")

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

    def _get_weaviate_client(self) -> WeaviateClient:
        """Get Weaviate client, connecting if necessary (thread-safe).

        Returns:
            Connected Weaviate client

        Raises:
            RuntimeError: If connection fails
        """
        # Fast path: check without lock (common case)
        if self.weaviate_client is not None:
            return self.weaviate_client

        # Slow path: acquire lock and connect
        with self._weaviate_lock:
            # Double-check inside lock (another thread may have connected)
            if self.weaviate_client is not None:
                return self.weaviate_client

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
            return self.weaviate_client

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

    async def process_event(self, event: Dict[str, Any]) -> None:
        """Process a document ingestion event.

        Args:
            event: Event dictionary from Kafka

        Raises:
            Exception: If processing fails
        """
        event_type = event.get("event_type")
        document_id = cast(str, event.get("document_id"))
        namespace = event.get("namespace", "default")
        minio_bucket = cast(str, event.get("minio_bucket"))
        minio_key = cast(str, event.get("minio_key"))

        logger.info(f"Processing event: type={event_type}, doc_id={document_id}, namespace={namespace}")

        if event_type != "document.ingested":
            logger.warning(f"Unknown event type: {event_type}")
            return

        try:
            # Acquire distributed lock to prevent concurrent processing
            with self.document_lock(document_id):
                # Check if document already exists in Weaviate (duplicate detection)
                weaviate_client = self._get_weaviate_client()
                collection = weaviate_client.collections.get(self.config.weaviate_class)

                # Query for existing chunks with this doc_id (async)
                existing = await asyncio.to_thread(
                    collection.query.fetch_objects,
                    filters=weaviate.classes.query.Filter.by_property("doc_id").equal(document_id),
                    limit=1,
                )

                if len(existing.objects) > 0:
                    logger.info(f"Document {document_id} already indexed ({len(existing.objects)} chunks found), skipping...")
                    return

                # Create indexing pipeline with Weaviate client
                chunk_store = self._chunk_store_factory()
                pipeline = IndexingPipeline(
                    loader=self._pipeline_components["loader"],
                    cleaner=self._pipeline_components["cleaner"],
                    splitter=self._pipeline_components["splitter"],
                    embedding_generator=self._pipeline_components["embedding_generator"],
                    chunk_store=chunk_store,
                )

                # Process document through pipeline (async)
                num_chunks = await asyncio.to_thread(
                    pipeline.process_document,
                    bucket=minio_bucket,
                    key=minio_key,
                )

                logger.info(f"✓ Successfully processed document {document_id} ({num_chunks} chunks)")

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
            raise
