"""Configuration for Indexer service."""

from typing import Literal

from pydantic import Field, ValidationError

from src.common.config import KafkaConfig, MinIOConfig, ServiceConfig, WeaviateConfig


class IndexerConfig(ServiceConfig):
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
        description="OTLP endpoint for tracing (defaults to env var or http://xrag-tempo:4317)",
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

    # Getter methods for composed configs

    def get_kafka_config(self) -> KafkaConfig:
        """Get Kafka configuration as a validated model.

        Returns:
            KafkaConfig instance with validated Kafka settings
        """
        return KafkaConfig(
            kafka_bootstrap=self.kafka_bootstrap,
            kafka_topic=self.kafka_topic,
            kafka_group_id=self.kafka_group_id,
            kafka_auto_offset_reset=self.kafka_auto_offset_reset,
        )

    def get_minio_config(self) -> MinIOConfig:
        """Get MinIO configuration as a validated model.

        Returns:
            MinIOConfig instance with validated MinIO settings
        """
        return MinIOConfig(
            minio_endpoint=self.minio_endpoint,
            minio_access_key=self.minio_access_key,
            minio_secret_key=self.minio_secret_key,
            minio_bucket=self.minio_bucket,
            minio_secure=self.minio_secure,
        )

    def get_weaviate_config(self) -> WeaviateConfig:
        """Get Weaviate configuration as a validated model.

        Returns:
            WeaviateConfig instance with validated Weaviate settings
        """
        return WeaviateConfig(
            weaviate_url=self.weaviate_url,
            weaviate_timeout=30,  # Use default since not in IndexerConfig
            weaviate_collection=self.weaviate_class,
        )

    def _validate_cross_fields(self, errors: list[str], warnings: list[str]) -> None:
        """Validate cross-field dependencies and composed configs.

        Args:
            errors: List to append validation errors to
            warnings: List to append validation warnings to
        """
        # Validate composed configs
        try:
            self.get_kafka_config()
        except ValidationError as e:
            errors.extend(f"Kafka config: {err}" for err in e.errors())

        try:
            self.get_minio_config()
        except ValidationError as e:
            errors.extend(f"MinIO config: {err}" for err in e.errors())

        try:
            self.get_weaviate_config()
        except ValidationError as e:
            errors.extend(f"Weaviate config: {err}" for err in e.errors())

        # Validate chunk configuration
        if self.chunk_overlap >= self.chunk_size:
            errors.append(f"chunk_overlap ({self.chunk_overlap}) must be less than chunk_size ({self.chunk_size})")

        if self.batch_size <= 0:
            errors.append(f"batch_size must be positive, got {self.batch_size}")

        if self.embedding_service_timeout <= 0:
            errors.append(f"embedding_service_timeout must be positive, got {self.embedding_service_timeout}")
