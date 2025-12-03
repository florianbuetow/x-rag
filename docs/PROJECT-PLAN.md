# X-RAG Infrastructure Setup & Project Structure Plan

## Overview

This plan details the setup of infrastructure and project structure for X-RAG, a production-grade RAG platform using:
- **Language**: Python 3.11+ for all services
- **Validation**: Pydantic for data models
- **RAG Framework**: Haystack for retrieval pipelines
- **Internal Communication**: gRPC for service-to-service
- **External APIs**: FastAPI REST/HTTP for user-facing endpoints
- **Infrastructure**: Kubernetes (Kind) for local development

## Architecture Summary

### Communication Pattern
```
External Users (HTTP/REST)
    ↓
[Search UI - FastAPI] ←─gRPC─→ [Search Service - gRPC Server] ←─gRPC─→ [Embedding Service - gRPC Server]
    (Web Interface)              (RAG Pipeline Logic)                   (Embeddings)
                                         ↓
                                     Weaviate
                                         ↑
[Ingestion API - FastAPI] ──→ Kafka → [Indexer - Consumer] ─gRPC→ [Embedding Service]
    (Document Upload)                  (Processing)                    (Embeddings)
                                         ↓
                                     Weaviate
```

### Services
1. **Search UI** (FastAPI REST) - User-facing web interface, calls Search Service via gRPC
2. **Search Service** (gRPC Server) - Backend search logic, uses Haystack pipelines, calls Embedding Service
3. **Ingestion API** (FastAPI REST) - External document upload endpoint
4. **Embedding Service** (gRPC Server) - Internal embedding generation service
5. **Indexer** (Kafka Consumer) - Background document processing, calls Embedding Service via gRPC

## 1. Makefile Structure

### 1.1 Main Targets

```makefile
.PHONY: help check setup status clean reset build deploy-apps dev-* test logs-*

# Default target
help:
    Display comprehensive command reference

# Setup lifecycle
check:
    Validate prerequisites (Docker, kubectl, Kind, Helm, Python 3.11+, uv)
    - Check tool versions
    - Validate Docker resources (6GB+ RAM, 4+ CPUs)
    - Check port availability (8080, 8081, 8082, 3000, 9090, 5000)
    - Display actionable error messages with install instructions

setup:
    Complete infrastructure setup with checkpoint-based resumption
    - Run prerequisite checks
    - Create Kind cluster with local registry
    - Deploy infrastructure (Redis, MinIO, Kafka, Weaviate)
    - Deploy monitoring (Prometheus, Grafana)
    - Verify all services are healthy

status:
    Display system health
    - Cluster status
    - Pod readiness
    - Service endpoints
    - Resource usage

# Development workflow
dev-search:
    Run Search API locally with hot reload
    Uses: uv run uvicorn src.search_api.main:app --reload

dev-ingest:
    Run Ingestion API locally with hot reload

dev-embedding:
    Run Embedding Service (gRPC) locally

build:
    Build all Docker images using uv
    - Build with layer caching
    - Push to localhost:5000
    - Tag with git SHA

deploy-apps:
    Deploy application services to cluster
    - Search API
    - Ingestion API
    - Embedding Service
    - Indexer

# Testing
test:
    Run all tests using pytest

test-e2e:
    Run end-to-end integration tests

# Monitoring
logs-search:
    Tail Search API logs

logs-ingest:
    Tail Ingestion API logs

logs-embedding:
    Tail Embedding Service logs

logs-indexer:
    Tail Indexer logs

# Cleanup
clean:
    Interactive cleanup with confirmation
    - Prompt before deletion
    - Delete cluster
    - Remove checkpoints
    - Optionally remove data/

reset:
    clean + setup (fresh start)
```

### 1.2 Implementation Details

#### Prerequisite Checking (Check-Only, No Auto-Install)

```makefile
.check-prerequisites:
    @echo "Checking prerequisites..."
    @$(MAKE) .check-docker
    @$(MAKE) .check-kubectl
    @$(MAKE) .check-kind
    @$(MAKE) .check-helm
    @$(MAKE) .check-python
    @$(MAKE) .check-uv
    @$(MAKE) .check-docker-resources
    @$(MAKE) .check-ports
    @echo "✓ All prerequisites met"

.check-docker:
    - Check docker command exists
    - Check Docker daemon is running
    - Display version
    - On failure: Show install instructions for macOS/Linux

.check-python:
    - Check python3 command exists
    - Verify version >= 3.11
    - On failure: Link to python.org/downloads

.check-uv:
    - Check uv command exists
    - On failure: Show install command (curl -LsSf https://astral.sh/uv/install.sh | sh)

.check-docker-resources:
    - Parse docker info for memory and CPUs
    - Verify >= 6GB RAM, >= 4 CPUs
    - On failure: Show how to increase in Docker Desktop settings

.check-ports:
    - Use lsof to check ports 8080, 8081, 8082, 3000, 9090, 5000
    - On conflict: Display which process is using port and how to resolve
```

