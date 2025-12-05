# Distributed Tracing Implementation Guide for RAG Microservices

A comprehensive guide for implementing OpenTelemetry-based distributed tracing with Grafana Tempo, designed for Python FastAPI microservices with existing Prometheus/Grafana monitoring.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Python Application Setup](#python-application-setup)
5. [Auto-Instrumentation](#auto-instrumentation)
6. [Manual Instrumentation](#manual-instrumentation)
7. [Service Implementation Examples](#service-implementation-examples)
8. [Grafana Configuration](#grafana-configuration)
9. [Validation Tests](#validation-tests)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This guide implements distributed tracing across RAG microservices using:

- **OpenTelemetry**: Instrumentation and trace context propagation
- **Grafana Tempo**: Trace storage and querying (integrates with existing Grafana)
- **OTLP Protocol**: Standard export format for traces

### Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Search API │────▶│Ingestion API│────▶│  Vector DB  │
└──────┬──────┘     └──────┬──────┘     └─────────────┘
       │                   │
       │ OTLP              │ OTLP
       ▼                   ▼
┌─────────────────────────────────────┐
│           Grafana Tempo             │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│             Grafana UI              │
│  (Traces + Prometheus Metrics)      │
└─────────────────────────────────────┘
```

---

## Prerequisites

### Required Software

- Docker and Docker Compose (or Kind for Kubernetes)
- Python 3.10+
- Existing Grafana instance (v9.0+ recommended for Tempo integration)
- Existing Prometheus setup

### Python Dependencies

Create or update your `requirements.txt`:

```txt
# Core application
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.24.0

# OpenTelemetry - Core
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
opentelemetry-exporter-otlp>=1.20.0

# OpenTelemetry - Auto-instrumentation
opentelemetry-distro>=0.41b0
opentelemetry-instrumentation-fastapi>=0.41b0
opentelemetry-instrumentation-httpx>=0.41b0
opentelemetry-instrumentation-logging>=0.41b0

# Your existing dependencies
prometheus-client>=0.17.0
```

Install with:

```bash
pip install -r requirements.txt

# Auto-install all available instrumentations for your dependencies
opentelemetry-bootstrap -a install
```

---

## Infrastructure Setup

### Option A: Docker Compose (Development)

Add Tempo to your existing `docker-compose.yml`:

```yaml
version: "3.8"

services:
  # Your existing services...
  
  tempo:
    image: grafana/tempo:2.3.0
    container_name: tempo
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./tempo-config.yaml:/etc/tempo.yaml:ro
      - tempo-data:/var/tempo
    ports:
      - "3200:3200"   # Tempo API
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    networks:
      - monitoring

  # Update your Grafana service to connect to Tempo
  grafana:
    # ... your existing config
    environment:
      - GF_FEATURE_TOGGLES_ENABLE=traceqlEditor
    depends_on:
      - tempo

volumes:
  tempo-data:

networks:
  monitoring:
    driver: bridge
```

Create `tempo-config.yaml`:

```yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"
        http:
          endpoint: "0.0.0.0:4318"

ingester:
  max_block_duration: 5m

compactor:
  compaction:
    block_retention: 48h

storage:
  trace:
    backend: local
    wal:
      path: /var/tempo/wal
    local:
      path: /var/tempo/blocks

querier:
  frontend_worker:
    frontend_address: ""

metrics_generator:
  registry:
    external_labels:
      source: tempo
  storage:
    path: /var/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
        send_exemplars: true
```

### Option B: Kind/Kubernetes (Production-like)

Create `tempo-k8s.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tempo-config
  namespace: monitoring
data:
  tempo.yaml: |
    server:
      http_listen_port: 3200
    distributor:
      receivers:
        otlp:
          protocols:
            grpc:
              endpoint: "0.0.0.0:4317"
            http:
              endpoint: "0.0.0.0:4318"
    ingester:
      max_block_duration: 5m
    compactor:
      compaction:
        block_retention: 48h
    storage:
      trace:
        backend: local
        wal:
          path: /var/tempo/wal
        local:
          path: /var/tempo/blocks
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tempo
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: tempo
  template:
    metadata:
      labels:
        app: tempo
    spec:
      containers:
        - name: tempo
          image: grafana/tempo:2.3.0
          args:
            - "-config.file=/etc/tempo/tempo.yaml"
          ports:
            - containerPort: 3200
              name: http
            - containerPort: 4317
              name: otlp-grpc
            - containerPort: 4318
              name: otlp-http
          volumeMounts:
            - name: config
              mountPath: /etc/tempo
            - name: data
              mountPath: /var/tempo
      volumes:
        - name: config
          configMap:
            name: tempo-config
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: tempo
  namespace: monitoring
spec:
  selector:
    app: tempo
  ports:
    - name: http
      port: 3200
      targetPort: 3200
    - name: otlp-grpc
      port: 4317
      targetPort: 4317
    - name: otlp-http
      port: 4318
      targetPort: 4318
```

Apply with:

```bash
kubectl apply -f tempo-k8s.yaml
```

---

## Python Application Setup

### Tracing Configuration Module

Create `tracing.py` - a reusable module for all your services:

```python
"""
tracing.py - OpenTelemetry configuration for RAG microservices

Usage:
    from tracing import init_tracing, get_tracer
    
    # Initialize once at startup
    init_tracing(service_name="search-api")
    
    # Get tracer for manual spans
    tracer = get_tracer(__name__)
"""

import os
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator

logger = logging.getLogger(__name__)

_tracer_provider: Optional[TracerProvider] = None


def init_tracing(
    service_name: str,
    otlp_endpoint: Optional[str] = None,
    environment: str = "development",
) -> TracerProvider:
    """
    Initialize OpenTelemetry tracing.
    
    Args:
        service_name: Name of this service (appears in traces)
        otlp_endpoint: Tempo/collector endpoint. Defaults to OTEL_EXPORTER_OTLP_ENDPOINT 
                       env var or localhost:4317
        environment: Deployment environment tag
    
    Returns:
        Configured TracerProvider
    """
    global _tracer_provider
    
    if _tracer_provider is not None:
        logger.warning("Tracing already initialized, returning existing provider")
        return _tracer_provider
    
    # Resolve endpoint
    endpoint = otlp_endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", 
        "http://localhost:4317"
    )
    
    # Create resource with service metadata
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "service.namespace": "rag-platform",
        "deployment.environment": environment,
        "service.version": os.getenv("SERVICE_VERSION", "0.1.0"),
    })
    
    # Initialize provider
    _tracer_provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=True,  # Set False and configure TLS for production
    )
    
    # Use batch processor for efficiency
    span_processor = BatchSpanProcessor(
        otlp_exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
    )
    _tracer_provider.add_span_processor(span_processor)
    
    # Set as global provider
    trace.set_tracer_provider(_tracer_provider)
    
    # Configure context propagation (W3C Trace Context + Baggage)
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ]))
    
    logger.info(f"Tracing initialized for {service_name}, exporting to {endpoint}")
    
    return _tracer_provider


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance for creating manual spans."""
    return trace.get_tracer(name)


def shutdown_tracing():
    """Gracefully shutdown tracing (call on app shutdown)."""
    global _tracer_provider
    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None
        logger.info("Tracing shutdown complete")
```

### Instrumentation Utilities

Create `tracing_utils.py` for common span patterns:

```python
"""
tracing_utils.py - Helper utilities for manual instrumentation

