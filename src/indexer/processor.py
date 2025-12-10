"""Document processing and indexing logic.

Integrates the indexing pipeline with Weaviate storage and Kafka event processing.
"""

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from types import TracebackType
from typing import Any, cast

import weaviate
from weaviate import WeaviateClient

from src.common.metrics import track_latency
from src.common.tracing_utils import trace_document_processing, trace_embedding_generation
from src.indexer.config import IndexerConfig
from src.indexer.grpc_clients import EmbeddingServiceClient as GrpcEmbeddingServiceClient
from src.indexer.metrics import (
    duplicate_check_duration,
    embedding_duration,
    weaviate_insert_duration,
)
from src.pipelines.indexing_pipeline import (
    BasicTextCleaner,
    ChunkIngestionInterface,
    DocumentChunk,
    IndexingPipeline,
    MinIODocumentLoader,
    WordBasedTextSplitter,
)

logger = logging.getLogger(__name__)


class BatchEmbedder:
    """Batches text and calls embedding service to generate embeddings.

    Implements the AbstractEmbedder interface for the indexing pipeline.
    """

    def __init__(
        self,
        client: GrpcEmbeddingServiceClient,
        model: str,
        batch_size: int,
    ) -> None:
        """Initialize batch embedder.

        Args:
            client: Connected embedding service client
            model: Embedding model name
            batch_size: Batch size for embedding generation
        """
        self.client = client
        self.model = model
        self.batch_size = batch_size
        logger.info(f"✓ Batch embedder initialized (model={model}, batch_size={batch_size})")

    def generate(self, texts: list[str]) -> list[list[float]]:
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
        with (
            track_latency(embedding_duration, None),
            trace_embedding_generation(model=self.model, chunk_count=len(texts), total_tokens=None) as embed_span,
        ):
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                logger.debug(f"Generating embeddings for batch {i // self.batch_size + 1} ({len(batch)} texts)")

                embeddings = self.client.embed_batch(
                    texts=batch,
                    model=self.model,
                )
                all_embeddings.extend(embeddings)

            embed_span.set_attribute("embedding.batch_count", (len(texts) + self.batch_size - 1) // self.batch_size)

        return all_embeddings


class WeaviateBatchInserter:
    """Inserts document chunks into Weaviate in batches.

    Implements the ChunkIngestionInterface for the indexing pipeline.
    """

    def __init__(
        self,
        client: WeaviateClient,
        collection_name: str,
    ) -> None:
        """Initialize Weaviate batch inserter.

        Args:
            client: Connected Weaviate client
            collection_name: Name of Weaviate collection
        """
        self.client = client
        self.collection_name = collection_name
        logger.info(f"✓ Weaviate batch inserter initialized (collection={collection_name})")

    def store(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
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
                "source": chunk.metadata["source_file"] if "source_file" in chunk.metadata else "",
                "title": chunk.metadata["title"] if "title" in chunk.metadata else "",
                "metadata_json": json.dumps(chunk.metadata),
            }
            objects.append((obj, embedding))

        # Batch insert with metrics
        logger.debug(f"Inserting {len(objects)} chunks into Weaviate collection {self.collection_name}")
        with track_latency(weaviate_insert_duration, None), collection.batch.dynamic() as batch:
            for obj, vector in objects:
                batch.add_object(properties=obj, vector=vector)


class DocumentIndexer:
    """Indexes documents by coordinating the indexing pipeline.

    Integrates the indexing pipeline with:
    - Duplicate detection via Weaviate
    - Lazy Weaviate connection management
    - Async event processing from Kafka
    """

    def __init__(self, config: IndexerConfig) -> None:
        """Initialize the document indexer.

        Args:
            config: Indexer configuration
        """
        self.config = config

        # Weaviate client (initialized lazily for thread safety)
        self.weaviate_client: WeaviateClient | None = None
        self._weaviate_lock = threading.Lock()

        # Initialize Embedding Service client
        self.embedding_client = GrpcEmbeddingServiceClient(
            address=config.embedding_service_addr,
            timeout=config.embedding_service_timeout,
        )
        self.embedding_client.connect()

        # Pipeline components (typed for mypy)
        self._pipeline_components: dict[str, Any]
        self._chunk_ingester_factory: Callable[[], ChunkIngestionInterface]

        # Initialize indexing pipeline components
        self._init_pipeline()

        logger.info("✓ Document indexer initialized")

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
        cleaner = BasicTextCleaner(
            remove_empty_lines=self.config.cleaner_remove_empty_lines,
            remove_extra_whitespaces=self.config.cleaner_remove_extra_whitespaces,
            unicode_normalization=self.config.cleaner_unicode_normalization,
        )

        # Text splitter (convert char-based chunk_size/overlap to word counts)
        chunk_size_words = max(1, self.config.chunk_size // 5)
        chunk_overlap_words = max(0, self.config.chunk_overlap // 5)
        splitter = WordBasedTextSplitter(
            chunk_size_words=chunk_size_words,
            chunk_overlap_words=chunk_overlap_words,
        )

        # Embedder
        embedder = BatchEmbedder(
            client=self.embedding_client,
            model=self.config.embedding_model,
            batch_size=self.config.batch_size,
        )

        # Chunk ingester (initialized lazily, uses _get_weaviate_client)
        # We'll create this on-demand when processing
        self._chunk_ingester_factory = lambda: WeaviateBatchInserter(
            client=self._get_weaviate_client(),
            collection_name=self.config.weaviate_class,
        )

        # Create the pipeline components
        # Note: We can't initialize chunk_ingester yet because Weaviate is lazy
        # We'll recreate the pipeline in process_event after ensuring connection
        self._pipeline_components = {
            "loader": loader,
            "cleaner": cleaner,
            "splitter": splitter,
            "embedder": embedder,
        }

        logger.info("✓ Indexing pipeline components initialized")

    def __enter__(self) -> "DocumentIndexer":
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

    def close(self) -> None:
        """Close connections."""
        if self.embedding_client:
            self.embedding_client.close()
        if self.weaviate_client:
            self.weaviate_client.close()

    async def process_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Process a document ingestion event.

        Args:
            event: Event dictionary from Kafka

        Returns:
            Dictionary with processing results including chunks_created

        Raises:
            Exception: If processing fails
        """
        event_type = event["event_type"] if "event_type" in event else None
        document_id = cast(str, event["document_id"])
        namespace = event["namespace"] if "namespace" in event else "default"
        minio_bucket = cast(str, event.get("minio_bucket"))
        minio_key = cast(str, event.get("minio_key"))

        logger.info(f"Processing event: type={event_type}, doc_id={document_id}, namespace={namespace}")

        if event_type != "document.ingested":
            logger.warning(f"Unknown event type: {event_type}")
            return {"chunks_created": 0, "skipped": True, "reason": "unknown_event_type"}

        try:
            # Check if document already exists in Weaviate (duplicate detection)
            weaviate_client = self._get_weaviate_client()
            collection = weaviate_client.collections.get(self.config.weaviate_class)

            # Query for existing chunks with this doc_id (async) with metrics
            with (
                track_latency(duplicate_check_duration, None),
                trace_document_processing(document_id, "duplicate_check") as dup_span,
            ):
                existing = await asyncio.to_thread(
                    collection.query.fetch_objects,
                    filters=weaviate.classes.query.Filter.by_property("doc_id").equal(document_id),
                    limit=1,
                )
                dup_span.set_attribute("document.existing_chunks", len(existing.objects))

            if len(existing.objects) > 0:
                logger.info(f"Document {document_id} already indexed ({len(existing.objects)} chunks found), skipping...")
                return {"chunks_created": 0, "skipped": True, "reason": "duplicate"}

            # Create indexing pipeline with Weaviate client
            chunk_ingester = self._chunk_ingester_factory()
            pipeline = IndexingPipeline(
                loader=self._pipeline_components["loader"],
                cleaner=self._pipeline_components["cleaner"],
                splitter=self._pipeline_components["splitter"],
                embedder=self._pipeline_components["embedder"],
                chunk_ingester=chunk_ingester,
            )

            # Process document through pipeline (async)
            with trace_document_processing(document_id, "pipeline") as pipeline_span:
                pipeline_span.set_attribute("document.namespace", namespace)
                pipeline_span.set_attribute("document.bucket", minio_bucket)
                pipeline_span.set_attribute("document.key", minio_key)
                num_chunks = await asyncio.to_thread(
                    pipeline.process_document,
                    bucket=minio_bucket,
                    key=minio_key,
                )
                pipeline_span.set_attribute("document.chunk_count", num_chunks)

            logger.info(f"✓ Successfully processed document {document_id} ({num_chunks} chunks)")
            return {"chunks_created": num_chunks, "skipped": False}

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
            raise