#### Checkpoint-Based Setup (Idempotent)

Uses `.setup/` directory for checkpoint markers:
- `.setup/prerequisites.done` - Prerequisites validated
- `.setup/cluster.done` - Cluster created
- `.setup/registry.done` - Registry running
- `.setup/infrastructure.done` - Infrastructure deployed
- `.setup/monitoring.done` - Monitoring deployed

```makefile
.setup-cluster:
    if [ -f .setup/cluster.done ]; then
        verify cluster health
        if healthy: skip
        if unhealthy: delete and recreate
    else
        create cluster
        create namespace
        mark checkpoint
```

## 2. Directory Structure

```
x-rag/
├── .gitignore
├── .env.example                  # Environment variable template
├── Makefile                      # Main developer interface
├── pyproject.toml                # Python dependencies (uv)
├── README.md
├── SETUP.md
├── SYSTEM-DIAGRAM.md
│
├── .setup/                       # Checkpoints (gitignored)
│   ├── prerequisites.done
│   ├── cluster.done
│   ├── registry.done
│   ├── infrastructure.done
│   └── monitoring.done
│
├── .venv/                        # UV virtual environment (gitignored)
│
├── data/
│   └── storage/                  # Kind PV mount (gitignored)
│       └── .gitkeep
│
├── docs/
│   ├── QUICKSTART.md             # 3-minute setup guide
│   ├── TROUBLESHOOTING.md        # Common issues & solutions
│   └── ARCHITECTURE.md           # System design details
│
├── proto/                        # gRPC Protocol Buffers
│   ├── embedding.proto           # Embedding service definitions
│   └── common.proto              # Shared message types
│
├── infra/
│   ├── kind/
│   │   └── cluster-config.yaml   # Kind cluster topology
│   │
│   ├── k8s/
│   │   ├── weaviate/
│   │   │   ├── weaviate.yaml
│   │   │   └── schema-init.yaml
│   │   ├── kafka/
│   │   │   └── kafka.yaml
│   │   ├── minio/
│   │   │   └── minio.yaml
│   │   ├── redis/
│   │   │   └── redis.yaml
│   │   ├── monitoring/
│   │   │   ├── prometheus.yaml
│   │   │   └── grafana.yaml
│   │   ├── search-ui/
│   │   │   ├── deployment.yaml
│   │   │   └── service.yaml
│   │   ├── search-service/
│   │   │   ├── deployment.yaml
│   │   │   └── service.yaml
│   │   ├── ingestion-api/
│   │   │   ├── deployment.yaml
│   │   │   └── service.yaml
│   │   ├── embedding-service/
│   │   │   ├── deployment.yaml
│   │   │   └── service.yaml
│   │   └── indexer/
│   │       └── deployment.yaml
│   │
│   └── docker/
│       ├── Dockerfile.search-ui
│       ├── Dockerfile.search-service
│       ├── Dockerfile.ingestion-api
│       ├── Dockerfile.embedding-service
│       └── Dockerfile.indexer
│
├── scripts/
│   ├── check-prerequisites.sh    # Comprehensive prerequisite validation
│   ├── check-docker-resources.sh # Docker resource checker
│   ├── check-ports.sh            # Port conflict checker
│   ├── create-cluster.sh         # Idempotent cluster creation
│   ├── setup-registry.sh         # Local registry setup
│   ├── deploy-infrastructure.sh  # Infrastructure deployment with wait logic
│   ├── deploy-monitoring.sh      # Monitoring stack deployment
│   ├── deploy-apps.sh            # Application deployment
│   ├── generate-grpc.sh          # Generate Python gRPC code from protos
│   └── troubleshoot.sh           # Diagnostic script
│
├── src/
│   ├── __init__.py
│   │
│   ├── proto_gen/                # Generated gRPC code (gitignored)
│   │   ├── __init__.py
│   │   ├── embedding_pb2.py
│   │   ├── embedding_pb2_grpc.py
│   │   ├── search_pb2.py
│   │   ├── search_pb2_grpc.py
│   │   └── common_pb2.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── interfaces.py         # Python Protocol definitions (Haystack compatible)
│   │   ├── document.py           # CoreDocument model
│   │   └── errors.py             # Custom exceptions
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── health.py             # Reusable health check infrastructure
│   │   ├── config.py             # Base configuration with validation
│   │   ├── metrics.py            # Prometheus metrics helpers
│   │   └── grpc_utils.py         # gRPC client/server utilities
│   │
│   ├── retrievers/
│   │   ├── __init__.py
│   │   └── weaviate_haystack.py  # Haystack-compatible Weaviate retriever
│   │
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── search_pipeline.py    # Haystack search pipeline
│   │   └── indexing_pipeline.py  # Haystack indexing pipeline
│   │
│   ├── search_ui/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI web interface
│   │   ├── models.py             # Pydantic request/response models
│   │   ├── config.py             # Environment configuration
│   │   ├── grpc_clients.py       # gRPC client for Search Service
│   │   └── templates/            # HTML templates (optional)
│   │       └── index.html
│   │
│   ├── search_service/
│   │   ├── __init__.py
│   │   ├── main.py               # gRPC server entrypoint
│   │   ├── server.py             # gRPC servicer with Haystack pipelines
│   │   ├── config.py             # Environment configuration
│   │   └── grpc_clients.py       # gRPC client for Embedding Service
│   │
│   ├── ingestion_api/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app
│   │   ├── models.py             # Pydantic models
│   │   └── config.py
│   │
│   ├── embedding_service/
│   │   ├── __init__.py
│   │   ├── main.py               # gRPC server entrypoint
│   │   ├── server.py             # gRPC servicer implementation
│   │   ├── config.py             # Configuration
│   │   └── backends/
│   │       ├── __init__.py
│   │       ├── base.py           # Backend protocol
│   │       └── openai.py         # OpenAI embeddings
│   │
│   └── indexer/
│       ├── __init__.py
│       ├── main.py               # Entrypoint
│       ├── consumer.py           # Kafka consumer
│       ├── processor.py          # Document processing with Haystack
│       ├── config.py             # Configuration
│       └── grpc_clients.py       # gRPC client for Embedding Service
│
└── tests/
    ├── __init__.py
    ├── conftest.py               # Pytest fixtures
    ├── test_health.py            # Health check tests
    ├── test_config.py            # Configuration validation tests
    ├── test_grpc.py              # gRPC communication tests
    └── test_e2e.py               # End-to-end tests
```