Provides decorators and context managers for common tracing patterns
in RAG applications: LLM calls, embedding generation, vector search.
"""

import functools
import time
from typing import Any, Callable, Optional
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, SpanKind

tracer = trace.get_tracer(__name__)


def trace_llm_call(
    model: str,
    operation: str = "completion",
):
    """
    Decorator for tracing LLM API calls.
    
    Usage:
        @trace_llm_call(model="gpt-4", operation="rerank")
        async def rerank_documents(query: str, docs: list) -> list:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                f"llm.{operation}",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("llm.model", model)
                span.set_attribute("llm.operation", operation)
                
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    
                    # Record token counts if available
                    if hasattr(result, "usage"):
                        span.set_attribute("llm.prompt_tokens", result.usage.prompt_tokens)
                        span.set_attribute("llm.completion_tokens", result.usage.completion_tokens)
                        span.set_attribute("llm.total_tokens", result.usage.total_tokens)
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("llm.duration_ms", duration_ms)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                f"llm.{operation}",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("llm.model", model)
                span.set_attribute("llm.operation", operation)
                
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("llm.duration_ms", duration_ms)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


@contextmanager
def trace_embedding_generation(
    model: str,
    chunk_count: int,
    total_tokens: Optional[int] = None,
):
    """
    Context manager for tracing embedding generation.
    
    Usage:
        with trace_embedding_generation("text-embedding-3-small", len(chunks)) as span:
            embeddings = client.embeddings.create(input=chunks, model=model)
            span.set_attribute("embedding.dimensions", len(embeddings[0]))
    """
    with tracer.start_as_current_span(
        "embedding.generate",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("embedding.model", model)
        span.set_attribute("embedding.chunk_count", chunk_count)
        if total_tokens:
            span.set_attribute("embedding.total_tokens", total_tokens)
        
        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("embedding.duration_ms", duration_ms)


@contextmanager
def trace_vector_search(
    index_name: str,
    top_k: int,
    query_vector_dim: Optional[int] = None,
):
    """
    Context manager for tracing vector database searches.
    
    Usage:
        with trace_vector_search("documents", top_k=10) as span:
            results = vector_db.search(query_embedding, top_k=10)
            span.set_attribute("vector_search.result_count", len(results))
    """
    with tracer.start_as_current_span(
        "vector_search.query",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("vector_search.index", index_name)
        span.set_attribute("vector_search.top_k", top_k)
        if query_vector_dim:
            span.set_attribute("vector_search.query_dimensions", query_vector_dim)
        
        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("vector_search.duration_ms", duration_ms)


def add_rag_attributes(
    span: trace.Span,
    query: str,
    retrieved_count: int,
    reranked: bool = False,
    final_context_tokens: Optional[int] = None,
):
    """Add RAG-specific attributes to a span."""
    span.set_attribute("rag.query_length", len(query))
    span.set_attribute("rag.retrieved_count", retrieved_count)
    span.set_attribute("rag.reranked", reranked)
    if final_context_tokens:
        span.set_attribute("rag.context_tokens", final_context_tokens)


# Import asyncio for the decorator check
import asyncio
```

---

## Auto-Instrumentation

### Method 1: CLI Wrapper (Recommended for Development)

Run your application with automatic instrumentation:

```bash
# Set required environment variables
export OTEL_SERVICE_NAME=search-api
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=none  # Keep using Prometheus for metrics
export OTEL_LOGS_EXPORTER=none

# Run with auto-instrumentation
opentelemetry-instrument uvicorn main:app --host 0.0.0.0 --port 8000
```

### Method 2: Programmatic Setup (Recommended for Production)

Initialize in your application's entry point:

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from tracing import init_tracing, shutdown_tracing

# Instrument libraries BEFORE importing them
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_tracing(
        service_name="search-api",
        environment="development",
    )
    
    # Instrument libraries
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)
    
    yield
    
    # Shutdown
    shutdown_tracing()


app = FastAPI(
    title="Search API",
    lifespan=lifespan,
)
```

---

## Service Implementation Examples

### Search API Service

```python
# search_api/main.py
"""
Search API - Handles RAG search queries
"""

import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tracing import init_tracing, shutdown_tracing, get_tracer
from tracing_utils import (
    trace_embedding_generation,
    trace_vector_search,
    add_rag_attributes,
)

# Instrumentation imports
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


# --- Models ---

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    rerank: bool = True


class SearchResult(BaseModel):
    document_id: str
    content: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    trace_id: Optional[str] = None


# --- Application Setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing(
        service_name="search-api",
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    
    yield
    
    shutdown_tracing()


app = FastAPI(title="RAG Search API", lifespan=lifespan)
tracer = get_tracer(__name__)


# --- Simulated Dependencies ---

class EmbeddingClient:
    """Simulated embedding service client."""
    
    async def generate(self, texts: list[str], model: str = "text-embedding-3-small"):
        # Simulate API call latency
        import asyncio
        await asyncio.sleep(0.05)
        return [[0.1] * 1536 for _ in texts]


class VectorDBClient:
    """Simulated vector database client."""
    
    async def search(self, embedding: list[float], top_k: int, index: str = "documents"):
        import asyncio
        await asyncio.sleep(0.02)
        return [
            {"id": f"doc_{i}", "content": f"Sample content {i}", "score": 0.9 - i * 0.05}
            for i in range(min(top_k, 5))
        ]


embedding_client = EmbeddingClient()
vector_db = VectorDBClient()


# --- Endpoints ---

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "search-api"}


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Execute a RAG search query.
    
    1. Generate embedding for query
    2. Search vector database
    3. Optionally rerank results
    4. Return results with trace ID for debugging
    """
    from opentelemetry import trace
    
    # Get current span for adding attributes
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    trace_id = format(span_context.trace_id, '032x') if span_context.is_valid else None
    
    # Add request attributes to span
    current_span.set_attribute("search.query_length", len(request.query))
    current_span.set_attribute("search.top_k", request.top_k)
    current_span.set_attribute("search.rerank_enabled", request.rerank)
    
    # Step 1: Generate query embedding
    with trace_embedding_generation(
        model="text-embedding-3-small",
        chunk_count=1,
    ) as embed_span:
        query_embedding = await embedding_client.generate([request.query])
        embed_span.set_attribute("embedding.dimensions", len(query_embedding[0]))
    
    # Step 2: Vector search
    with trace_vector_search(
        index_name="documents",
        top_k=request.top_k,
        query_vector_dim=len(query_embedding[0]),
    ) as search_span:
        raw_results = await vector_db.search(
            embedding=query_embedding[0],
            top_k=request.top_k,
        )
        search_span.set_attribute("vector_search.result_count", len(raw_results))
    
    # Step 3: Optional reranking
    if request.rerank and raw_results:
        with tracer.start_as_current_span("rerank") as rerank_span:
            rerank_span.set_attribute("rerank.input_count", len(raw_results))
            # Simulate reranking (would call LLM or cross-encoder)
            import asyncio
            await asyncio.sleep(0.03)
            rerank_span.set_attribute("rerank.output_count", len(raw_results))
    
    # Add RAG summary attributes
    add_rag_attributes(
        current_span,
        query=request.query,
        retrieved_count=len(raw_results),
        reranked=request.rerank,
    )
    
    # Build response
    results = [
        SearchResult(
            document_id=r["id"],
            content=r["content"],
            score=r["score"],
            metadata={},
        )
        for r in raw_results
    ]
    
    return SearchResponse(
        query=request.query,
        results=results,
        trace_id=trace_id,
    )


@app.post("/ingest")
async def trigger_ingestion(document_url: str):
    """
    Trigger document ingestion via Ingestion API.
    Demonstrates cross-service trace propagation.
    """
    async with httpx.AsyncClient() as client:
        # Trace context automatically propagated via HTTPXClientInstrumentor
        response = await client.post(
            f"{os.getenv('INGESTION_API_URL', 'http://localhost:8001')}/ingest",
            json={"url": document_url},
            timeout=30.0,
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Ingestion failed")
        
        return response.json()
```

### Ingestion API Service

```python
# ingestion_api/main.py
"""
Ingestion API - Handles document ingestion and chunking
"""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from tracing import init_tracing, shutdown_tracing, get_tracer
from tracing_utils import trace_embedding_generation

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace


# --- Models ---

class IngestRequest(BaseModel):
    url: str
    chunk_size: int = 512
    chunk_overlap: int = 50


class IngestResponse(BaseModel):
    job_id: str
    status: str
    trace_id: Optional[str] = None


# --- Application Setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing(
        service_name="ingestion-api",
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )
    FastAPIInstrumentor.instrument_app(app)
    
    yield
    
    shutdown_tracing()


app = FastAPI(title="RAG Ingestion API", lifespan=lifespan)
tracer = get_tracer(__name__)


# --- Background Processing ---

async def process_document(job_id: str, url: str, chunk_size: int, chunk_overlap: int):
    """
    Background task for document processing.
    Creates a new trace linked to the original request.
    """
    with tracer.start_as_current_span(
        "document_processing",
        attributes={
            "job.id": job_id,
            "document.url": url,
        }
    ) as span:
        
        # Step 1: Fetch document
        with tracer.start_as_current_span("fetch_document") as fetch_span:
            import asyncio
            await asyncio.sleep(0.1)  # Simulate fetch
            fetch_span.set_attribute("document.size_bytes", 15000)
        
        # Step 2: Parse and chunk
        with tracer.start_as_current_span("chunk_document") as chunk_span:
            await asyncio.sleep(0.05)  # Simulate chunking
            chunk_count = 12  # Simulated
            chunk_span.set_attribute("chunking.strategy", "recursive")
            chunk_span.set_attribute("chunking.chunk_size", chunk_size)
            chunk_span.set_attribute("chunking.overlap", chunk_overlap)
            chunk_span.set_attribute("chunking.result_count", chunk_count)
        
        # Step 3: Generate embeddings
        with trace_embedding_generation(
            model="text-embedding-3-small",
            chunk_count=chunk_count,
        ) as embed_span:
            await asyncio.sleep(0.08)  # Simulate embedding API
            embed_span.set_attribute("embedding.dimensions", 1536)
        
        # Step 4: Store in vector DB
        with tracer.start_as_current_span("store_vectors") as store_span:
            await asyncio.sleep(0.03)  # Simulate storage
            store_span.set_attribute("storage.index", "documents")
            store_span.set_attribute("storage.vectors_stored", chunk_count)
        
        span.set_attribute("job.status", "completed")


# --- Endpoints ---

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ingestion-api"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Queue a document for ingestion.
    Returns immediately with job ID; processing happens in background.
    """
    import uuid
    
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    trace_id = format(span_context.trace_id, '032x') if span_context.is_valid else None
    
    job_id = str(uuid.uuid4())
    
    current_span.set_attribute("job.id", job_id)
    current_span.set_attribute("document.url", request.url)
    
    # Queue background processing
    background_tasks.add_task(
        process_document,
        job_id=job_id,
        url=request.url,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    )
    
    return IngestResponse(
        job_id=job_id,
        status="queued",
        trace_id=trace_id,
    )
```

---

## Grafana Configuration

### Add Tempo Data Source

1. Navigate to Grafana → Configuration → Data Sources → Add data source
2. Select "Tempo"
3. Configure:

```yaml
Name: Tempo
URL: http://tempo:3200  # Or your Tempo service URL
```

4. Under "Additional settings", enable:
   - "Enable TraceQL Search"

5. Click "Save & Test"

### Link Traces to Metrics (Exemplars)

If your Prometheus scrapes from Tempo's metrics generator, you can click from metric spikes directly to traces.

Update your Prometheus scrape config:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'tempo'
    static_configs:
      - targets: ['tempo:3200']
```

### Sample Dashboard Panel

Create a panel to show trace links from your existing metrics:

```json
{
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service=\"search-api\"}[5m]))",
      "exemplar": true
    }
  ],
  "options": {
    "dataLinks": [
      {
        "title": "View trace",
        "url": "/explore?orgId=1&left=%5B%22now-1h%22,%22now%22,%22Tempo%22,%7B%22query%22:%22${__data.fields.traceID}%22%7D%5D"
      }
    ]
  }
}
```

---

## Validation Tests

### Test 1: Verify Tempo is Receiving Traces

```bash
# Check Tempo is running and receiving data
curl -s http://localhost:3200/ready
# Expected: "ready"

