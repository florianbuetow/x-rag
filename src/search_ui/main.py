"""Search UI - FastAPI application."""

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from prometheus_client import Counter, Histogram, start_http_server

from src.common.health import HealthChecker
from src.search_ui.config import SearchUIConfig
from src.search_ui.grpc_clients import SearchServiceClient
from src.search_ui.models import SearchRequest, SearchResponse, Source

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Prometheus Metrics
SEARCH_REQUESTS = Counter(
    "search_ui_requests_total",
    "Total search requests",
    ["status", "mode"],
)
SEARCH_DURATION = Histogram(
    "search_ui_duration_seconds",
    "Time to process search request",
    ["operation"],
)

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

    # Start Prometheus metrics server on separate port
    start_http_server(9091)
    logger.info("Prometheus metrics available at http://0.0.0.0:9091/metrics")

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
    with SEARCH_DURATION.labels(operation="search").time():
        try:
            if search_client is None:
                raise HTTPException(
                    status_code=503,
                    detail="Search Service client not initialized",
                )

            # Call Search Service via gRPC
            grpc_response = await search_client.search(
                query=request.query,
                namespace=request.namespace,
                top_k=request.top_k,
                mode=request.mode,
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

            response = SearchResponse(
                answer=grpc_response.answer,
                sources=sources,
                metadata=dict(grpc_response.metadata),
            )

            # Track success
            SEARCH_REQUESTS.labels(status="success", mode=request.mode).inc()

            logger.info(
                f"Search completed: query='{request.query[:50]}...', mode={request.mode}, sources={len(sources)}",
            )

            return response

        except Exception as e:
            SEARCH_REQUESTS.labels(status="error", mode=request.mode).inc()
            logger.error(f"Search failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Search failed: {str(e)}",
            ) from e


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
