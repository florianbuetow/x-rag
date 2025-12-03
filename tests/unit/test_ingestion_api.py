"""Unit tests for Ingestion API endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.ingestion_api.main import (
    DocumentMetadata,
    IngestRequest,
    IngestResponse,
    health,
    ingest_document,
    liveness,
    readiness,
    root,
)


class TestIngestRequestValidation:
    """Tests for IngestRequest model validation."""

    def test_valid_request(self):
        """Valid request passes validation."""
        request = IngestRequest(
            text="Test document content",
            metadata=DocumentMetadata(title="Test Title"),
            namespace="default",
        )

        assert request.text == "Test document content"
        assert request.metadata.title == "Test Title"
        assert request.namespace == "default"

    def test_empty_text_rejected(self):
        """Empty text raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            IngestRequest(
                text="",
                metadata=DocumentMetadata(title="Test"),
                namespace="default",
            )

        assert "text" in str(exc_info.value)

    def test_invalid_namespace_pattern(self):
        """Invalid namespace pattern raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title="Test"),
                namespace="Invalid_Namespace!",
            )

        assert "namespace" in str(exc_info.value)

    def test_valid_namespace_patterns(self):
        """Valid namespace patterns accepted."""
        valid_namespaces = ["default", "my-namespace", "test123", "a-b-c-123"]

        for ns in valid_namespaces:
            request = IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title="Test"),
                namespace=ns,
            )
            assert request.namespace == ns

    def test_metadata_required_fields(self):
        """Metadata title is required."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title=""),  # Empty title
                namespace="default",
            )

        assert "title" in str(exc_info.value)

    def test_metadata_optional_fields(self):
        """Metadata optional fields work correctly."""
        request = IngestRequest(
            text="Test content",
            metadata=DocumentMetadata(
                title="Test Title",
                source_file="document.pdf",
                type="pdf",
                transcription_method="tesseract",
            ),
            namespace="default",
        )

        assert request.metadata.source_file == "document.pdf"
        assert request.metadata.type == "pdf"
        assert request.metadata.transcription_method == "tesseract"

    def test_metadata_extra_fields_rejected(self):
        """Extra fields in metadata are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            DocumentMetadata(title="Test", unknown_field="value")

        assert "extra" in str(exc_info.value).lower() or "unknown_field" in str(exc_info.value)


class TestIngestEndpoint:
    """Tests for /ingest endpoint."""

    @pytest.fixture
    def mock_minio_client(self):
        """Mock MinioClient."""
        client = Mock()
        client.store_document = Mock(return_value="test-id.json")
        client.health_check = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_kafka_client(self):
        """Mock KafkaClient."""
        client = AsyncMock()
        client.publish = AsyncMock()
        client.health_check = AsyncMock(return_value=True)
        return client

    @pytest.mark.asyncio
    async def test_ingest_success(self, mock_minio_client, mock_kafka_client):
        """Successful ingestion stores in MinIO and publishes to Kafka."""
        import src.ingestion_api.main as main_module

        # Patch global clients
        original_minio = main_module.minio_client
        original_kafka = main_module.kafka_client
        main_module.minio_client = mock_minio_client
        main_module.kafka_client = mock_kafka_client

        try:
            request = IngestRequest(
                text="Test document content",
                metadata=DocumentMetadata(title="Test Title"),
                namespace="default",
            )

            response = await ingest_document(request)

            assert response.status == "accepted"
            assert response.minio_bucket is not None
            assert response.minio_key.endswith(".json")
            assert response.document_id is not None

            # Verify MinIO was called
            mock_minio_client.store_document.assert_called_once()
            call_args = mock_minio_client.store_document.call_args
            assert call_args[0][0].endswith(".json")

            # Verify Kafka was called
            mock_kafka_client.publish.assert_called_once()
            call_args = mock_kafka_client.publish.call_args
            event = call_args[0][1]
            assert event["event_type"] == "document.ingested"
            assert event["namespace"] == "default"

        finally:
            main_module.minio_client = original_minio
            main_module.kafka_client = original_kafka

    @pytest.mark.asyncio
    async def test_ingest_minio_not_initialized(self):
        """Ingestion fails when MinIO client is None."""
        from fastapi import HTTPException

        import src.ingestion_api.main as main_module

        original_minio = main_module.minio_client
        main_module.minio_client = None

        try:
            request = IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title="Test"),
                namespace="default",
            )

            with pytest.raises(HTTPException) as exc_info:
                await ingest_document(request)

            # HTTPException is caught by generic handler and wrapped as 500
            assert exc_info.value.status_code == 500
            assert "MinIO" in exc_info.value.detail

        finally:
            main_module.minio_client = original_minio

    @pytest.mark.asyncio
    async def test_ingest_kafka_not_initialized(self, mock_minio_client):
        """Ingestion fails when Kafka client is None."""
        from fastapi import HTTPException

        import src.ingestion_api.main as main_module

        original_minio = main_module.minio_client
        original_kafka = main_module.kafka_client
        main_module.minio_client = mock_minio_client
        main_module.kafka_client = None

        try:
            request = IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title="Test"),
                namespace="default",
            )

            with pytest.raises(HTTPException) as exc_info:
                await ingest_document(request)

            # HTTPException is caught by generic handler and wrapped as 500
            assert exc_info.value.status_code == 500
            assert "Kafka" in exc_info.value.detail

        finally:
            main_module.minio_client = original_minio
            main_module.kafka_client = original_kafka

    @pytest.mark.asyncio
    async def test_ingest_minio_failure(self, mock_minio_client, mock_kafka_client):
        """Ingestion fails when MinIO store fails."""
        from fastapi import HTTPException
        from minio.error import S3Error

        import src.ingestion_api.main as main_module

        mock_minio_client.store_document.side_effect = S3Error("PUT", "bucket", "key", 500, "500", "InternalError", "Internal Error", None)

        original_minio = main_module.minio_client
        original_kafka = main_module.kafka_client
        main_module.minio_client = mock_minio_client
        main_module.kafka_client = mock_kafka_client

        try:
            request = IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title="Test"),
                namespace="default",
            )

            with pytest.raises(HTTPException) as exc_info:
                await ingest_document(request)

            assert exc_info.value.status_code == 500
            assert "Ingestion failed" in exc_info.value.detail

        finally:
            main_module.minio_client = original_minio
            main_module.kafka_client = original_kafka

    @pytest.mark.asyncio
    async def test_ingest_kafka_failure(self, mock_minio_client, mock_kafka_client):
        """Ingestion fails when Kafka publish fails."""
        from aiokafka.errors import KafkaError
        from fastapi import HTTPException

        import src.ingestion_api.main as main_module

        mock_kafka_client.publish.side_effect = KafkaError("Connection failed")

        original_minio = main_module.minio_client
        original_kafka = main_module.kafka_client
        main_module.minio_client = mock_minio_client
        main_module.kafka_client = mock_kafka_client

        try:
            request = IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title="Test"),
                namespace="default",
            )

            with pytest.raises(HTTPException) as exc_info:
                await ingest_document(request)

            assert exc_info.value.status_code == 500
            assert "Ingestion failed" in exc_info.value.detail

        finally:
            main_module.minio_client = original_minio
            main_module.kafka_client = original_kafka

    @pytest.mark.asyncio
    async def test_ingest_with_custom_namespace(self, mock_minio_client, mock_kafka_client):
        """Ingestion uses custom namespace in Kafka event."""
        import src.ingestion_api.main as main_module

        original_minio = main_module.minio_client
        original_kafka = main_module.kafka_client
        main_module.minio_client = mock_minio_client
        main_module.kafka_client = mock_kafka_client

        try:
            request = IngestRequest(
                text="Test content",
                metadata=DocumentMetadata(title="Test"),
                namespace="my-custom-ns",
            )

            await ingest_document(request)

            # Verify namespace in Kafka event
            call_args = mock_kafka_client.publish.call_args
            event = call_args[0][1]
            assert event["namespace"] == "my-custom-ns"

        finally:
            main_module.minio_client = original_minio
            main_module.kafka_client = original_kafka


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.fixture
    def mock_health_checker(self):
        """Mock HealthChecker."""
        checker = AsyncMock()
        checker.check_all = AsyncMock(
            return_value={
                "status": "HEALTHY",
                "dependencies": {"minio": "HEALTHY", "kafka": "HEALTHY"},
            }
        )
        return checker

    @pytest.mark.asyncio
    async def test_health_healthy(self, mock_health_checker):
        """Health endpoint returns healthy status."""
        import src.ingestion_api.main as main_module

        original_checker = main_module.health_checker
        main_module.health_checker = mock_health_checker

        try:
            result = await health()

            assert result["status"] == "HEALTHY"
            assert "dependencies" in result

        finally:
            main_module.health_checker = original_checker

    @pytest.mark.asyncio
    async def test_health_unhealthy(self, mock_health_checker):
        """Health endpoint raises 503 when unhealthy."""
        from fastapi import HTTPException

        import src.ingestion_api.main as main_module

        mock_health_checker.check_all.return_value = {
            "status": "UNHEALTHY",
            "dependencies": {"minio": "UNHEALTHY", "kafka": "HEALTHY"},
        }

        original_checker = main_module.health_checker
        main_module.health_checker = mock_health_checker

        try:
            with pytest.raises(HTTPException) as exc_info:
                await health()

            assert exc_info.value.status_code == 503

        finally:
            main_module.health_checker = original_checker

    @pytest.mark.asyncio
    async def test_health_checker_not_initialized(self):
        """Health endpoint raises 503 when checker is None."""
        from fastapi import HTTPException

        import src.ingestion_api.main as main_module

        original_checker = main_module.health_checker
        main_module.health_checker = None

        try:
            with pytest.raises(HTTPException) as exc_info:
                await health()

            assert exc_info.value.status_code == 503
            assert "Health checker not initialized" in exc_info.value.detail

        finally:
            main_module.health_checker = original_checker

    @pytest.mark.asyncio
    async def test_readiness_healthy(self, mock_health_checker):
        """Readiness endpoint returns healthy status."""
        import src.ingestion_api.main as main_module

        original_checker = main_module.health_checker
        main_module.health_checker = mock_health_checker

        try:
            result = await readiness()

            assert result["status"] == "HEALTHY"
            mock_health_checker.check_all.assert_called_once()

        finally:
            main_module.health_checker = original_checker

    @pytest.mark.asyncio
    async def test_readiness_unhealthy(self, mock_health_checker):
        """Readiness endpoint raises 503 when unhealthy."""
        from fastapi import HTTPException

        import src.ingestion_api.main as main_module

        mock_health_checker.check_all.return_value = {"status": "UNHEALTHY", "dependencies": {}}

        original_checker = main_module.health_checker
        main_module.health_checker = mock_health_checker

        try:
            with pytest.raises(HTTPException) as exc_info:
                await readiness()

            assert exc_info.value.status_code == 503

        finally:
            main_module.health_checker = original_checker

    @pytest.mark.asyncio
    async def test_liveness_always_returns_alive(self):
        """Liveness endpoint always returns alive."""
        result = await liveness()

        assert result["status"] == "alive"

    @pytest.mark.asyncio
    async def test_root_returns_service_info(self):
        """Root endpoint returns service information."""
        result = await root()

        assert result["service"] == "ingestion-api"
        assert result["version"] == "0.1.0"
        assert result["status"] == "operational"


class TestIngestResponse:
    """Tests for IngestResponse model."""

    def test_response_fields(self):
        """IngestResponse has correct fields."""
        response = IngestResponse(
            document_id="test-123",
            status="accepted",
            minio_bucket="documents",
            minio_key="test-123.json",
            message="Document accepted",
        )

        assert response.document_id == "test-123"
        assert response.status == "accepted"
        assert response.minio_bucket == "documents"
        assert response.minio_key == "test-123.json"
        assert response.message == "Document accepted"

    def test_response_default_values(self):
        """IngestResponse uses default values."""
        response = IngestResponse(
            document_id="test-123",
            minio_bucket="documents",
            minio_key="test-123.json",
        )

        assert response.status == "accepted"
        assert response.message == "Document accepted for processing"