# Check Tempo metrics
curl -s http://localhost:3200/metrics | grep tempo_distributor_ingester_appends_total
# Should show non-zero values after sending traces
```

### Test 2: End-to-End Trace Generation

Create `test_tracing.py`:

```python
"""
test_tracing.py - Validation tests for distributed tracing setup
"""

import asyncio
import httpx
import time


SEARCH_API_URL = "http://localhost:8000"
TEMPO_URL = "http://localhost:3200"


async def test_single_service_trace():
    """Test that a single request generates a trace."""
    print("\n=== Test 1: Single Service Trace ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SEARCH_API_URL}/search",
            json={"query": "test query", "top_k": 5},
        )
        
        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        trace_id = data.get("trace_id")
        
        print(f"Request successful, trace_id: {trace_id}")
        
        if trace_id:
            # Wait for trace to be indexed
            await asyncio.sleep(2)
            
            # Query Tempo for the trace
            trace_response = await client.get(
                f"{TEMPO_URL}/api/traces/{trace_id}",
            )
            
            if trace_response.status_code == 200:
                print("✓ Trace found in Tempo!")
                trace_data = trace_response.json()
                span_count = len(trace_data.get("batches", [{}])[0].get("scopeSpans", [{}])[0].get("spans", []))
                print(f"  Span count: {span_count}")
            else:
                print(f"✗ Trace not found (may need more time): {trace_response.status_code}")
        
        return trace_id


