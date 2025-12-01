"""Document processing and indexing logic."""

import json
import logging
import uuid
from typing import Any, Dict, List

from minio import Minio
import weaviate
from weaviate.classes.config import Property, DataType

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
    ):
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

    def __init__(self, config: IndexerConfig):
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

        # Initialize Embedding Service client
        self.embedding_client = EmbeddingServiceClient(
            address=config.embedding_service_addr
        )
        self.embedding_client.connect()

        logger.info("✓ Document processor initialized")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _ensure_weaviate_connected(self) -> None:
        """Ensure Weaviate client is connected (lazy initialization)."""
        if self.weaviate_client is None:
            logger.info("Connecting to Weaviate...")
            self.weaviate_client = weaviate.connect_to_custom(
                http_host=self.config.weaviate_url.replace("http://", "").replace("https://", ""),
                http_port=8080,
                http_secure=False,
                grpc_host=self.config.weaviate_url.replace("http://", "").replace("https://", ""),
                grpc_port=50051,
                grpc_secure=False,
            )
            logger.info("✓ Connected to Weaviate")

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
            data = response.read()
            response.close()
            response.release_conn()

            document = json.loads(data.decode("utf-8"))
            logger.info(f"✓ Loaded document: {document.get('id')}")
            return document

        except Exception as e:
            logger.error(f"Failed to load document {bucket}/{key}: {e}")
            raise

    def chunk_text(self, text: str) -> List[str]:
        """Chunk text into overlapping segments.

        Uses a simple character-based chunking strategy with overlap.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)

            # Move start position forward (with overlap)
            start = end - overlap

        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
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
            logger.info(
                f"Generating embeddings for batch {i//batch_size + 1} "
                f"({len(batch)} chunks)"
            )

            embeddings = self.embedding_client.embed_batch(
                texts=batch,
                model=self.config.embedding_model,
            )
            all_embeddings.extend(embeddings)

        logger.info(f"✓ Generated {len(all_embeddings)} embeddings")
        return all_embeddings

    def store_chunks(
        self, chunks: List[DocumentChunk], embeddings: List[List[float]]
    ) -> None:
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
        for chunk, embedding in zip(chunks, embeddings):
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

        logger.info(
            f"Processing event: type={event_type}, doc_id={document_id}, "
            f"namespace={namespace}"
        )

        if event_type != "document.ingested":
            logger.warning(f"Unknown event type: {event_type}")
            return

        try:
            # 1. Load document from MinIO
            document = self.load_document(minio_bucket, minio_key)

            # 2. Create chunks
            chunks = self.create_chunks(document)

            # 3. Generate embeddings
            embeddings = self.embed_chunks(chunks)

            # 4. Store in Weaviate
            self.store_chunks(chunks, embeddings)

            logger.info(f"✓ Successfully processed document {document_id}")

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}", exc_info=True)
            raise
