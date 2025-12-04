# X-RAG System Architecture Diagram

**Generated:** 2025-12-04
**Based on:** Actual codebase analysis

---

## System Overview

```mermaid
flowchart TB
    subgraph External["External (Host Machine)"]
        User["👤 User/Browser"]
        Client["📱 API Client"]
    end

    subgraph KindCluster["Kind Kubernetes Cluster (xrag-k8)"]
        subgraph ControlPlane["Control Plane (Port Mappings)"]
            PM8080["Port 8080"]
            PM8082["Port 8082"]
            PM8081["Port 8081"]
            PM3000["Port 3000"]
            PM9090["Port 9090"]
        end

        subgraph RagSystem["Namespace: rag-system"]

            subgraph AppLayer["Application Services"]
                SearchUI["Search UI<br/>(FastAPI)<br/>Port 8080"]
                SearchService["Search Service<br/>(gRPC)<br/>Port 50052"]
                EmbeddingService["Embedding Service<br/>(gRPC)<br/>Port 50051"]
                IngestionAPI["Ingestion API<br/>(FastAPI)<br/>Port 8082"]
                Indexer["Indexer<br/>(Kafka Consumer)<br/>Port 8080/8081"]
            end

            subgraph DataLayer["Data Layer"]
                Weaviate["Weaviate<br/>(Vector DB)<br/>Port 8080"]
                Kafka["Kafka<br/>(Message Queue)<br/>Port 9092"]
                MinIO["MinIO<br/>(Object Storage)<br/>Port 9000"]
                Redis["Redis<br/>(Cache)<br/>Port 6379"]
            end

            subgraph Observability["Observability"]
                Prometheus["Prometheus<br/>Port 9090"]
                Grafana["Grafana<br/>Port 3000"]
            end
        end
    end

    subgraph ExternalAPIs["External LLM Providers"]
        OpenAI["OpenAI API<br/>(gpt-4o-mini)"]
        LMStudio["LM Studio<br/>(Local, Optional)"]
    end

    subgraph EmbeddingBackends["Embedding Backends"]
        OpenAIEmbed["OpenAI Embeddings<br/>(text-embedding-3-small)"]
        HashBased["Hash-Based<br/>(Development)"]
        BGEEmbed["BGE Embeddings<br/>(via LM Studio)"]
    end

    %% User connections through port mappings
    User -->|"HTTP :8080"| PM8080
    Client -->|"HTTP :8082<br/>POST /ingest"| PM8082
    User -->|"HTTP :8081<br/>Weaviate Console"| PM8081
    User -->|"HTTP :3000<br/>Dashboards"| PM3000
    User -->|"HTTP :9090<br/>PromQL"| PM9090

    %% Port mappings to services
    PM8080 --> SearchUI
    PM8082 --> IngestionAPI
    PM8081 --> Weaviate
    PM3000 --> Grafana
    PM9090 --> Prometheus

    %% Search flow (gRPC)
    SearchUI -->|"gRPC :50052<br/>Search()"| SearchService
    SearchService -->|"gRPC :50051<br/>Embed()"| EmbeddingService
    SearchService -->|"HTTP :8080<br/>Vector/BM25/Hybrid"| Weaviate
    SearchService -->|"HTTPS<br/>ChatCompletion"| OpenAI
    SearchService -.->|"HTTP :8000<br/>(Optional)"| LMStudio

    %% Ingestion flow (async)
    IngestionAPI -->|"HTTP :9000<br/>PutObject"| MinIO
    IngestionAPI -->|"TCP :9092<br/>Produce"| Kafka

    Kafka -->|"TCP :9092<br/>Consume"| Indexer
    Indexer -->|"HTTP :9000<br/>GetObject"| MinIO
    Indexer -->|"gRPC :50051<br/>EmbedBatch()"| EmbeddingService
    Indexer -->|"HTTP :8080<br/>BatchInsert"| Weaviate

    %% Embedding backends
    EmbeddingService -->|"HTTPS"| OpenAIEmbed
    EmbeddingService -.->|"Local"| HashBased
    EmbeddingService -.->|"HTTP :8000"| BGEEmbed

    %% Observability
    Prometheus -->|"Scrape /metrics"| SearchUI
    Prometheus -->|"Scrape /metrics"| SearchService
    Prometheus -->|"Scrape /metrics"| EmbeddingService
    Prometheus -->|"Scrape /metrics"| IngestionAPI
    Prometheus -->|"Scrape /metrics"| Indexer
    Grafana -->|"PromQL"| Prometheus

    %% Optional cache
    SearchService -.->|"TCP :6379<br/>(Optional)"| Redis

    %% Styling
    classDef external fill:#e1f5fe,stroke:#01579b
    classDef app fill:#fff3e0,stroke:#e65100
    classDef data fill:#e8f5e9,stroke:#2e7d32
    classDef obs fill:#f3e5f5,stroke:#7b1fa2
    classDef extapi fill:#fce4ec,stroke:#c2185b
    classDef port fill:#eceff1,stroke:#546e7a
    classDef backend fill:#fff8e1,stroke:#f9a825

    class User,Client external
    class SearchUI,SearchService,EmbeddingService,IngestionAPI,Indexer app
    class Weaviate,Kafka,MinIO,Redis data
    class Prometheus,Grafana obs
    class OpenAI,LMStudio extapi
    class PM8080,PM8082,PM8081,PM3000,PM9090 port
    class OpenAIEmbed,HashBased,BGEEmbed backend
```

