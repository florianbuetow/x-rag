"""Configuration for Ingestion API."""

from pydantic import Field, field_validator

from src.common.config import ServiceConfig


class IngestionAPIConfig(ServiceConfig):
    """Ingestion API configuration."""

    service_name: str = Field(default="ingestion-api")
    port: int = Field(default=8082)

    # MinIO
    minio_endpoint: str = Field(default="xrag-minio:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin123")
    minio_bucket: str = Field(default="documents")
    minio_secure: bool = Field(default=False)

    # Kafka
    kafka_bootstrap: str = Field(default="xrag-kafka:9092")
    kafka_topic: str = Field(default="document-changes")
    kafka_acks: str = Field(default="1")  # 0, 1, or "all"

    # API
    max_content_length: int = Field(default=10_485_760)  # 10MB
    cors_enabled: bool = Field(default=True)

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
