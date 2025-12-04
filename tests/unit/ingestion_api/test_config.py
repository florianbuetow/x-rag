"""Unit tests for src/ingestion_api/config.py.

Tests cover:
- IngestionAPIConfig defaults
- IngestionAPIConfig MinIO endpoint validation
"""

from src.ingestion_api.config import IngestionAPIConfig


class TestIngestionAPIConfigDefaults:
    """Tests for IngestionAPIConfig default values."""

    def test_defaults(self):
        """Tests that defaults are set correctly.

        Note: Some defaults may be overridden by environment variables.
        We verify structural defaults that aren't env-dependent.
        """
        config = IngestionAPIConfig()

        assert config.service_name == "ingestion-api"
        assert config.port == 8082
        # minio_endpoint may be overridden by env - just check it's valid HTTP URL
        assert config.minio_endpoint.startswith("http://")
        # These core defaults should be stable
        assert config.minio_bucket == "documents"
        assert config.minio_secure is False
        assert config.kafka_topic == "document-changes"
        assert config.kafka_acks == "1"
        assert config.max_content_length == 10_485_760
        assert config.cors_enabled is True


class TestIngestionAPIConfigMinIOValidation:
    """Tests for IngestionAPIConfig MinIO endpoint validation."""

    def test_endpoint_with_http(self):
        """Tests that http:// prefix is preserved."""
        config = IngestionAPIConfig(minio_endpoint="http://localhost:9000")

        assert config.minio_endpoint == "http://localhost:9000"

    def test_endpoint_with_https(self):
        """Tests that https:// prefix is preserved."""
        config = IngestionAPIConfig(minio_endpoint="https://minio.example.com")

        assert config.minio_endpoint == "https://minio.example.com"

    def test_endpoint_without_scheme(self):
        """Tests that http:// is added when no scheme provided."""
        config = IngestionAPIConfig(minio_endpoint="minio:9000")

        assert config.minio_endpoint == "http://minio:9000"

    def test_endpoint_strips_trailing_slash(self):
        """Tests that trailing slash is stripped."""
        config = IngestionAPIConfig(minio_endpoint="http://minio:9000/")

        assert config.minio_endpoint == "http://minio:9000"
