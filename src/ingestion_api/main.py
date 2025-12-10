"""Ingestion API - FastAPI application."""

import json
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import start_http_server
from pydantic import BaseModel, ConfigDict, Field

from src.common.health import HealthChecker
from src.common.metrics import track_latency
from src.common.tracing import init_tracing, shutdown_tracing
from src.ingestion_api.config import IngestionAPIConfig
from src.ingestion_api.kafka_client import KafkaClient
from src.ingestion_api.metrics import (
    active_requests,
    document_size_bytes,
    errors_total,
    kafka_publish_duration,
    minio_upload_duration,
    request_duration,
    requests_total,
)
from src.ingestion_api.minio_client import MinioClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Pydantic Models


class DocumentMetadata(BaseModel):
    """Document metadata (flexible schema)."""

    model_config = ConfigDict(extra="forbid")  # Reject unexpected fields

    title: str = Field(..., min_length=1, max_length=512)
    source_file: str | None = None
    type: str = "text"
    transcription_method: str | None = None


class IngestRequest(BaseModel):
    """Document ingestion request."""

    text: str = Field(..., min_length=1, description="Document content")
    metadata: DocumentMetadata = Field(..., description="Document metadata")
    namespace: str = Field(default="default", pattern="^[a-z0-9-]+$")


class IngestResponse(BaseModel):
    """Document ingestion response."""

    document_id: str = Field(..., description="Unique document ID")
    status: str = Field(default="accepted", description="Processing status")
    minio_bucket: str = Field(..., description="Storage bucket")
    minio_key: str = Field(..., description="Storage key")
    message: str = Field(default="Document accepted for processing")


# Global state
config = IngestionAPIConfig()
minio_client: MinioClient | None = None
kafka_client: KafkaClient | None = None
health_checker: HealthChecker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager."""
    global minio_client, kafka_client, health_checker

    # Startup
    logger.info(f"Starting {config.service_name}...")

    # Initialize distributed tracing
    init_tracing(
        service_name=config.service_name,
        otlp_endpoint=config.otlp_endpoint,
        environment=config.environment,
    )

    # Start Prometheus metrics server
    start_http_server(8080)
    logger.info("Prometheus metrics available at http://0.0.0.0:8080/metrics")

    # Initialize MinIO
    logger.info("Initializing MinIO client...")
    minio_client = MinioClient(
        endpoint=config.minio_endpoint,
        access_key=config.minio_access_key,
        secret_key=config.minio_secret_key,
        bucket=config.minio_bucket,
        secure=config.minio_secure,
    )

    # Initialize Kafka
    logger.info("Initializing Kafka client...")
    kafka_client = KafkaClient(
        bootstrap_servers=config.kafka_bootstrap,
        acks=config.kafka_acks,
    )
    await kafka_client.start()

    # Initialize health checker
    health_checker = HealthChecker()
    health_checker.add_dependency(
        "minio",
        minio_client.health_check,
        critical=True,
    )
    health_checker.add_dependency(
        "kafka",
        kafka_client.health_check,
        critical=True,
    )

    logger.info(f"✓ {config.service_name} ready on port {config.port}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    shutdown_tracing()
    if kafka_client:
        await kafka_client.stop()
    logger.info("✓ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="X-RAG Ingestion API",
    description="Document ingestion service for X-RAG platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Instrument FastAPI for distributed tracing
FastAPIInstrumentor.instrument_app(app)

# CORS
if config.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Routes
@app.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(request: IngestRequest) -> IngestResponse:
    """Ingest a document for processing.

    The document is stored in MinIO and an event is published to Kafka
    for asynchronous processing by the Indexer service.

    Args:
        request: Document ingestion request

    Returns:
        Ingestion response with document ID and storage location

    Raises:
        HTTPException: If ingestion fails
    """
    active_requests.inc()
    try:
        with track_latency(request_duration, {"operation": "ingest"}):
            # Generate unique ID
            document_id = str(uuid4())

            # Prepare document
            document = {
                "id": document_id,
                "text": request.text,
                "metadata": request.metadata.model_dump(),
                "namespace": request.namespace,
                "ingested_at": datetime.now(UTC).isoformat(),
            }

            # Store in MinIO
            if minio_client is None:
                raise HTTPException(status_code=503, detail="MinIO client not initialized")
            object_name = f"{document_id}.json"
            doc_bytes = json.dumps(document, indent=2).encode("utf-8")

            # Record document size
            document_size_bytes.observe(len(doc_bytes))

            with track_latency(minio_upload_duration, None):
                minio_client.store_document(object_name, doc_bytes)

            # Publish to Kafka
            if kafka_client is None:
                raise HTTPException(status_code=503, detail="Kafka client not initialized")
            event = {
                "event_type": "document.ingested",
                "document_id": document_id,
                "namespace": request.namespace,
                "minio_bucket": config.minio_bucket,
                "minio_key": object_name,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            with track_latency(kafka_publish_duration, None):
                await kafka_client.publish(config.kafka_topic, event)

        # Track success
        requests_total.labels(status="success", namespace=request.namespace).inc()

        logger.info(f"Ingested document {document_id} ({len(doc_bytes)} bytes)")

        return IngestResponse(
            document_id=document_id,
            status="accepted",
            minio_bucket=config.minio_bucket,
            minio_key=object_name,
            message="Document accepted for processing",
        )

    except HTTPException:
        requests_total.labels(status="error", namespace=request.namespace).inc()
        raise

    except Exception as e:
        requests_total.labels(status="error", namespace=request.namespace).inc()
        errors_total.labels(operation="ingest", error_type=type(e).__name__).inc()
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        ) from e

    finally:
        active_requests.dec()


@app.get("/health")
async def health() -> dict[str, Any]:
    """Comprehensive health check.

    Returns:
        Health status with dependency checks

    Raises:
        HTTPException: If service is unhealthy
    """
    if health_checker is None:
        raise HTTPException(status_code=503, detail="Health checker not initialized")
    result = await health_checker.check_all()
    if result["status"] == "UNHEALTHY":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result,
        )
    return result


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe.

    Returns:
        Liveness status
    """
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """Kubernetes readiness probe.

    Returns:
        Readiness status with dependency checks

    Raises:
        HTTPException: If service is not ready
    """
    if health_checker is None:
        raise HTTPException(status_code=503, detail="Health checker not initialized")
    result = await health_checker.check_all()
    if result["status"] == "UNHEALTHY":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result,
        )
    return result


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Service information
    """
    return {
        "service": config.service_name,
        "version": "0.1.0",
        "status": "operational",
    }


if __name__ == "__main__":
    import uvicorn

    # Bind to 0.0.0.0 for Kubernetes service access - network isolation handled by K8s
    uvicorn.run(
        app,
        host="0.0.0.0",  # nosec B104
        port=config.port,
        log_level=config.log_level.lower(),
    )
