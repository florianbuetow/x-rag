# X-RAG Infrastructure Overview

This diagram provides a high-level view of the X-RAG system architecture, showing all services and infrastructure components running within a Kubernetes cluster.

```mermaid
flowchart TB
    subgraph External["External"]
        User["👤 User / Client"]
        Browser["🌐 Browser"]
    end

    subgraph K8s["Kubernetes Cluster (Kind)"]

        subgraph Services["Application Services"]
            SearchUI["Search UI<br/>(FastAPI)<br/>:8080"]
            SearchService["Search Service<br/>(gRPC)<br/>:50052"]
            IngestionAPI["Ingestion API<br/>(FastAPI)<br/>:8082"]
            Indexer["Indexer<br/>(Kafka Consumer)"]
            EmbeddingService["Embedding Service<br/>(gRPC)<br/>:50051"]
            LLMService["LLM Inference Service<br/>(gRPC/HTTP)"]
        end

        subgraph DataStores["Data Stores"]
            Weaviate["Weaviate<br/>(Vector DB)<br/>:8081"]
            Redis["Redis<br/>(Cache)<br/>:6379"]
            MinIO["MinIO<br/>(Object Storage)<br/>:9000"]
        end

        subgraph Messaging["Message Queue"]
            Kafka["Kafka<br/>(Event Streaming)<br/>:9092"]
        end

        subgraph Observability["Observability Stack"]
            Prometheus["Prometheus<br/>(Metrics)<br/>:9090"]
            Grafana["Grafana<br/>(Dashboards)<br/>:3000"]
            Loki["Loki<br/>(Log Aggregation)"]
            Promtail["Promtail<br/>(Log Shipper)"]
        end

    end

    subgraph ExternalAPIs["External APIs"]
        OpenAI["OpenAI API<br/>(Embeddings)"]
        LLMBackend["LLM Backend<br/>(OpenAI / Local)"]
    end

    %% User interactions
    User -->|"HTTP"| Browser
    Browser -->|"Search Queries<br/>:8080"| SearchUI
    Browser -->|"Document Upload<br/>:8082"| IngestionAPI
    Browser -->|"View Dashboards<br/>:3000"| Grafana

    %% Search flow
    SearchUI -->|"gRPC"| SearchService
    SearchService -->|"gRPC"| EmbeddingService
    SearchService -->|"Vector/Hybrid Search"| Weaviate
    SearchService -->|"Cache Lookup"| Redis
    SearchService -->|"Generate Answer"| LLMService

    %% LLM and Embedding backends
    EmbeddingService -->|"API Call"| OpenAI
    LLMService -->|"API Call"| LLMBackend

    %% Ingestion flow
    IngestionAPI -->|"Store Document"| MinIO
    IngestionAPI -->|"Publish Event"| Kafka
    Kafka -->|"Consume Events"| Indexer
    Indexer -->|"Fetch Document"| MinIO
    Indexer -->|"gRPC"| EmbeddingService
    Indexer -->|"Index Chunks"| Weaviate
    Indexer -->|"Distributed Lock"| Redis

    %% Observability flow
    Prometheus -->|"Scrape /metrics"| SearchUI
    Prometheus -->|"Scrape /metrics"| SearchService
    Prometheus -->|"Scrape /metrics"| IngestionAPI
    Prometheus -->|"Scrape /metrics"| Indexer
    Prometheus -->|"Scrape /metrics"| EmbeddingService
    Prometheus -->|"Scrape /metrics"| LLMService
    Grafana -->|"Query Metrics"| Prometheus
    Grafana -->|"Query Logs"| Loki

    %% Log collection
    Promtail -->|"Ship Logs"| Loki
    SearchUI -.->|"stdout/stderr"| Promtail
    SearchService -.->|"stdout/stderr"| Promtail
    IngestionAPI -.->|"stdout/stderr"| Promtail
    Indexer -.->|"stdout/stderr"| Promtail
    EmbeddingService -.->|"stdout/stderr"| Promtail
    LLMService -.->|"stdout/stderr"| Promtail

    %% Styling
    classDef user fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef service fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef datastore fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef messaging fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef observability fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef external fill:#eceff1,stroke:#546e7a,stroke-width:2px

    class User,Browser user
    class SearchUI,SearchService,IngestionAPI,Indexer,EmbeddingService,LLMService service
    class Weaviate,Redis,MinIO datastore
    class Kafka messaging
    class Prometheus,Grafana,Loki,Promtail observability
    class OpenAI,LLMBackend external
```