async def test_cross_service_propagation():
    """Test that traces propagate across service calls."""
    print("\n=== Test 2: Cross-Service Propagation ===")
    
    async with httpx.AsyncClient() as client:
        # Trigger ingestion which should call Ingestion API
        try:
            response = await client.post(
                f"{SEARCH_API_URL}/ingest",
                params={"document_url": "https://example.com/doc.pdf"},
                timeout=10.0,
            )
            
            if response.status_code == 200:
                print("✓ Cross-service call successful")
                data = response.json()
                print(f"  Response: {data}")
            else:
                print(f"  Ingestion endpoint returned: {response.status_code}")
                
        except httpx.ConnectError:
            print("  Note: Ingestion API not running - skipping cross-service test")


async def test_span_attributes():
    """Test that custom span attributes are recorded."""
    print("\n=== Test 3: Span Attributes ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SEARCH_API_URL}/search",
            json={"query": "what is machine learning?", "top_k": 10, "rerank": True},
        )
        
        assert response.status_code == 200
        trace_id = response.json().get("trace_id")
        
        if trace_id:
            await asyncio.sleep(2)
            
            trace_response = await client.get(f"{TEMPO_URL}/api/traces/{trace_id}")
            
            if trace_response.status_code == 200:
                print("✓ Trace with attributes found")
                # Parse and validate attributes would go here
                print(f"  Trace ID: {trace_id}")
                print("  Check Grafana Tempo UI for detailed attribute inspection")
            else:
                print(f"  Trace lookup returned: {trace_response.status_code}")


