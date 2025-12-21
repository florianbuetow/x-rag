"""Configuration for Indexer service."""

from typing import Literal

from pydantic import Field

from src.common.config import BaseConfig


class IndexerConfig(BaseConfig):
    """Configuration for Indexer service.

    Loads configuration from environment variables.
    """

    # Service info
    service_name: str = Field(default="indexer", description="Service name")
    log_level: str = Field(default="INFO", description="Logging level")

    # Kafka configuration
    kafka_bootstrap: str = Field(
        default="kafka:9092",
        description="Kafka bootstrap servers",
    )
    kafka_topic: str = Field(
        default="document-changes",
        description="Kafka topic to consume from",
    )
    kafka_group_id: str = Field(
        default="indexer-group",
        description="Kafka consumer group ID",
    )
    kafka_auto_offset_reset: str = Field(
        default="earliest",
        description="Kafka auto offset reset (earliest/latest)",
    )

    # MinIO configuration
    minio_endpoint: str = Field(
        default="minio:9000",
        description="MinIO endpoint",
    )
    minio_access_key: str = Field(
        default="minioadmin",
        description="MinIO access key",
    )
    minio_secret_key: str = Field(
        default="minioadmin123",
        description="MinIO secret key",
    )
    minio_bucket: str = Field(
        default="documents",
        description="MinIO bucket name",
    )
    minio_secure: bool = Field(
        default=False,
        description="Use HTTPS for MinIO",
    )

    # Weaviate configuration
    weaviate_url: str = Field(
        default="http://weaviate:8080",
        description="Weaviate URL",
    )
    weaviate_class: str = Field(
        default="DocumentChunk",
        description="Weaviate class name",
    )

    # Embedding Service configuration
    embedding_service_addr: str = Field(
        default="embedding-service:50051",
        description="Embedding Service gRPC address",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model to use",
    )

    # Processing configuration
    chunk_size: int = Field(
        default=500,
        description="Chunk size in characters",
    )
    chunk_overlap: int = Field(
        default=50,
        description="Chunk overlap in characters",
    )
    batch_size: int = Field(
        default=10,
        description="Batch size for embedding requests",
    )

    # Health check server
    health_port: int = Field(
        default=8080,
        description="Health check HTTP server port",
    )

    # OpenTelemetry tracing configuration
    otlp_endpoint: str | None = Field(
        default=None,
        description="OTLP endpoint for tracing (defaults to env var or http://tempo.monitoring.svc.cluster.local:4317)",
    )
    environment: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)",
    )

    # Embedding service timeout
    embedding_service_timeout: float = Field(
        default=30.0,
        description="Embedding Service timeout in seconds",
    )

    # Text cleaner configuration
    cleaner_remove_empty_lines: bool = Field(
        default=True,
        description="Remove empty lines during text cleaning",
    )
    cleaner_remove_extra_whitespaces: bool = Field(
        default=True,
        description="Remove extra whitespaces during text cleaning",
    )
    cleaner_unicode_normalization: Literal["NFC", "NFKC", "NFD", "NFKD"] | None = Field(
        default="NFC",
        description="Unicode normalization form (NFC, NFKC, NFD, NFKD)",
    )
