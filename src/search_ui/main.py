"""Search UI - FastAPI application."""

import logging
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from src.common.health import HealthChecker
from src.common.metrics import track_latency
from src.common.otel_metrics import init_otel_metrics, shutdown_otel_metrics
from src.common.tracing import get_current_trace_id, init_tracing, shutdown_tracing
from src.search_ui.config import SearchUIConfig
from src.search_ui.grpc_clients import SearchServiceClient
from src.search_ui.metrics import (
    active_requests,
    errors_total,
    grpc_call_duration,
    request_duration,
    requests_total,
    sources_returned,
)
from src.search_ui.models import SearchRequest, SearchResponse, Source

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Global state
config = SearchUIConfig()
search_client: SearchServiceClient | None = None
health_checker: HealthChecker | None = None

# Templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager."""
    global search_client, health_checker

    # Startup
    logger.info(f"Starting {config.service_name}...")

    # Initialize distributed tracing
    init_tracing(
        service_name=config.service_name,
        otlp_endpoint=config.otlp_endpoint,
        environment=config.environment,
    )

    # Initialize OpenTelemetry metrics export to Grafana Alloy
    init_otel_metrics(
        service_name=config.service_name,
        service_version=os.getenv("SERVICE_VERSION", "0.1.0"),
    )

    # Initialize Search Service client
    logger.info("Initializing Search Service client...")
    search_client = SearchServiceClient(
        address=config.search_service_addr,
        timeout=config.search_service_timeout,
    )
    await search_client.connect()

    # Initialize health checker
    health_checker = HealthChecker()
    health_checker.add_dependency(
        "search_service",
        search_client.health_check,
        critical=True,
    )

    logger.info(f"✓ {config.service_name} ready on port {config.port}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    shutdown_otel_metrics()
    shutdown_tracing()
    if search_client:
        await search_client.close()
    logger.info("✓ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="X-RAG Search UI",
    description="Web interface for X-RAG search service",
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
@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Serve search interface.

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML template
    """
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Perform search via Search Service.

    Args:
        request: Search request

    Returns:
        Search response with answer and sources

    Raises:
        HTTPException: If search fails
    """
    active_requests.inc()
    try:
        with track_latency(request_duration, {"operation": "search"}):
            if search_client is None:
                raise HTTPException(
                    status_code=503,
                    detail="Search Service client not initialized",
                )

            # Call Search Service via gRPC with metrics
            with track_latency(grpc_call_duration, {"method": "Search"}):
                grpc_response = await search_client.search(
                    query=request.query,
                    namespace=request.namespace,
                    top_k=request.top_k,
                    mode=request.mode,
                    options=None,
                )

            # Convert gRPC response to Pydantic model
            sources = [
                Source(
                    id=source.id,
                    content=source.content,
                    score=source.score,
                    metadata=dict(source.metadata),
                )
                for source in grpc_response.sources
            ]

            # Record number of sources returned
            sources_returned.observe(len(sources))

            # Add trace_id to metadata for debugging
            response_metadata = dict(grpc_response.metadata)
            trace_id = get_current_trace_id()
            if trace_id:
                response_metadata["trace_id"] = trace_id

            response = SearchResponse(
                answer=grpc_response.answer,
                sources=sources,
                metadata=response_metadata,
            )

        # Track success
        requests_total.labels(status="success", mode=request.mode).inc()

        logger.info(
            f"Search completed: query='{request.query[:50]}...', mode={request.mode}, sources={len(sources)}",
        )

        return response

    except HTTPException:
        requests_total.labels(status="error", mode=request.mode).inc()
        raise

    except Exception as e:
        requests_total.labels(status="error", mode=request.mode).inc()
        errors_total.labels(operation="search", error_type=type(e).__name__).inc()
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
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


if __name__ == "__main__":
    import uvicorn

    # Bind to 0.0.0.0 for Kubernetes service access
    uvicorn.run(
        app,
        host="0.0.0.0",  # nosec B104
        port=config.port,
        log_level=config.log_level.lower(),
    )