## 3. Technology Stack & Dependencies

### 3.1 pyproject.toml

```toml
[project]
name = "x-rag"
version = "0.1.0"
description = "X-RAG: Distributed Search & Indexing for RAG"
requires-python = ">=3.11"
dependencies = [
    # Web framework
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",

    # Data validation
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",

    # Haystack for RAG
    "haystack-ai>=2.0.0",
    "weaviate-haystack>=2.0.0",

    # gRPC
    "grpcio>=1.60.0",
    "grpcio-tools>=1.60.0",
    "grpcio-reflection>=1.60.0",

    # HTTP client
    "httpx>=0.25.0",

    # Databases/Caching
    "redis[hiredis]>=5.0.0",
    "weaviate-client>=4.0.0",

    # LLM/Embeddings
    "openai>=1.3.0",

    # Messaging
    "aiokafka>=0.9.0",

    # Object storage
    "boto3>=1.29.0",
    "minio>=7.2.0",

    # Observability
    "prometheus-client>=0.19.0",

    # Utilities
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "pytest-grpc>=0.8.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
    "mypy-protobuf>=3.5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"
```

## 4. gRPC Protocol Definitions

### 4.1 proto/common.proto

```protobuf
syntax = "proto3";

package xrag.common;

// Common message types
message Metadata {
  map<string, string> fields = 1;
}

message HealthCheckRequest {}

message HealthCheckResponse {
  enum Status {
    UNKNOWN = 0;
    HEALTHY = 1;
    DEGRADED = 2;
    UNHEALTHY = 3;
  }
  Status status = 1;
  map<string, string> dependencies = 2;
  string message = 3;
}
```

### 4.2 proto/embedding.proto

```protobuf
syntax = "proto3";

package xrag.embedding;

import "common.proto";

// Embedding service definition
service EmbeddingService {
  // Generate embeddings for texts
  rpc Embed(EmbedRequest) returns (EmbedResponse);

  // Batch embedding generation
  rpc EmbedBatch(EmbedBatchRequest) returns (EmbedBatchResponse);

  // Health check
  rpc HealthCheck(xrag.common.HealthCheckRequest) returns (xrag.common.HealthCheckResponse);
}

message EmbedRequest {
  string text = 1;
  string model = 2;  // e.g., "text-embedding-3-small"
  map<string, string> options = 3;
}

message EmbedResponse {
  repeated float embedding = 1;
  int32 dimension = 2;
  string model = 3;
}

message EmbedBatchRequest {
  repeated string texts = 1;
  string model = 2;
  map<string, string> options = 3;
}

message EmbedBatchResponse {
  repeated EmbedResponse embeddings = 1;
}
```

### 4.3 proto/search.proto

```protobuf
syntax = "proto3";

package xrag.search;

import "common.proto";

// Search service definition
service SearchService {
  // Perform search and generate answer
  rpc Search(SearchRequest) returns (SearchResponse);

  // Health check
  rpc HealthCheck(xrag.common.HealthCheckRequest) returns (xrag.common.HealthCheckResponse);
}

message SearchRequest {
  string query = 1;
  string namespace = 2;  // default: "default"
  int32 top_k = 3;       // default: 10
  string mode = 4;       // "vector", "bm25", or "hybrid"
  map<string, string> options = 5;
}

message Source {
  string id = 1;
  string content = 2;
  float score = 3;
  map<string, string> metadata = 4;
}

message SearchResponse {
  string answer = 1;
  repeated Source sources = 2;
  map<string, string> metadata = 3;
}
```

