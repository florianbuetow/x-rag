# X-RAG Project Guide for AI Agents

## Project Overview

X-RAG is a production-grade distributed search and indexing platform for Retrieval-Augmented Generation (RAG), built entirely in Python and running on Kubernetes (Kind for local development).

## Core Technology Stack

- **Language**: Python 3.11+
- **Validation**: Pydantic for all data models
- **RAG Framework**: Haystack for retrieval pipelines
- **Internal Communication**: gRPC for service-to-service
- **External APIs**: FastAPI for user-facing REST endpoints
- **Infrastructure**: Kubernetes (Kind) for local development
- **Package Management**: uv (manages Python versions and dependencies)

## Architecture

### Communication Pattern
```
External Users (HTTP/REST)
    ↓
[Search UI - FastAPI] ←─gRPC─→ [Search Service - gRPC] ←─gRPC─→ [Embedding Service - gRPC]
                                         ↓
                                     Weaviate
                                         ↑
[Ingestion API - FastAPI] ──→ Kafka → [Indexer] ─gRPC→ [Embedding Service]
```

### Services
1. **Search UI** (FastAPI REST) - User-facing web interface
2. **Search Service** (gRPC Server) - Backend search logic with Haystack
3. **Ingestion API** (FastAPI REST) - Document upload endpoint
4. **Embedding Service** (gRPC Server) - Embedding generation service
5. **Indexer** (Kafka Consumer) - Background document processing

### Infrastructure Components
- **Weaviate**: Vector/BM25/hybrid search
- **Kafka**: Message queue
- **Redis**: Caching
- **MinIO**: Object storage
- **Prometheus + Grafana**: Monitoring

## Development Workflow

### Main Commands (ALWAYS use Makefile)

```bash
make help         # Show all available commands
make check        # Validate prerequisites
make setup        # One-time cluster setup (creates Kind cluster, deploys infrastructure)
make start        # Build and deploy applications
make stop         # Stop services (keeps cluster)
make status       # Show system status
make test         # Run pytest tests
make clean        # Delete cluster and data (with confirmation)
make destroy      # Stop services and delete Docker images
make reset        # Clean + setup (fresh start)
```

### Logs
```bash
make logs-search-ui
make logs-search-service
make logs-embedding
make logs-ingest
make logs-indexer
make logs-weaviate
make logs-kafka
make logs-redis
```

## Critical Development Rules

### 1. Everything Runs in Kubernetes
- **NO local development outside Kind cluster**
- All services run inside the cluster
- No `dev-*` targets in Makefile

### 2. Always Use Makefile
- **NEVER** run scripts directly
- **ALWAYS** use `make` targets
- Example: Use `make check`, NOT `./scripts/check-prerequisites.sh`

### 3. Python & Dependencies
- Python version managed by `uv` (defined in pyproject.toml)
- Don't check for Python version in prerequisites
- All dependencies in pyproject.toml

### 4. Docker Configuration
- Minimum: 6GB RAM, 4 cores
- Recommended: 10GB RAM, 8 cores
- Use "cores" not "CPUs" in all messaging

### 5. Git Commits
- **NEVER** attribute AI in commit messages
- Commit after each milestone
- Use conventional format: `<type>: <description>`
- Types: feat, fix, docs, infra, test, refactor, chore

### 6. Resource Check Output Format
```
System Resources:
  Recommended: 10GB RAM, 8 cores
  Available: 31GB RAM, 16 cores (via docker configuration) ✓
```

## Project Structure

