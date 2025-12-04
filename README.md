# X-RAG — Distributed Search & Indexing for Retrieval-Augmented Generation

X-RAG is a production-grade, multi-tenant RAG platform that combines vector, lexical, and graph retrieval into a unified, Kubernetes-native architecture. Designed for teams who need more than a simple vector database wrapper — X-RAG provides the full infrastructure for ingestion, retrieval, orchestration, and observability at scale.

---

## Key Features

### Functional Capabilities

| Capability | Implementation | Details |
|------------|----------------|---------|
| **Vector Search** | Weaviate (HNSW) | Semantic similarity search with custom embeddings; supports OpenAI, Cohere, local models |
| **Lexical Search** | OpenSearch/Elasticsearch | BM25 ranking with field boosts, analyzers, and token filters |
| **Hybrid Search** | Weaviate + OpenSearch | Score fusion between vector and lexical results with tunable alpha weighting |
| **Graph Search** | Neo4j | Entity-relationship traversal, neighbor expansion, Cypher-based query planning |
| **Metadata Filtering** | All backends | Namespace-aware filtering across all retrieval modes |
| **Multi-Hop Retrieval** | Orchestration layer | LLM-powered question decomposition with iterative retrieval |
| **Re-Ranking** | Cross-encoder / LLM | Post-retrieval relevance scoring for precision improvement |

### Non-Functional Characteristics

| Characteristic | Approach | Details |
|----------------|----------|---------|
| **Scalability** | Per-namespace isolation | Independent scaling of storage (Weaviate, OpenSearch, Neo4j) and compute (API, indexers) per domain |
| **Latency** | gRPC + FastAPI + Redis | Sub-100ms P95 retrieval via connection pooling, async I/O, and query/response caching |
| **Query Throughput** | Horizontal pod autoscaling | Stateless API layer scales with HPA; Redis caching reduces backend load by 60-80% for repeated queries |
| **Indexing Throughput** | Kafka + parallel consumers | Event-driven ingestion with configurable consumer parallelism per namespace |
| **Observability** | Prometheus + Grafana + Langfuse | System metrics, LLM-specific traces, per-namespace dashboards, and distributed tracing via OpenTelemetry |
| **Partition Tolerance** | Kubernetes + StatefulSets | Weaviate/OpenSearch/Neo4j replication; Kafka consumer group rebalancing on failure |
| **Availability** | Multi-replica deployments | No single point of failure for stateless services; storage backends support replica failover |
| **Consistency** | Eventual (tunable) | Kafka-based ingestion provides at-least-once delivery; storage backends handle their own consistency guarantees |

---

## Development

### Code Style

This project follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting to enforce consistent code style across the codebase.

### Linting and Formatting

Before committing code, ensure it passes linting and formatting checks:

```bash
# Check code style and formatting (read-only, no changes)
make code-style

# Automatically fix linting issues and format code
make code-format
```

**What these commands do:**

- `make code-style` — Runs Ruff in check-only mode to identify style violations and formatting issues without making changes
- `make code-format` — Automatically fixes linting issues and formats all Python code according to the style guide

**Configuration:** Ruff is configured in `pyproject.toml` with Google-style docstring conventions, line length of 140 characters, and Python 3.11+ target version.

### Security Checks

Run security analysis with Bandit to detect common security issues:

```bash
# Run security checks and generate reports
make code-security
```

**What this does:**

- Scans all code in `src/` for security vulnerabilities
- Detects hardcoded passwords, SQL injection risks, unsafe deserialization, etc.
- Generates a text report at `reports/security/bandit.txt`
- Displays findings in CLI and fails on medium+ severity/confidence issues

**Configuration:** Bandit is configured in `pyproject.toml` with medium severity and confidence thresholds.

### Quick Reference

```bash
make help            # Show all available commands
make check           # Validate prerequisites
make init            # Initialize local dev environment (install deps, generate gRPC)
make cluster-init    # Build Docker images for deployment
make cluster-start   # Start cluster and deploy all services
make test            # Run test suite
make ci              # Run all CI checks (style + security + tests with coverage)
make cluster-status  # Show cluster status
```