## 5. Service Stubs with Key Features

### 5.1 Search UI (FastAPI + gRPC Client)

**Purpose**: User-facing web interface, calls Search Service via gRPC

**Key Components**:
```python
# src/search_ui/main.py
- FastAPI app with CORS
- Health check endpoints (/health, /health/ready, /health/live)
- GET / (simple web form or serve static HTML)
- POST /api/search endpoint
- gRPC client for Search Service
- Prometheus metrics

# src/search_ui/grpc_clients.py
- SearchServiceClient wrapper
- Connection pooling
- Retry logic
- Error handling
```

**Health Check Strategy**:
- Check Search Service via gRPC (critical)
- Report status

### 5.2 Search Service (gRPC Server + Haystack)

**Purpose**: Backend search logic with Haystack pipelines, calls Embedding Service via gRPC

**Key Components**:
```python
# src/search_service/server.py
- SearchServiceServicer implementation
- Search() method with Haystack pipeline
- Uses Weaviate retriever
- Uses OpenAI generator
- Calls Embedding Service for query embeddings
- Redis caching
- HealthCheck() method

# src/search_service/main.py
- gRPC server initialization
- Signal handling for graceful shutdown
- Server reflection for debugging

# src/search_service/grpc_clients.py
- EmbeddingServiceClient wrapper
```

**Health Check Strategy**:
- Check Weaviate connectivity (critical)
- Check Redis connectivity (non-critical)
- Check Embedding Service via gRPC (critical)
- Report aggregate status

### 5.3 Ingestion API (FastAPI)

**Purpose**: External REST API for document upload, publishes to Kafka

**Key Components**:
```python
# src/ingestion_api/main.py
- FastAPI app
- POST /ingest endpoint
- Document validation with Pydantic
- MinIO upload
- Kafka event publishing
- Health checks

# src/ingestion_api/models.py
- DocumentUploadRequest (Pydantic)
- DocumentUploadResponse (Pydantic)
```

**Flow**:
1. Receive document via POST
2. Validate with Pydantic
3. Store raw document in MinIO
4. Publish event to Kafka topic
5. Return acknowledgment

### 5.4 Embedding Service (gRPC Server)

**Purpose**: Internal gRPC service for embedding generation

**Key Components**:
```python
# src/embedding_service/main.py
- gRPC server initialization
- Signal handling for graceful shutdown
- Server reflection for debugging

# src/embedding_service/server.py
- EmbeddingServiceServicer implementation
- Embed() method
- EmbedBatch() method (optimized batching)
- HealthCheck() method
- Backend abstraction (OpenAI, local models)

# src/embedding_service/backends/openai.py
- OpenAI API client
- Rate limiting
- Error handling with retries
```

**gRPC Features**:
- Server reflection for grpcurl debugging
- Health checking protocol
- Interceptors for logging/metrics
- Connection keepalive

### 5.5 Indexer (Kafka Consumer + gRPC Client)

**Purpose**: Background processor that consumes from Kafka, processes documents, calls Embedding Service

**Key Components**:
```python
# src/indexer/main.py
- Kafka consumer loop
- Graceful shutdown handling
- Health check HTTP server (for K8s probes)

# src/indexer/consumer.py
- AIOKafka consumer
- Batch processing
- Offset management
- Error handling with dead-letter queue

# src/indexer/processor.py
- Haystack indexing pipeline
- Document chunking
- Calls Embedding Service via gRPC
- Stores to Weaviate

# src/indexer/grpc_clients.py
- EmbeddingServiceClient
- Connection management
```

## 6. Common Modules

### 6.1 Health Check Infrastructure

```python
# src/common/health.py

class HealthChecker:
    """Aggregate health checker for services"""
    - add_dependency(name, check_func, critical=True)
    - check_all() -> Dict[str, Any]
    - Parallel execution of all checks
    - Aggregate status (healthy/degraded/unhealthy)

# Reusable checkers
async def check_weaviate(url: str) -> bool
async def check_redis(url: str) -> bool
async def check_kafka(bootstrap: str) -> bool
async def check_grpc_service(address: str, stub_class) -> bool
```

### 6.2 Configuration Validation

```python
# src/common/config.py

class BaseConfig(BaseModel):
    """Base configuration with environment loading"""
    - from_env(prefix: str) -> Self
    - Validates all required fields
    - Provides actionable error messages
    - Lists missing environment variables

def require_env_file(path: str = ".env"):
    """Check .env exists, guide user if not"""
```