```
x-rag/
├── .gitignore
├── .env.example              # Copy to .env and add OPENAI_API_KEY
├── Makefile                  # Main developer interface
├── pyproject.toml            # Python dependencies
├── CLAUDE.md                 # Points to this file
├── AGENTS.md                 # This file
├── README.md
├── SETUP.md
├── SYSTEM-DIAGRAM.md
│
├── .setup/                   # Checkpoints (gitignored)
├── data/storage/             # Kind PV mount (gitignored)
│
├── proto/                    # gRPC Protocol Buffers
│   ├── embedding.proto
│   ├── search.proto
│   └── common.proto
│
├── infra/
│   ├── kind/
│   │   └── cluster-config.yaml
│   ├── k8s/                  # Kubernetes manifests
│   │   ├── weaviate/
│   │   ├── kafka/
│   │   ├── minio/
│   │   ├── redis/
│   │   ├── monitoring/
│   │   ├── search-ui/
│   │   ├── search-service/
│   │   ├── ingestion-api/
│   │   ├── embedding-service/
│   │   └── indexer/
│   └── docker/               # Dockerfiles
│
├── scripts/
│   ├── check-prerequisites.sh
│   ├── check-docker-resources.sh
│   ├── check-ports.sh
│   ├── create-cluster.sh
│   ├── setup-registry.sh
│   ├── deploy-infrastructure.sh
│   ├── deploy-monitoring.sh
│   ├── deploy-apps.sh
│   ├── build-images.sh
│   └── generate-grpc.sh
│
├── src/
│   ├── proto_gen/            # Generated gRPC code (gitignored)
│   ├── core/                 # Shared interfaces and models
│   ├── common/               # Reusable utilities
│   ├── retrievers/           # Haystack retrievers
│   ├── pipelines/            # Haystack pipelines
│   ├── search_ui/            # FastAPI web interface
│   ├── search_service/       # gRPC search server
│   ├── ingestion_api/        # FastAPI ingestion endpoint
│   ├── embedding_service/    # gRPC embedding server
│   └── indexer/              # Kafka consumer
│
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_config.py
    ├── test_grpc.py
    └── test_e2e.py
```

## Port Mappings

- **8080**: Search UI
- **8081**: Weaviate
- **8082**: Ingestion API
- **3000**: Grafana (admin/admin)
- **9090**: Prometheus
- **5000**: Local Docker registry

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required
OPENAI_API_KEY=sk-your-key-here

# Internal Services (Kubernetes)
WEAVIATE_URL=http://weaviate:8080
KAFKA_BOOTSTRAP=kafka:9092
REDIS_URL=redis://redis:6379
EMBEDDING_SERVICE_ADDR=embedding-service:50051
SEARCH_SERVICE_ADDR=search-service:50052
```

## Implementation Status

### ✅ Completed
- Phase 0: .gitignore
- Phase 1: Foundation (Makefile, scripts, pyproject.toml, .env.example, directory structure)

### 🚧 In Progress
- Phase 2: Infrastructure Implementation (Kind cluster, K8s manifests)

### 📋 Pending
- Phase 3: gRPC Protocol Definitions
- Phase 4: Common Modules
- Phase 5: Embedding Service
- Phase 6: Ingestion API
- Phase 7: Indexer
- Phase 8: Search Service
- Phase 9: Search UI
- Phase 10: Haystack Pipelines
- Phase 11: Testing
- Phase 12: Documentation
- Phase 13: Validation

## Common Issues & Solutions

### Issue: "Docker daemon not running"
**Solution**: Start Docker Desktop (macOS) or `sudo systemctl start docker` (Linux)

### Issue: "Port already in use"
**Solution**: Run `make check` to see which process is using the port, then stop it

### Issue: "Insufficient Docker resources"
**Solution**: Docker Desktop → Settings → Resources → Increase RAM/Cores

### Issue: "Cluster not found"
**Solution**: Run `make setup` to create the cluster first

### Issue: "Prerequisites missing"
**Solution**: Run `make check` to see what's missing and install required tools

## Design Principles

1. **Simplicity**: Don't over-engineer; solve the current problem
2. **Idempotency**: All setup scripts can be run multiple times safely
3. **Actionable Errors**: Every error message should tell the user exactly how to fix it
4. **Minimal Base Images**: Use `python:3.11-slim` for Docker images
5. **Health Checks**: All services must implement health endpoints
6. **Metrics**: All services expose Prometheus metrics
7. **Type Safety**: Use Pydantic for all data validation
8. **Testing**: Write tests for all core functionality

## When Working on This Project

1. **Always read this file first** to understand the architecture and rules
2. **Use the Makefile** for all operations (never run scripts directly)
3. **Check prerequisites** with `make check` before starting work
4. **Refer to the plan** at `/Users/flo/.claude/plans/mighty-jumping-bachman.md` for detailed implementation phases
5. **Commit frequently** after completing each milestone
6. **Don't add emojis** unless explicitly requested by the user
7. **Use proper terminology**: "cores" not "CPUs", "gRPC" not "grpc", etc.

## Quick Start for New Work

```bash
# 1. Check prerequisites
make check

# 2. Setup infrastructure (first time only)
make setup

# 3. Build and start services
make start

# 4. Check status
make status

# 5. Run tests
make test
```

## Getting Help

- Run `make help` to see all available commands
- Check TROUBLESHOOTING.md for common issues (to be created in Phase 11)
- Review ARCHITECTURE.md for design details (to be created in Phase 11)
