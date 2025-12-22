"""Configuration for Ingestion API."""

from pydantic import Field, ValidationError, field_validator

from src.common.config import KafkaConfig, MinIOConfig, ServiceConfig


class IngestionAPIConfig(ServiceConfig):
    """Ingestion API configuration."""

    service_name: str = Field(...)
    port: int = Field(...)

    # MinIO
    minio_endpoint: str = Field(...)
    minio_access_key: str = Field(...)
    minio_secret_key: str = Field(...)
    minio_bucket: str = Field(...)
    minio_secure: bool = Field(...)

    # Kafka
    kafka_bootstrap: str = Field(...)
    kafka_topic: str = Field(...)
    kafka_acks: str = Field(...)  # 0, 1, or "all"

    # API
    max_content_length: int = Field(...)  # 10MB
    cors_enabled: bool = Field(...)

    @field_validator("minio_endpoint")
    @classmethod
    def validate_minio_endpoint(cls, v: str) -> str:
        """Validate MinIO endpoint format.

        Args:
            v: MinIO endpoint string

        Returns:
            Formatted endpoint string
        """
        if v.startswith(("http://", "https://")):
            return v.rstrip("/")
        # Assume http:// if no scheme
        return f"http://{v}".rstrip("/")

    # Getter methods for composed configs

    def get_kafka_config(self) -> KafkaConfig:
        """Get Kafka configuration as a validated model.

        Returns:
            KafkaConfig instance with validated Kafka settings
        """
        return KafkaConfig(
            kafka_bootstrap=self.kafka_bootstrap,
            kafka_topic=self.kafka_topic,
            kafka_acks=self.kafka_acks,
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

        # Validate content length
        if self.max_content_length <= 0:
            errors.append(f"max_content_length must be positive, got {self.max_content_length}")