### Accessing Web UIs

```bash
# Open Search UI in browser
make open-search-ui        # http://localhost:8080

# Open Ingestion API documentation
make open-ingestion-api    # http://localhost:8082/docs

# Open monitoring dashboards
make open-grafana          # http://localhost:3000 (admin/admin)
make open-prometheus       # http://localhost:9090

# Open Weaviate console
make open-weaviate         # http://localhost:8081

# Open Kubernetes Dashboard
make open-k8-dashboard        # https://localhost:8443
make show-k8-dashboard-token  # Get authentication token (if needed)
```

### Debugging

```bash
# Check detailed pod status
kubectl get pods -n rag-system

# View service logs
make logs-<service-name>  # e.g., make logs-embedding, make logs-indexer

# Debug specific pod
kubectl describe pod <pod-name> -n rag-system
kubectl logs <pod-name> -n rag-system
```

#### Debugging gRPC Services

For debugging gRPC services (embedding-service, search-service), install [grpcurl](https://github.com/fullstorydev/grpcurl):

```bash
# Install (macOS)
brew install grpcurl

# Install (Linux)
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
```

Example commands:

```bash
# List available services (server reflection enabled)
grpcurl -plaintext localhost:50051 list

# Call health check on embedding service
grpcurl -plaintext localhost:50051 xrag.embedding.EmbeddingService/HealthCheck

# Call health check on search service
grpcurl -plaintext localhost:50052 xrag.search.SearchService/HealthCheck
```

### Project Structure

```
x-rag/
├── src/                    # Python application code
│   ├── core/              # Core domain models and interfaces
│   ├── common/            # Shared utilities (config, health, metrics)
│   ├── search_api/        # Search API service (FastAPI)
│   ├── ingestion_api/     # Ingestion API service (FastAPI)
│   ├── embedding_service/ # Embedding service (gRPC)
│   ├── indexer/           # Background document processor (Kafka consumer)
│   ├── pipelines/         # Haystack RAG pipelines
│   ├── retrievers/        # Custom retrievers (Weaviate, etc.)
│   └── proto_gen/         # Generated gRPC code (auto-generated)
├── proto/                  # Protocol buffer definitions
├── infra/                  # Infrastructure configuration
│   ├── kind/              # Kind cluster configuration
│   ├── k8s/               # Kubernetes manifests (all services)
│   └── docker/            # Dockerfiles for each service
├── scripts/                # Automation scripts (cluster, deploy, status)
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests (requires cluster)
├── reports/                # Test reports and coverage (gitignored)
│   └── coverage/          # HTML and XML coverage reports
├── data/                   # Persistent data
│   └── storage/           # Kind cluster persistent volumes (gitignored)
├── .setup/                 # Setup checkpoints (gitignored)
├── Makefile               # Main developer interface
├── pyproject.toml         # Python dependencies and tool configuration
└── README.md              # This file
```

**Key Directories:**
- **`src/`** — All Python application code organized by service
- **`infra/`** — Kubernetes manifests, Dockerfiles, and cluster configuration
- **`proto/`** — gRPC service definitions (use `make apps-generate-grpc` to regenerate)
- **`scripts/`** — Shell scripts for cluster management and deployment
- **`tests/`** — Unit and integration tests (use `make test` or `make ci`)
- **`reports/`** — Generated test coverage reports (created by `make init`)
- **`docs/`** — Additional documentation and guides

For quick start guide, see [docs/QUICKSTART.md](docs/QUICKSTART.md). For architecture details, see [docs/SYSTEM-DIAGRAM.md](docs/SYSTEM-DIAGRAM.md). For advanced Kind and pod access operations, see [docs/KIND-ACCESS-CHEAT-SHEET.md](docs/KIND-ACCESS-CHEAT-SHEET.md).