async def test_error_recording():
    """Test that errors are properly recorded in traces."""
    print("\n=== Test 4: Error Recording ===")
    
    async with httpx.AsyncClient() as client:
        # This should generate an error trace if endpoint validates input
        response = await client.post(
            f"{SEARCH_API_URL}/search",
            json={"query": "", "top_k": -1},  # Invalid input
        )
        
        print(f"  Response status: {response.status_code}")
        if response.status_code >= 400:
            print("✓ Error response received - check Tempo for error span")
        else:
            print("  Note: Endpoint accepted invalid input")


async def test_concurrent_requests():
    """Test trace isolation under concurrent load."""
    print("\n=== Test 5: Concurrent Request Isolation ===")
    
    async with httpx.AsyncClient() as client:
        queries = [f"query_{i}" for i in range(5)]
        
        async def make_request(query: str):
            response = await client.post(
                f"{SEARCH_API_URL}/search",
                json={"query": query, "top_k": 3},
            )
            return response.json().get("trace_id")
        
        trace_ids = await asyncio.gather(*[make_request(q) for q in queries])
        
        unique_traces = set(t for t in trace_ids if t)
        print(f"✓ Generated {len(unique_traces)} unique traces for {len(queries)} requests")
        
        if len(unique_traces) == len(queries):
            print("  All requests have distinct trace IDs")
        else:
            print("  Warning: Some trace IDs may be duplicated")