### 6.3 gRPC Utilities

```python
# src/common/grpc_utils.py

class GrpcClient:
    """Base gRPC client with connection management"""
    - __init__(address: str, stub_class)
    - __enter__, __exit__ for context management
    - Automatic reconnection
    - Timeout handling
    - Error logging

def create_grpc_server(port: int, max_workers: int = 10) -> grpc.Server:
    """Create gRPC server with standard configuration"""
    - Thread pool
    - Compression
    - Max message sizes
    - Keepalive settings
```

## 7. Infrastructure Components

### 7.1 Kind Cluster Configuration

**File**: `infra/kind/cluster-config.yaml`

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: rag-hackathon

nodes:
  - role: control-plane
    extraPortMappings:
      # Search API
      - containerPort: 30080
        hostPort: 8080
      # Ingestion API
      - containerPort: 30082
        hostPort: 8082
      # Weaviate
      - containerPort: 30081
        hostPort: 8081
      # Grafana
      - containerPort: 30030
        hostPort: 3000
      # Prometheus
      - containerPort: 30090
        hostPort: 9090
    extraMounts:
      - hostPath: ./data/storage
        containerPath: /var/local-path-provisioner

  - role: worker
  - role: worker
```

### 7.2 Weaviate Deployment

**File**: `infra/k8s/weaviate/weaviate.yaml`

- StatefulSet with 1 replica
- PersistentVolumeClaim for data
- Resource limits (CPU: 2000m, Memory: 4Gi)
- Liveness/Readiness probes
- NodePort service (30081)

### 7.3 Kafka Deployment

**File**: `infra/k8s/kafka/kafka.yaml`

- Bitnami Kafka image with KRaft mode
- StatefulSet with 1 replica
- Auto-create topics enabled
- Topic: `document-changes`

### 7.4 Application Deployments

All applications use similar patterns:
- Deployment with configurable replicas
- ConfigMap for non-sensitive config
- Secret for sensitive data (OPENAI_API_KEY)
- Service with appropriate type (NodePort for external, ClusterIP for internal)
- Health check probes (liveness, readiness)
- Resource requests/limits

**gRPC Service Pattern**:
```yaml
# Embedding Service - gRPC only (ClusterIP)
apiVersion: v1
kind: Service
metadata:
  name: embedding-service
  namespace: rag-system
spec:
  type: ClusterIP
  ports:
    - port: 50051
      targetPort: 50051
      name: grpc
  selector:
    app: embedding-service
```

## 8. Scripts

### 8.1 Prerequisite Validation

**scripts/check-prerequisites.sh**
- Check all required tools
- Validate versions
- Display color-coded output (✓ green, ✗ red)
- Provide install instructions on failure
- Exit code 0 if all pass, 1 if any fail

**scripts/check-docker-resources.sh**
- Parse `docker info` for memory and CPU
- Validate >= 6GB RAM, >= 4 CPUs
- Warn if below recommended (10GB, 8 CPUs)

**scripts/check-ports.sh**
- Use `lsof` to check ports 8080, 8081, 8082, 3000, 9090, 5000
- Report conflicts with process names
- Suggest resolution steps

### 8.2 Cluster Management

**scripts/create-cluster.sh**
- Check for existing cluster
- Verify health if exists
- Create if missing or unhealthy
- Create namespace
- Wait for cluster ready

**scripts/setup-registry.sh**
- Create local registry container (localhost:5000)
- Connect to Kind network
- Create ConfigMap for registry info

### 8.3 Service Deployment

**scripts/deploy-infrastructure.sh**
- Deploy in dependency order:
  1. Redis (fast)
  2. MinIO (medium)
  3. Kafka (slow)
  4. Weaviate (slow)
- Wait for each to be Ready
- Run health checks
- Initialize Weaviate schema
- Report success/failure with debug commands

**scripts/deploy-monitoring.sh**
- Deploy Prometheus with scrape configs
- Deploy Grafana with datasource
- Wait for Ready
- Display access URLs

**scripts/deploy-apps.sh**
- Build Docker images
- Push to local registry
- Apply K8s manifests
- Wait for Ready
- Verify health endpoints

### 8.4 gRPC Code Generation

**scripts/generate-grpc.sh**
```bash
#!/bin/bash
# Generate Python code from protobuf definitions

