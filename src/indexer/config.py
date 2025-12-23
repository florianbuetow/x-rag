"""Configuration for Indexer service."""

from pydantic import Field, ValidationError

from src.common.config import KafkaConfig, MinIOConfig, ServiceConfig


class IndexerConfig(ServiceConfig):
    """Configuration for Indexer service.

    Loads configuration from environment variables.
    """

    # Service info
    service_name: str = Field(..., description="Service name")

    # Kafka configuration
    kafka_bootstrap: str = Field(
        ...,
        description="Kafka bootstrap servers",
    )
    kafka_topic: str = Field(
        ...,
        description="Kafka topic to consume from",
    )
    kafka_group_id: str = Field(
        ...,
        description="Kafka consumer group ID",
    )
    kafka_auto_offset_reset: str = Field(
        ...,
        description="Kafka auto offset reset (earliest/latest)",
    )

    # MinIO configuration
    minio_endpoint: str = Field(
        ...,
        description="MinIO endpoint",
    )
    minio_access_key: str = Field(
        ...,
        description="MinIO access key",
    )
    minio_secret_key: str = Field(
        ...,
        description="MinIO secret key",
    )
    minio_bucket: str = Field(
        ...,
        description="MinIO bucket name",
    )
    minio_secure: bool = Field(
        ...,
        description="Use HTTPS for MinIO",
    )

    # Weaviate configuration
    weaviate_url: str = Field(
        ...,
        description="Weaviate URL",
    )
    weaviate_timeout_init: int = Field(
        ...,
        ge=1,
        description="Weaviate init timeout in seconds",
    )
    weaviate_timeout_query: int = Field(
        ...,
        ge=1,
        description="Weaviate query timeout in seconds",
    )
    weaviate_timeout_insert: int = Field(
        ...,
        ge=1,
        description="Weaviate insert timeout in seconds",
    )

    # Embedding Service configuration
    embedding_service_addr: str = Field(
        ...,
        description="Embedding Service gRPC address",
    )

    # Dataset config path
    datasets_config_path: str = Field(
        ...,
        description="Path to datasets configuration file",
    )

    # Processing configuration
    batch_size: int = Field(
        ...,
        description="Batch size for embedding requests",
    )

    # Health check server
    health_port: int = Field(
        ...,
        description="Health check HTTP server port",
    )

    # Embedding service timeout
    embedding_service_timeout: float = Field(
        ...,
        description="Embedding Service timeout in seconds",
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

        # Validate processing configuration
        if self.batch_size <= 0:
            errors.append(f"batch_size must be positive, got {self.batch_size}")

        if self.embedding_service_timeout <= 0:
            errors.append(f"embedding_service_timeout must be positive, got {self.embedding_service_timeout}")