---

## Search Flow (Synchronous)

```mermaid
sequenceDiagram
    autonumber
    participant User as User Browser
    participant UI as Search UI<br/>(FastAPI :8080)
    participant SS as Search Service<br/>(gRPC :50052)
    participant ES as Embedding Service<br/>(gRPC :50051)
    participant WV as Weaviate<br/>(:8080)
    participant LLM as OpenAI/LM Studio

    User->>UI: GET / (Web Interface)
    UI-->>User: index.html

    User->>UI: POST /api/search<br/>{query, mode, top_k}
    UI->>SS: gRPC Search()

    SS->>ES: gRPC Embed(query)
    ES-->>SS: float[] embedding

    SS->>WV: Query DocumentChunk<br/>(vector/bm25/hybrid)
    WV-->>SS: SearchResult[]<br/>{content, score, metadata}

    SS->>SS: Build context from results<br/>(max 4000 chars)

    SS->>LLM: ChatCompletion<br/>(context + query)
    LLM-->>SS: Generated answer

    SS-->>UI: SearchResponse<br/>{answer, sources[]}
    UI-->>User: JSON response + render
```

### Search Flow Details

| Step | Component | Action | Configuration |
|------|-----------|--------|---------------|
| 1-2 | Search UI | Serve web interface | Templates in `src/search_ui/templates/` |
| 3 | Search UI | Forward search request | gRPC client to `search-service:50052` |
| 4-5 | Search Service | Generate query embedding | Via Embedding Service gRPC |
| 6-7 | Search Service | Retrieve documents | Weaviate collection: `DocumentChunk` |
| 8 | Search Service | Build RAG context | Max 4000 characters |
| 9-10 | Search Service | Generate answer | Model: `gpt-4o-mini` (configurable) |
| 11-12 | Search UI | Return results | JSON with answer + sources |

### Search Modes

| Mode | Algorithm | Use Case |
|------|-----------|----------|
| `vector` | Cosine similarity on embeddings | Semantic similarity search |
| `bm25` | BM25F keyword matching | Exact keyword matching |
| `hybrid` | Combined (alpha=0.5) | Best of both (default) |

---

## Ingestion Flow (Asynchronous)

