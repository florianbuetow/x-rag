```mermaid
flowchart TB
    subgraph External["External (Host Machine)"]
        User["👤 User"]
    end

    subgraph KindCluster["Kind Kubernetes Cluster"]
        subgraph ControlPlane["Control Plane Node (Port Mappings)"]
            PM8080["Port 8080"]
            PM8082["Port 8082"]
            PM8081["Port 8081"]
            PM3000["Port 3000"]
            PM9090["Port 9090"]
        end

        subgraph RagSystem["Namespace: rag-system"]
            
            subgraph AppLayer["Application Layer (independently scalable)"]
                SearchAPI["Search API<br/>/search, /health, /metrics<br/>NodePort 30080"]
                IngestAPI["Ingestion API<br/>/ingest, /health, /metrics<br/>NodePort 30082"]
                EmbeddingService["Embedding Service<br/>/embed, /health, /metrics"]
                Indexer["Indexer<br/>/health, /metrics"]
            end

            subgraph DataLayer["Data Layer"]
                Weaviate["Weaviate<br/>(Vector + BM25 + Hybrid)<br/>NodePort 30081"]
                Kafka["Kafka<br/>(Message Queue)"]
                MinIO["MinIO<br/>(Object Storage)"]
                Redis["Redis<br/>(Cache)"]
            end

            subgraph Observability["Observability"]
                Prometheus["Prometheus<br/>NodePort 30090"]
                Grafana["Grafana<br/>NodePort 30030"]
            end
        end
    end

    subgraph ExternalAPIs["External APIs"]
        OpenAI["OpenAI API"]
    end

    subgraph EmbeddingBackends["Embedding Backends (configurable)"]
        OpenAIEmbed["OpenAI Embeddings"]
        FastText["FastText (local)"]
        SentenceTrans["Sentence Transformers"]
    end

    %% User connections through port mappings
    User -->|"HTTP :8080<br/>POST /search"| PM8080
    User -->|"HTTP :8082<br/>POST /ingest"| PM8082
    User -->|"HTTP :8081<br/>Weaviate REST"| PM8081
    User -->|"HTTP :3000<br/>Dashboards"| PM3000
    User -->|"HTTP :9090<br/>PromQL"| PM9090

    %% Port mappings to services
    PM8080 --> SearchAPI
    PM8082 --> IngestAPI
    PM8081 --> Weaviate
    PM3000 --> Grafana
    PM9090 --> Prometheus

    %% Search flow
    SearchAPI -->|"1. Check cache"| Redis
    SearchAPI -->|"2. Get query embedding"| EmbeddingService
    SearchAPI -->|"3. Vector/BM25/Hybrid search"| Weaviate
    SearchAPI -->|"4. Generate answer"| OpenAI

    %% Ingestion flow
    IngestAPI -->|"Store raw doc"| MinIO
    IngestAPI -->|"Publish event"| Kafka
    
    Kafka -->|"Consume events"| Indexer
    Indexer -->|"Fetch raw doc"| MinIO
    Indexer -->|"Get chunk embeddings"| EmbeddingService
    Indexer -->|"Store chunks + vectors"| Weaviate

    %% Embedding service backends
    EmbeddingService -->|"API call"| OpenAIEmbed
    EmbeddingService -.->|"or local model"| FastText
    EmbeddingService -.->|"or local model"| SentenceTrans

    %% Observability - scrape all services
    Prometheus -->|"Scrape /metrics"| SearchAPI
    Prometheus -->|"Scrape /metrics"| IngestAPI
    Prometheus -->|"Scrape /metrics"| EmbeddingService
    Prometheus -->|"Scrape /metrics"| Indexer
    Grafana -->|"Query PromQL"| Prometheus

    %% Styling
    classDef external fill:#e1f5fe,stroke:#01579b
    classDef app fill:#fff3e0,stroke:#e65100
    classDef data fill:#e8f5e9,stroke:#2e7d32
    classDef obs fill:#f3e5f5,stroke:#7b1fa2
    classDef extapi fill:#fce4ec,stroke:#c2185b
    classDef port fill:#eceff1,stroke:#546e7a
    classDef backend fill:#fff8e1,stroke:#f9a825

    class User external
    class SearchAPI,IngestAPI,EmbeddingService,Indexer app
    class Weaviate,Kafka,MinIO,Redis data
    class Prometheus,Grafana obs
    class OpenAI extapi
    class PM8080,PM8082,PM8081,PM3000,PM9090 port
    class OpenAIEmbed,FastText,SentenceTrans backend
```