python3 -m grpc_tools.protoc \
  -I proto \
  --python_out=src/proto_gen \
  --grpc_python_out=src/proto_gen \
  --mypy_out=src/proto_gen \
  proto/*.proto

# Fix imports in generated files
sed -i '' 's/^import common_pb2/from . import common_pb2/' src/proto_gen/*.py
```

## 9. Environment Configuration

### 9.1 .env.example

```bash
# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Internal Services (K8s cluster)
WEAVIATE_URL=http://weaviate:8080
KAFKA_BOOTSTRAP=kafka:9092
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
REDIS_URL=redis://redis:6379

# gRPC Services (internal)
EMBEDDING_SERVICE_ADDR=embedding-service:50051

# Local Development (when running outside K8s)
# WEAVIATE_URL=http://localhost:8081
# KAFKA_BOOTSTRAP=localhost:9092
# REDIS_URL=redis://localhost:6379
# EMBEDDING_SERVICE_ADDR=localhost:50051

# Application
LOG_LEVEL=INFO
CACHE_TTL=3600
```

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/test_health.py
- Test HealthChecker with all healthy dependencies
- Test critical dependency failure (status = unhealthy)
- Test non-critical failure (status = degraded)
- Test timeout handling

# tests/test_config.py
- Test valid configuration loading
- Test missing required fields
- Test invalid values (URL format, etc.)
- Test environment variable resolution

# tests/test_grpc.py
- Test EmbeddingService Embed() method
- Test EmbedBatch() method
- Test error handling
- Test connection retry logic
```

### 10.2 Integration Tests

```python
# tests/test_e2e.py
- Test full ingestion flow (API → Kafka → Indexer → Weaviate)
- Test search flow (API → Embedding Service → Weaviate → LLM)
- Test health endpoints on all services
- Test metrics endpoints
```

## 11. Haystack Integration

### 11.1 Search Pipeline

```python
# src/pipelines/search_pipeline.py

from haystack import Pipeline
from haystack.components.retrievers import WeaviateEmbeddingRetriever
from haystack.components.generators import OpenAIGenerator

def create_search_pipeline(weaviate_client, embedding_client):
    """Create Haystack RAG pipeline"""
    pipeline = Pipeline()

    # Add retriever
    pipeline.add_component(
        "retriever",
        WeaviateEmbeddingRetriever(
            client=weaviate_client,
            embedding_function=embedding_client.embed
        )
    )

    # Add generator
    pipeline.add_component(
        "generator",
        OpenAIGenerator(model="gpt-4")
    )

    # Connect components
    pipeline.connect("retriever", "generator")

    return pipeline
```

### 11.2 Indexing Pipeline

```python
# src/pipelines/indexing_pipeline.py

from haystack import Pipeline
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.writers import DocumentWriter

def create_indexing_pipeline(document_store):
    """Create Haystack document indexing pipeline"""
    pipeline = Pipeline()

    # Add cleaner
    pipeline.add_component("cleaner", DocumentCleaner())

    # Add splitter
    pipeline.add_component(
        "splitter",
        DocumentSplitter(split_by="word", split_length=200)
    )

    # Add writer
    pipeline.add_component(
        "writer",
        DocumentWriter(document_store=document_store)
    )

    # Connect
    pipeline.connect("cleaner", "splitter")
    pipeline.connect("splitter", "writer")

    return pipeline
```

## 12. Git Commit Strategy

**Important**: Create git commits after each milestone. Never attribute AI in commit messages.

### Commit Message Format
```
<type>: <description>

<optional body>
```

**Types**: feat, fix, docs, infra, test, refactor

### Example Commits
- `infra: add Makefile and setup scripts`
- `infra: add Kind cluster configuration`
- `feat: add Embedding Service gRPC implementation`
- `feat: add Search Service with Haystack pipeline`
- `docs: add QUICKSTART guide`

### Milestone Commits
After completing each phase below, create a commit:
- Phase 1: `git commit -m "infra: add foundation (Makefile, scripts, directory structure)"`
- Phase 2: `git commit -m "infra: add Kubernetes manifests for all services"`
- Phase 3: `git commit -m "feat: add gRPC protocol definitions"`
- And so on...

## 13. Implementation Phases

### Phase 0: Initial Setup
1. Create .gitignore (Python, Docker, macOS, IDE)
2. Commit: `git commit -m "chore: add .gitignore"`

### Phase 1: Foundation (Days 1-2)
1. Create Makefile with all targets
2. Create all scripts (check-prerequisites.sh, create-cluster.sh, etc.)
3. Create directory structure
4. Create pyproject.toml with all dependencies
5. Create .env.example
6. Test `make check` on fresh machine
7. **Commit**: `git commit -m "infra: add foundation (Makefile, scripts, structure)"`

### Phase 2: Infrastructure (Days 2-3)
1. Create Kind cluster configuration
2. Create Weaviate manifests
3. Create Kafka manifests
4. Create MinIO manifests
5. Create Redis manifests
6. Create Prometheus/Grafana manifests
7. Test `make setup` end-to-end
8. **Commit**: `git commit -m "infra: add Kubernetes manifests for infrastructure"`

### Phase 3: gRPC Layer (Day 3)
1. Define proto/common.proto
2. Define proto/embedding.proto
3. Create scripts/generate-grpc.sh
4. Create src/common/grpc_utils.py
5. Generate Python gRPC code
6. Test proto compilation
7. **Commit**: `git commit -m "feat: add gRPC protocol definitions"`

### Phase 4: Common Modules (Day 3-4)
1. Create src/core/interfaces.py
2. Create src/core/document.py
3. Create src/common/health.py
4. Create src/common/config.py
5. Create src/common/metrics.py
6. Write unit tests for common modules
7. **Commit**: `git commit -m "feat: add core modules and common utilities"`

### Phase 5: Embedding Service (Day 4)
1. Create src/embedding_service/server.py (gRPC servicer)
2. Create src/embedding_service/main.py
3. Create src/embedding_service/backends/openai.py
4. Create Dockerfile.embedding-service
5. Create K8s manifests
6. Test locally with grpcurl
7. Test in cluster
8. **Commit**: `git commit -m "feat: add Embedding Service (gRPC)"`

### Phase 6: Ingestion API (Day 5)
1. Create src/ingestion_api/main.py (FastAPI)
2. Create src/ingestion_api/models.py (Pydantic)
3. Create src/ingestion_api/config.py
4. Create Dockerfile.ingestion-api
5. Create K8s manifests
6. Test locally
7. Test in cluster
8. **Commit**: `git commit -m "feat: add Ingestion API (FastAPI)"`

### Phase 7: Indexer (Day 5-6)
1. Create src/indexer/consumer.py (Kafka)
2. Create src/indexer/processor.py (Haystack pipeline)
3. Create src/indexer/grpc_clients.py (Embedding Service client)
4. Create src/indexer/main.py
5. Create Dockerfile.indexer
6. Create K8s manifests
7. Test end-to-end: Ingest → Kafka → Indexer → Weaviate
8. **Commit**: `git commit -m "feat: add Indexer (Kafka consumer)"`

### Phase 8: Search Service (Day 6-7)
1. Create src/search_service/main.py (gRPC server)
2. Create src/search_service/server.py (Servicer with Haystack)
3. Create src/search_service/grpc_clients.py (Embedding Service client)
4. Create src/pipelines/search_pipeline.py (Haystack)
5. Create Dockerfile.search-service
6. Create K8s manifests
7. Test with grpcurl
8. **Commit**: `git commit -m "feat: add Search Service (gRPC with Haystack)"`

### Phase 8b: Search UI (Day 7)
1. Create src/search_ui/main.py (FastAPI)
2. Create src/search_ui/models.py (Pydantic)
3. Create src/search_ui/grpc_clients.py (Search Service client)
4. Create src/search_ui/templates/index.html (optional)
5. Create Dockerfile.search-ui
6. Create K8s manifests
7. Test end-to-end: UI → Search Service → Weaviate → LLM
8. **Commit**: `git commit -m "feat: add Search UI (FastAPI)"`

### Phase 9: Haystack Pipelines (Day 7-8)
1. Create src/pipelines/indexing_pipeline.py
2. Create src/pipelines/search_pipeline.py
3. Integrate into Indexer
4. Integrate into Search Service
5. Test pipelines
6. **Commit**: `git commit -m "feat: integrate Haystack pipelines"`

### Phase 10: Testing (Day 8)
1. Write unit tests (health, config, grpc)
2. Write integration tests (services)
3. Write E2E tests (full flows)
4. Create test fixtures
5. Test coverage report
6. **Commit**: `git commit -m "test: add comprehensive test suite"`

### Phase 11: Documentation (Day 8-9)
1. Write docs/QUICKSTART.md
2. Write docs/TROUBLESHOOTING.md
3. Write docs/ARCHITECTURE.md
4. Update README.md
5. Add inline code documentation
6. **Commit**: `git commit -m "docs: add comprehensive documentation"`

### Phase 12: Validation (Day 9)
1. Fresh clone on new machine
2. Run `make check`
3. Run `make setup`
4. Run `make build && make deploy-apps`
5. Test search endpoint
6. Test ingestion endpoint
7. Verify monitoring dashboards
8. Document any issues
9. **Final Commit**: `git commit -m "chore: validate complete system on fresh install"`

## 14. .gitignore Contents

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST
.venv/
venv/
ENV/
env/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
*.cover
*.log

# gRPC generated files
src/proto_gen/*.py
src/proto_gen/*.pyi
!src/proto_gen/__init__.py

# Setup checkpoints
.setup/
setup.log

# Data directories
data/storage/*
!data/storage/.gitkeep

# Environment
.env
.env.local
*.env

# Docker
*.tar
*.tar.gz

# Kubernetes
*.swp
*~

# macOS
.DS_Store
.AppleDouble
.LSOverride
Icon
._*
.DocumentRevisions-V100
.fseventsd
.Spotlight-V100
.TemporaryItems
.Trashes
.VolumeIcon.icns
.com.apple.timemachine.donotpresent
.AppleDB
.AppleDesktop
Network Trash Folder
Temporary Items
.apdisk

# IDE
.vscode/
.idea/
*.swp
*.swo
*.swn
*.bak
*~

# Logs
*.log
logs/
*.pid
*.seed
*.pid.lock

# OS
Thumbs.db
ehthumbs.db
Desktop.ini
```

## 15. Success Criteria

### For Setup (`make setup`)
- [ ] Completes in < 5 minutes
- [ ] All pods reach Ready state
- [ ] All health endpoints return 200
- [ ] Port mappings work (8080 for Search UI, 8081, 8082, 3000, 9090)
- [ ] Grafana accessible at localhost:3000
- [ ] Prometheus accessible at localhost:9090
- [ ] Search UI accessible at localhost:8080

### For Development Experience
- [ ] `make dev-search-ui` starts Search UI with hot reload
- [ ] `make dev-search-service` starts Search Service gRPC server
- [ ] `make dev-embedding` starts Embedding Service gRPC server
- [ ] `make test` runs all tests and passes
- [ ] `make logs-*` tails service logs correctly
- [ ] Error messages are actionable

### For Services
- [ ] Embedding Service responds to gRPC calls
- [ ] Search Service responds to gRPC calls with answers
- [ ] Search UI serves web interface and calls Search Service
- [ ] Ingestion API accepts documents
- [ ] Indexer processes documents from Kafka
- [ ] All services have working health checks
- [ ] All services expose Prometheus metrics

### For gRPC
- [ ] Embedding Service gRPC server starts
- [ ] Search Service gRPC server starts
- [ ] Search UI can call Search Service via gRPC
- [ ] Search Service can call Embedding Service via gRPC
- [ ] Indexer can call Embedding Service via gRPC
- [ ] grpcurl works for debugging
- [ ] Error handling works (retries, timeouts)

### For Haystack
- [ ] Search pipeline in Search Service retrieves and generates answers
- [ ] Indexing pipeline in Indexer chunks and stores documents
- [ ] Weaviate integration works
- [ ] LLM integration works

### For Git
- [ ] Commits created after each milestone
- [ ] No AI attribution in commit messages
- [ ] .gitignore excludes all temporary files
- [ ] Clean git status (no untracked generated files)

## 16. Critical Files to Create

### Highest Priority (Create First)
1. `.gitignore` - Exclude temporary files
2. `Makefile` - Main developer interface
3. `pyproject.toml` - Dependencies
4. `.env.example` - Configuration template
5. `scripts/check-prerequisites.sh` - Validation
6. `scripts/create-cluster.sh` - Cluster setup
7. `infra/kind/cluster-config.yaml` - Cluster config

### gRPC Foundation
8. `proto/common.proto` - Common messages
9. `proto/embedding.proto` - Embedding service
10. `proto/search.proto` - Search service
11. `scripts/generate-grpc.sh` - Code generation
12. `src/common/grpc_utils.py` - gRPC utilities

### Core Services
13. `src/embedding_service/server.py` - Embedding gRPC server
14. `src/search_service/server.py` - Search gRPC server
15. `src/search_ui/main.py` - Search UI (FastAPI)
16. `src/ingestion_api/main.py` - Ingestion API
17. `src/indexer/main.py` - Indexer

### Infrastructure
18. `infra/k8s/weaviate/weaviate.yaml` - Vector DB
19. `infra/k8s/kafka/kafka.yaml` - Message queue
20. `infra/docker/Dockerfile.search-ui` - Docker build
21. `infra/docker/Dockerfile.search-service` - Docker build
22. `scripts/deploy-infrastructure.sh` - Deployment

## 17. Key Design Decisions

### gRPC vs REST
- **Internal services**: gRPC (Embedding Service, Search Service)
  - Reasons: Better performance, type safety, streaming support
- **External APIs**: REST/HTTP (Search UI, Ingestion API)
  - Reasons: Easier client integration, browser compatibility
- **Architecture**: Search UI (REST) → Search Service (gRPC) → Embedding Service (gRPC)
  - Separation of presentation layer from business logic
  - Search Service can be called by multiple frontends

### Haystack Framework
- Use Haystack for RAG pipelines
- Provides pre-built components (retrievers, generators)
- Easier to extend and customize
- Better integration with Weaviate

### Checkpoint-Based Setup
- Use `.setup/` directory for state tracking
- Makes setup idempotent
- Allows resuming from failures
- Clear indicator of what's complete

### Health Check Levels
- **Liveness**: Process alive (simple)
- **Readiness**: Can serve traffic (checks critical dependencies)
- **Health**: Detailed status (checks all dependencies, non-critical included)

### Error Handling Philosophy
- Every error should be actionable
- Include troubleshooting steps
- Link to documentation
- Show debug commands

This plan provides a complete roadmap for setting up the X-RAG infrastructure with Python, Pydantic, Haystack, gRPC internal communication, and REST external APIs, all running on Kind Kubernetes.