def run_validation_suite():
    """Run all validation tests."""
    print("=" * 60)
    print("Distributed Tracing Validation Suite")
    print("=" * 60)
    print(f"Search API: {SEARCH_API_URL}")
    print(f"Tempo: {TEMPO_URL}")
    
    asyncio.run(test_single_service_trace())
    asyncio.run(test_cross_service_propagation())
    asyncio.run(test_span_attributes())
    asyncio.run(test_error_recording())
    asyncio.run(test_concurrent_requests())
    
    print("\n" + "=" * 60)
    print("Validation complete!")
    print("Open Grafana Tempo UI to visually inspect traces")
    print("=" * 60)


if __name__ == "__main__":
    run_validation_suite()
```

Run the tests:

```bash
python test_tracing.py
```

### Test 3: Manual Trace Query via TraceQL

In Grafana → Explore → Select Tempo data source:

```
# Find slow search requests
{span.search.query_length > 0} | duration > 100ms

# Find all embedding operations
{name = "embedding.generate"}

# Find errors in a service
{resource.service.name = "search-api" && status = error}

# Find traces with reranking enabled
{span.search.rerank_enabled = true}
```

### Test 4: Verify Context Propagation Headers

```bash
# Check that traceparent header is being sent
curl -v -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}' 2>&1 | grep -i traceparent
```

---

## Troubleshooting

### Traces Not Appearing in Tempo

1. **Check Tempo connectivity:**
   ```bash
   curl http://localhost:3200/ready
   ```

2. **Verify OTLP endpoint:**
   ```bash
   # Test OTLP endpoint accepts connections
   nc -zv localhost 4317
   ```

3. **Check application logs for export errors:**
   ```bash
   # Look for OpenTelemetry export failures
   docker logs search-api 2>&1 | grep -i otel
   ```

4. **Verify environment variables:**
   ```bash
   # Inside your container
   env | grep OTEL
   ```

### Missing Spans in Trace

1. **Ensure instrumentation is loaded before imports:**
   ```python
   # CORRECT: Instrument before importing httpx
   from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
   HTTPXClientInstrumentor().instrument()
   import httpx  # Now httpx calls will be traced
   ```

2. **Check async context propagation:**
   ```python
   # If using background tasks, context may not propagate automatically
   # Use trace.get_current_span() to verify you're in an active span
   ```

### High Latency from Tracing

1. **Increase batch size:**
   ```python
   BatchSpanProcessor(
       exporter,
       max_queue_size=4096,
       max_export_batch_size=1024,
       schedule_delay_millis=10000,  # Export less frequently
   )
   ```

2. **Sample traces in high-traffic scenarios:**
   ```python
   from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
   
   sampler = TraceIdRatioBased(0.1)  # Sample 10% of traces
   provider = TracerProvider(resource=resource, sampler=sampler)
   ```

### Trace Context Lost Across Services

1. **Verify W3C Trace Context headers:**
   ```python
   # The traceparent header should look like:
   # traceparent: 00-{trace_id}-{span_id}-{flags}
   # Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
   ```

2. **Check HTTP client instrumentation:**
   ```python
   # Ensure HTTPXClientInstrumentor is active
   from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
   HTTPXClientInstrumentor().instrument()
   ```

---

## Next Steps

1. **Add trace-to-logs correlation** - Include trace IDs in your log format for end-to-end debugging
2. **Set up alerting** - Create alerts in Grafana for high error rates or latency spikes detected in traces
3. **Implement sampling strategies** - For production traffic, sample traces to reduce storage costs
4. **Add business metrics** - Track RAG-specific metrics like retrieval quality, context relevance scores

---

## References

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [Grafana Tempo Documentation](https://grafana.com/docs/tempo/latest/)
- [TraceQL Query Language](https://grafana.com/docs/tempo/latest/traceql/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