```mermaid
sequenceDiagram
    autonumber
    participant Client as API Client
    participant API as Ingestion API<br/>(FastAPI :8082)
    participant MIO as MinIO<br/>(:9000)
    participant KFK as Kafka<br/>(:9092)
    participant IDX as Indexer<br/>(Consumer)
    participant ES as Embedding Service<br/>(gRPC :50051)
    participant WV as Weaviate<br/>(:8080)

    Client->>API: POST /ingest<br/>{text, metadata, namespace}

    API->>API: Validate request<br/>(title, source_file)
    API->>MIO: PutObject<br/>(bucket: documents)
    MIO-->>API: OK

    API->>KFK: Produce event<br/>(topic: document-changes)
    KFK-->>API: ACK

    API-->>Client: 202 Accepted<br/>{document_id, status}

    Note over KFK,IDX: Asynchronous Processing

    KFK->>IDX: Consume event
    IDX->>MIO: GetObject<br/>(document_id.json)
    MIO-->>IDX: Document content

    IDX->>IDX: Chunk document<br/>(500 chars, 50 overlap)

    loop For each batch of 10 chunks
        IDX->>ES: gRPC EmbedBatch()
        ES-->>IDX: float[][] embeddings
    end

    IDX->>WV: Batch insert<br/>(DocumentChunk collection)
    WV-->>IDX: OK

    Note over WV: Document now searchable
```

### Ingestion Flow Details

| Step | Component | Action | Configuration |
|------|-----------|--------|---------------|
| 1 | Client | Upload document | `POST /ingest` with JSON body |
| 2 | Ingestion API | Validate metadata | title (1-512 chars), source_file |
| 3-4 | Ingestion API | Store raw document | MinIO bucket: `documents` |
| 5-6 | Ingestion API | Publish event | Kafka topic: `document-changes` |
| 7 | Ingestion API | Return immediately | 202 Accepted (async processing) |
| 8-10 | Indexer | Retrieve document | From MinIO via document_id |
| 11 | Indexer | Chunk document | 500 chars, 50 char overlap |
| 12-13 | Indexer | Generate embeddings | Batches of 10 chunks |
| 14-15 | Indexer | Store in Weaviate | DocumentChunk collection |

---

## Port Mappings

### External Access (Host → Cluster)

| Host Port | NodePort | Service | Protocol | Description |
|-----------|----------|---------|----------|-------------|
| 8080 | 30080 | Search UI | HTTP | Web interface for search |
| 8082 | 30082 | Ingestion API | HTTP | Document upload endpoint |
| 8081 | 30081 | Weaviate | HTTP | Vector database console |
| 3000 | 30030 | Grafana | HTTP | Monitoring dashboards |
| 9090 | 30090 | Prometheus | HTTP | Metrics query interface |

### Internal Services (ClusterIP)

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Search Service | 50052 | gRPC | Search RPC endpoint |
| Embedding Service | 50051 | gRPC | Embedding generation |
| Weaviate | 8080 | HTTP | Vector DB API |
| Kafka | 9092 | TCP | Message queue |
| MinIO | 9000 | HTTP | Object storage API |
| Redis | 6379 | TCP | Cache (optional) |

### Metrics Endpoints

| Service | Metrics Port | Path |
|---------|--------------|------|
| Search UI | 9091 | `/metrics` |
| Search Service | 8080 | `/metrics` |
| Embedding Service | 8080 | `/metrics` |
| Ingestion API | 8080 | `/metrics` |
| Indexer | 8081 | `/metrics` |

---

## Service Dependencies

```mermaid
graph LR
    subgraph Required["Required Dependencies"]
        UI[Search UI] --> SS[Search Service]
        SS --> ES[Embedding Service]
        SS --> WV[Weaviate]
        SS --> LLM[OpenAI/LM Studio]
        IDX[Indexer] --> ES
        IDX --> WV
        IDX --> MIO[MinIO]
        API[Ingestion API] --> MIO
        API --> KFK[Kafka]
        KFK --> IDX
    end

    subgraph Optional["Optional Dependencies"]
        SS -.-> Redis
    end

    style Required fill:#e8f5e9
    style Optional fill:#fff3e0
```

### Dependency Matrix