## Connection Summary

### Search Request Flow (Search API)
1. **User → Search API** (`:8080/search`) - HTTP POST with query
2. **Search API → Redis** - Check if response is cached
3. **Search API → Embedding Service** - Get embedding for query
4. **Search API → Weaviate** - Vector/BM25/Hybrid search
5. **Search API → OpenAI** - Generate answer from context
6. **Search API → Redis** - Cache the response
7. **Search API → User** - Return answer + sources

### Document Ingestion Flow (Ingestion API + Indexer)
1. **User → Ingestion API** (`:8082/ingest`) - Upload document
2. **Ingestion API → MinIO** - Store raw document
3. **Ingestion API → Kafka** - Publish `document-changes` event
4. **Kafka → Indexer** - Consumer receives event
5. **Indexer → MinIO** - Fetch raw document
6. **Indexer → Embedding Service** - Get embeddings for chunks
7. **Indexer → Weaviate** - Store chunks with vectors

### Observability Flow
1. **Prometheus → All Services** - Scrape `/metrics` every 15s
2. **Grafana → Prometheus** - Query metrics via PromQL
3. **User → Grafana** (`:3000`) - View dashboards

### Port Mappings (Host → Container)
| Host Port | Container Port | Service |
|-----------|----------------|---------|
| 8080 | 30080 | Search API |
| 8082 | 30082 | Ingestion API |
| 8081 | 30081 | Weaviate |
| 3000 | 30030 | Grafana |
| 9090 | 30090 | Prometheus |

## Independent Scaling

The four application components can be scaled independently:

```bash
# Scale search for high query load
kubectl scale deployment search-api --replicas=5 -n rag-system

# Scale ingestion API for bulk uploads
kubectl scale deployment ingestion-api --replicas=3 -n rag-system

# Scale embedding service for high throughput
kubectl scale deployment embedding-service --replicas=4 -n rag-system

# Scale indexers for faster document processing
kubectl scale deployment indexer --replicas=10 -n rag-system
```

Each service has its own Docker image:

| Service | Image | Dockerfile |
|---------|-------|------------|
| Search API | `localhost:5000/search-api:latest` | `Dockerfile.search-api` |
| Ingestion API | `localhost:5000/ingestion-api:latest` | `Dockerfile.ingestion-api` |
| Embedding Service | `localhost:5000/embedding-service:latest` | `Dockerfile.embedding-service` |
| Indexer | `localhost:5000/indexer:latest` | `Dockerfile.indexer` |

## Weaviate Search Modes

Weaviate supports all three search modes in a single instance (no need for separate deployments):

| Mode | Method | Use Case |
|------|--------|----------|
| **Vector** | HNSW nearest neighbor | Semantic similarity |
| **BM25** | Inverted index | Keyword matching |
| **Hybrid** | Vector + BM25 fusion | Best of both |

```python
# Configure per query
results = weaviate.query(query, mode="hybrid", alpha=0.5)  # 50% vector, 50% BM25
```

## Embedding Service Backends

The Embedding Service abstracts the embedding provider:

| Backend | Config | Use Case |
|---------|--------|----------|
| OpenAI | `EMBEDDING_BACKEND=openai` | Production, high quality |
| FastText | `EMBEDDING_BACKEND=fasttext` | Local, no API costs |
| Sentence Transformers | `EMBEDDING_BACKEND=sentence-transformers` | Local, good quality |

Switch backends via environment variable without code changes.