## Component Overview

### Application Services

| Service | Protocol | Port | Description |
|---------|----------|------|-------------|
| **Search UI** | HTTP/REST | 8080 | User-facing web interface for search |
| **Search Service** | gRPC | 50052 | Backend search logic with RAG pipeline |
| **Ingestion API** | HTTP/REST | 8082 | Document upload endpoint |
| **Indexer** | - | - | Kafka consumer for document processing |
| **Embedding Service** | gRPC | 50051 | Text embedding generation |
| **LLM Inference Service** | gRPC/HTTP | - | Answer generation from context |

### Data Stores

| Component | Port | Purpose |
|-----------|------|---------|
| **Weaviate** | 8081 | Vector database with hybrid search (HNSW + BM25) |
| **Redis** | 6379 | Response caching and distributed locking |
| **MinIO** | 9000 | Object storage for raw documents |

### Message Queue

| Component | Port | Purpose |
|-----------|------|---------|
| **Kafka** | 9092 | Event streaming for async document processing |

### Observability Stack

| Component | Port | Purpose |
|-----------|------|---------|
| **Prometheus** | 9090 | Metrics collection and alerting |
| **Grafana** | 3000 | Dashboards for metrics and logs |
| **Loki** | - | Log aggregation and querying |
| **Promtail** | - | Log shipping agent (DaemonSet) |

## Data Flows

### Search Request Flow

```
User → Search UI → Search Service → Embedding Service → Weaviate → LLM Service → User
                         ↓
                       Redis (cache)
```

1. User submits query via Search UI
2. Search UI forwards to Search Service (gRPC)
3. Search Service checks Redis cache
4. Search Service calls Embedding Service for query embedding
5. Search Service queries Weaviate (vector/hybrid search)
6. Search Service calls LLM Service to generate answer
7. Response cached in Redis and returned to user

### Document Ingestion Flow

```
User → Ingestion API → MinIO → Kafka → Indexer → Embedding Service → Weaviate
```

1. User uploads document via Ingestion API
2. Raw document stored in MinIO
3. Event published to Kafka topic
4. Indexer consumes event, fetches document from MinIO
5. Document chunked and embeddings generated
6. Chunks with vectors stored in Weaviate

### Observability Flow

```
Services → Prometheus (metrics scrape)
Services → Promtail → Loki (log shipping)
Grafana → Prometheus + Loki (visualization)
```

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Search UI | ✅ Implemented | FastAPI + Jinja2 templates |
| Search Service | ✅ Implemented | gRPC server with Haystack pipeline |
| Ingestion API | ✅ Implemented | FastAPI with async Kafka producer |
| Indexer | ✅ Implemented | Kafka consumer with distributed locking |
| Embedding Service | ✅ Implemented | gRPC server, OpenAI/hash-based backends |
| LLM Inference Service | ⚠️ Integrated | Currently uses OpenAI API directly |
| Weaviate | ✅ Deployed | Vector + BM25 hybrid search |
| Redis | ✅ Deployed | Caching + distributed locks |
| MinIO | ✅ Deployed | Document object storage |
| Kafka | ✅ Deployed | KRaft mode, single broker |
| Prometheus | ✅ Deployed | Scraping all services |
| Grafana | ✅ Deployed | Basic dashboards |
| Loki | 📋 Planned | Log aggregation |
| Promtail | 📋 Planned | Log shipping |

## Port Summary

| Port | Service | Access |
|------|---------|--------|
| 8080 | Search UI | External (NodePort 30080) |
| 8081 | Weaviate | External (NodePort 30081) |
| 8082 | Ingestion API | External (NodePort 30082) |
| 3000 | Grafana | External (NodePort 30030) |
| 9090 | Prometheus | External (NodePort 30090) |
| 50051 | Embedding Service | Internal (ClusterIP) |
| 50052 | Search Service | Internal (ClusterIP) |
| 6379 | Redis | Internal (ClusterIP) |
| 9092 | Kafka | Internal (ClusterIP) |
| 9000 | MinIO | Internal (ClusterIP) |
