"""Unit tests for src/ingestion_api/minio_client.py.

Tests cover:
- MinioClient initialization
- _ensure_bucket method
- store_document method
- health_check method
"""

from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from src.ingestion_api.minio_client import MinioClient


class TestMinioClientInit:
    """Tests for MinioClient initialization."""

    @patch("src.ingestion_api.minio_client.Minio")
    def test_init_creates_minio_client(self, mock_minio_class):
        """Tests that __init__ creates Minio client."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        client = MinioClient(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="test-bucket",
            secure=False,
        )

        mock_minio_class.assert_called_once_with(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False,
        )
        assert client.bucket == "test-bucket"

    @patch("src.ingestion_api.minio_client.Minio")
    def test_init_strips_http_prefix(self, mock_minio_class):
        """Tests that __init__ strips http:// prefix from endpoint."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        MinioClient(
            endpoint="http://localhost:9000",
            access_key="admin",
            secret_key="secret",
            bucket="bucket",
            secure=False,
        )

        # First positional arg should be clean endpoint
        call_args = mock_minio_class.call_args
        assert call_args[0][0] == "localhost:9000"

    @patch("src.ingestion_api.minio_client.Minio")
    def test_init_strips_https_prefix(self, mock_minio_class):
        """Tests that __init__ strips https:// prefix from endpoint."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        MinioClient(
            endpoint="https://minio.example.com:9000",
            access_key="admin",
            secret_key="secret",
            bucket="bucket",
            secure=True,
        )

        call_args = mock_minio_class.call_args
        assert call_args[0][0] == "minio.example.com:9000"

    @patch("src.ingestion_api.minio_client.Minio")
    def test_init_with_secure_true(self, mock_minio_class):
        """Tests that __init__ passes secure parameter."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        MinioClient(
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="secret",
            bucket="bucket",
            secure=True,
        )

        call_kwargs = mock_minio_class.call_args[1]
        assert call_kwargs["secure"] is True

    @patch("src.ingestion_api.minio_client.Minio")
    def test_init_calls_ensure_bucket(self, mock_minio_class):
        """Tests that __init__ calls _ensure_bucket."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio_class.return_value = mock_client

        MinioClient(
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="secret",
            bucket="new-bucket",
            secure=False,
        )

        mock_client.bucket_exists.assert_called_once_with("new-bucket")
        mock_client.make_bucket.assert_called_once_with("new-bucket")


class TestMinioClientEnsureBucket:
    """Tests for MinioClient._ensure_bucket method."""

    @patch("src.ingestion_api.minio_client.Minio")
    def test_ensure_bucket_creates_when_missing(self, mock_minio_class):
        """Tests that _ensure_bucket creates bucket when it doesn't exist."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio_class.return_value = mock_client

        MinioClient(
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="secret",
            bucket="new-bucket",
            secure=False,
        )

        mock_client.make_bucket.assert_called_once_with("new-bucket")

    @patch("src.ingestion_api.minio_client.Minio")
    def test_ensure_bucket_skips_when_exists(self, mock_minio_class):
        """Tests that _ensure_bucket skips creation when bucket exists."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        MinioClient(
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="secret",
            bucket="existing-bucket",
            secure=False,
        )

        mock_client.make_bucket.assert_not_called()

    @patch("src.ingestion_api.minio_client.Minio")
    def test_ensure_bucket_raises_on_s3_error(self, mock_minio_class):
        """Tests that _ensure_bucket raises S3Error on failure."""
        mock_client = MagicMock()
        mock_client.bucket_exists.side_effect = S3Error(
            code="AccessDenied",
            message="Access Denied",
            resource="bucket",
            request_id="123",
            host_id="456",
            response=MagicMock(),
        )
        mock_minio_class.return_value = mock_client

        with pytest.raises(S3Error):
            MinioClient(
                endpoint="localhost:9000",
                access_key="admin",
                secret_key="secret",
                bucket="bucket",
                secure=False,
            )


class TestMinioClientStoreDocument:
    """Tests for MinioClient.store_document method."""

    @pytest.fixture
    def client(self):
        """Create MinioClient with mocked Minio."""
        with patch("src.ingestion_api.minio_client.Minio") as mock_minio_class:
            mock_minio = MagicMock()
            mock_minio.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_minio

            minio_client = MinioClient(
                endpoint="localhost:9000",
                access_key="admin",
                secret_key="secret",
                bucket="test-bucket",
                secure=False,
            )
            yield minio_client

    def test_store_document_uploads_content(self, client):
        """Tests that store_document uploads content to MinIO."""
        content = b"document content"

        result = client.store_document("doc.json", content)

        assert result == "doc.json"
        client.client.put_object.assert_called_once()

    def test_store_document_sets_correct_bucket(self, client):
        """Tests that store_document uses correct bucket."""
        content = b"content"

        client.store_document("doc.json", content)

        call_kwargs = client.client.put_object.call_args[1]
        assert call_kwargs["bucket_name"] == "test-bucket"

    def test_store_document_sets_correct_object_name(self, client):
        """Tests that store_document uses correct object name."""
        content = b"content"

        client.store_document("path/to/doc.json", content)

        call_kwargs = client.client.put_object.call_args[1]
        assert call_kwargs["object_name"] == "path/to/doc.json"

    def test_store_document_sets_correct_content_type(self, client):
        """Tests that store_document sets content type to application/json."""
        content = b"content"

        client.store_document("doc.json", content)

        call_kwargs = client.client.put_object.call_args[1]
        assert call_kwargs["content_type"] == "application/json"

    def test_store_document_sets_correct_length(self, client):
        """Tests that store_document sets correct content length."""
        content = b"hello world"

        client.store_document("doc.json", content)

        call_kwargs = client.client.put_object.call_args[1]
        assert call_kwargs["length"] == len(content)

    def test_store_document_raises_on_s3_error(self, client):
        """Tests that store_document raises S3Error on failure."""
        client.client.put_object.side_effect = S3Error(
            code="InternalError",
            message="Internal Error",
            resource="doc.json",
            request_id="123",
            host_id="456",
            response=MagicMock(),
        )

        with pytest.raises(S3Error):
            client.store_document("doc.json", b"content")


class TestMinioClientHealthCheck:
    """Tests for MinioClient.health_check method."""

    @pytest.fixture
    def client(self):
        """Create MinioClient with mocked Minio."""
        with patch("src.ingestion_api.minio_client.Minio") as mock_minio_class:
            mock_minio = MagicMock()
            mock_minio.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_minio

            minio_client = MinioClient(
                endpoint="localhost:9000",
                access_key="admin",
                secret_key="secret",
                bucket="test-bucket",
                secure=False,
            )
            yield minio_client

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_healthy(self, client):
        """Tests that health_check returns True when MinIO is accessible."""
        client.client.bucket_exists.return_value = True

        result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_checks_bucket_exists(self, client):
        """Tests that health_check calls bucket_exists."""
        # Reset mock to track new calls
        client.client.bucket_exists.reset_mock()

        await client.health_check()

        client.client.bucket_exists.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self, client):
        """Tests that health_check returns False on exception."""
        client.client.bucket_exists.side_effect = Exception("Connection error")

        result = await client.health_check()

        assert result is False