| Service | Hard Dependencies | Soft Dependencies |
|---------|-------------------|-------------------|
| Search UI | Search Service | - |
| Search Service | Embedding Service, Weaviate, OpenAI | Redis (cache) |
| Embedding Service | Configured backend (no fallback - fails on misconfiguration) | - |
| Ingestion API | MinIO, Kafka | - |
| Indexer | Kafka, MinIO, Embedding Service, Weaviate | - |

---

## Health Check Architecture

### HTTP Services

| Service | Liveness | Readiness | Full Health |
|---------|----------|-----------|-------------|
| Search UI | `GET /health/live` | `GET /health/ready` | `GET /health` |
| Ingestion API | `GET /health/live` | `GET /health/ready` | `GET /health` |
| Indexer | `GET /health/live` | `GET /health/ready` | - |

### gRPC Services

| Service | Health Check |
|---------|--------------|
| Search Service | `grpc.health.v1.Health/Check` |
| Embedding Service | `grpc.health.v1.Health/Check` |

### Health Status Values

| Status | Code | Meaning |
|--------|------|---------|
| HEALTHY | 1 | All dependencies operational |
| DEGRADED | 2 | Some non-critical dependencies down |
| UNHEALTHY | 3 | Critical dependencies unavailable |

---

## Embedding Backends

The Embedding Service supports multiple backends. **No automatic fallback** - misconfiguration results in an error at startup.

| Backend | Config Value | Use Case | Dimension |
|---------|--------------|----------|-----------|
| OpenAI | `openai` | Production | 1536 |
| Hash-Based | `hash_based` | Development/Testing (deterministic, no API) | 384 |
| LM Studio (BGE) | `lm_studio` | Local/Privacy | 1024 |

Configuration via environment variable:
```bash
EMBEDDING_GENERATOR_TYPE=openai  # or hash_based, lm_studio
```

**Important:** An invalid or missing `EMBEDDING_GENERATOR_TYPE` will cause the service to fail immediately with a clear error message. This is intentional - silent fallbacks hide configuration problems.

---

## LLM Providers

The Search Service supports multiple LLM providers:

| Provider | Config | Model | Endpoint |
|----------|--------|-------|----------|
| OpenAI | `LLM_PROVIDER=openai` | gpt-4o-mini | api.openai.com |
| LM Studio | `LLM_PROVIDER=lm_studio` | (local model) | localhost:8000 |

---

## Weaviate Schema

### DocumentChunk Collection

```json
{
  "class": "DocumentChunk",
  "properties": [
    {"name": "content", "dataType": ["text"]},
    {"name": "doc_id", "dataType": ["text"]},
    {"name": "chunk_index", "dataType": ["int"]},
    {"name": "namespace", "dataType": ["text"]},
    {"name": "title", "dataType": ["text"]},
    {"name": "source_file", "dataType": ["text"]}
  ],
  "vectorizer": "none",
  "vectorIndexConfig": {
    "distance": "cosine"
  }
}
```

---

## Scaling Configuration

| Service | Default Replicas | Scalable | Notes |
|---------|------------------|----------|-------|
| Search UI | 1 | Yes | Stateless |
| Search Service | 2 | Yes | Stateless |
| Embedding Service | 2 | Yes | Stateless |
| Ingestion API | 2 | Yes | Stateless |
| Indexer | 1 | Limited | Single consumer for ordering |
| Weaviate | 1 | Yes* | StatefulSet |
| Kafka | 1 | Yes* | StatefulSet |
| Redis | 1 | Yes* | StatefulSet |
| MinIO | 1 | Yes* | StatefulSet |

*Infrastructure scaling requires additional configuration.

---

## Quick Commands

```bash
# Check cluster status
make cluster-status

# View service logs
make logs-search-ui
make logs-search-service
make logs-embedding
make logs-ingestion
make logs-indexer

# Access UIs
make open-search-ui        # http://localhost:8080
make open-ingestion-api    # http://localhost:8082/docs
make open-grafana          # http://localhost:3000
make open-weaviate         # http://localhost:8081

# Scale services
kubectl scale deployment search-service --replicas=5 -n rag-system
kubectl scale deployment embedding-service --replicas=4 -n rag-system
```
