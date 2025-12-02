# X-RAG Project Guide for AI Agents

## 🚨 CRITICAL: Read the Project Plan First

**The complete project plan is located at:**
`/Users/flo/.claude/plans/mighty-jumping-bachman.md`

**You MUST read the project plan before working on this project.** It contains:
- Complete architecture and service definitions
- Detailed technology stack and dependencies
- Full directory structure
- gRPC protocol definitions
- Infrastructure components (Kind, Weaviate, Kafka, etc.)
- All implementation phases
- Kubernetes manifests specifications
- Testing strategy
- Success criteria

This file (AGENTS.md) contains only **operational rules** and **current status** - everything else is in the plan.

## Project Quick Summary

X-RAG is a production-grade distributed RAG platform:
- **Python 3.11+** for all services
- **gRPC** for internal communication
- **FastAPI** for external APIs
- **Haystack** for RAG pipelines
- **Pydantic** for validation
- **Kind Kubernetes** for local development

See the project plan for complete architecture details.

## Main Commands

**ALWAYS use Makefile, NEVER run scripts directly:**

```bash
make help         # Show all commands
make check        # Validate prerequisites
make setup        # One-time setup
make start        # Build and deploy apps
make stop         # Stop services
make status       # Show status
make test         # Run tests
make clean        # Delete everything
make destroy      # Stop + delete images
make logs-*       # Tail service logs
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
- **ALWAYS** use `uv run python` instead of `python` directly
- **NEVER** run Python outside the virtual environment

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

## Quick Reference

- **Project Structure**: See project plan for full directory tree
- **Port Mappings**: 8080=UI, 8081=Weaviate, 8082=Ingestion, 3000=Grafana, 9090=Prometheus, 6379=Redis, 9092=Kafka
- **Environment Variables**: Copy `.env.example` to `.env` and add `OPENAI_API_KEY`

## Implementation Status

### ✅ Completed (7/13 phases = 54%)
- Phase 0: .gitignore
- Phase 1: Foundation (Makefile, scripts, pyproject.toml, .env.example, directory structure)
- Phase 2: Infrastructure Implementation (Kind cluster, K8s manifests)
- Phase 3: gRPC Protocol Definitions
- Phase 4: Common Modules (health checks, config, domain models)
- Phase 5: Embedding Service (gRPC server, OpenAI backend, Dockerfile, K8s manifests)
- Phase 6: Ingestion API (FastAPI + Kafka + MinIO)
- Phase 7: Indexer (Kafka consumer + document processing)

### 📋 Pending
- Phase 8: Search Service
- Phase 9: Search UI
- Phase 10: Haystack Pipelines
- Phase 11: Testing (unit/integration tests exist, need Search tests)
- Phase 12: Documentation
- Phase 13: Validation

## Recent Fixes (Phase 7 Validation - December 2025)

### Testing Summary
**All Tests Passing**: 20/20 tests (15 unit + 5 integration)
- ✅ `make check` - All prerequisites validated
- ✅ `make destroy` + `make start` - Cluster lifecycle robust
- ✅ `make build` - All images build successfully
- ✅ `make test` - 15/15 unit tests passed
- ✅ `make test-integration` - 5/5 integration tests passed
- ✅ E2E document ingestion flow working
- ✅ Duplicate detection working

### Quick Fixes Applied
1. **Indexer readiness probe bug** (src/indexer/main.py:155-157)
   - Issue: Health server started with consumer=None, never updated after consumer creation
   - Fix: Added code to update health_server.consumer after consumer initialization

2. **Python version standardization** (infra/docker/Dockerfile.indexer:2)
   - Issue: Indexer using python:3.13-slim while others use python:3.11-slim
   - Fix: Changed to python:3.11-slim for consistency

3. **MinIO connection leak** (src/indexer/processor.py:139-152)
   - Issue: Connection not closed if exception occurred during processing
   - Fix: Added try/finally block to ensure cleanup

4. **Docker process name pattern** (scripts/check-ports.sh:28)
   - Issue: Truncated process name "com.docke" used exact match instead of pattern
   - Fix: Changed to pattern matching with wildcards

5. **Pydantic V2 deprecation** (src/ingestion_api/main.py:32-35)
   - Issue: Using deprecated `class Config` pattern
   - Fix: Migrated to `model_config = ConfigDict(extra="forbid")`

6. **Ingestion API metrics endpoint** (infra/k8s/monitoring/prometheus.yaml:17-19)
   - Issue: Prometheus scraping wrong port (8082 instead of 8080)
   - Fix: Corrected to scrape ingestion-api:8080

## Known Issues (Require Future Work)

### Critical Priority
1. **Race condition in duplicate detection** (src/indexer/processor.py:312-328)
   - Multiple indexer replicas can process same document simultaneously
   - Solution: Requires distributed locking (Redis) or Weaviate transactions
   - Workaround: Run single indexer replica

2. **Blocking operations in indexer** (src/indexer/processor.py)
   - Synchronous MinIO/Weaviate calls block async event loop
   - Impacts throughput under high load
   - Solution: Wrap in executor or use async clients

3. **Weaviate connection thread safety** (src/indexer/processor.py:91-117)
   - Lazy initialization has race condition
   - Solution: Add threading.Lock for connection initialization

### Security Issues
4. **MinIO credentials exposed in YAML** (infra/k8s/minio/minio.yaml)
   - Default credentials (minioadmin/minioadmin123) in plain text
   - Solution: Move to Kubernetes Secret

5. **No TLS for inter-service communication**
   - All gRPC and HTTP traffic unencrypted within cluster
   - Production deployment should enable mTLS

6. **Weaviate anonymous access enabled**
   - Authentication disabled for development
   - Production should require API keys

### Architecture Improvements
7. **Kafka replication factor = 1** (infra/k8s/kafka/kafka.yaml)
   - Single replica = no high availability or durability
   - Current: Dev-only configuration
   - Production: Increase to 3 replicas

8. **Service list duplication** (scripts/build-images.sh, scripts/deploy-apps.sh)
   - Service names hardcoded in multiple scripts
   - Solution: Centralize in Makefile variable

9. **Missing dev-* targets**
   - No `dev-embedding`, `dev-ingest`, `dev-indexer` targets
   - Would enable faster local iteration with --reload

10. **No distributed tracing**
    - Difficult to debug cross-service issues
    - Solution: Add OpenTelemetry instrumentation

### Nice to Have
11. **Chunk overlap not implemented** (src/indexer/processor.py:156-188)
    - Current: Fixed-size non-overlapping chunks
    - Enhancement: Add sliding window with configurable overlap

12. **Complex health check probes** (K8s deployments)
    - Using Python exec commands for health checks
    - Could simplify to TCP/HTTP checks

## When Working on This Project

1. **Read the project plan** at `/Users/flo/.claude/plans/mighty-jumping-bachman.md` for architecture and implementation details
2. **Read this file** for operational rules and current status
3. **Run `make check`** before starting work
4. **Use the Makefile** for all operations
5. **Commit frequently** after each milestone

## Understanding Docker vs Kubernetes Architecture

### What You See in `docker ps` (4 Containers)

When you run `docker ps`, you see **4 Docker containers**:
```
1. xrag-k8-kind-registry   ← Local Docker registry (stores images)
2. xrag-k8-control-plane   ← Kubernetes master node
3. xrag-k8-worker          ← Kubernetes worker node
4. xrag-k8-worker2         ← Kubernetes worker node
```

### Where Are the Services?

**Redis, Kafka, MinIO, and Weaviate are NOT separate Docker containers.**

They run **INSIDE** the worker nodes as Kubernetes pods. Kind uses "Docker-in-Docker" - the worker containers run Kubernetes, and your services run as pods inside those containers.

### Architecture Visualization

```
┌─────────────────────────────────────────────────┐
│         Kubernetes Cluster (xrag-k8)            │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────┐  ┌──────────────────┐     │
│  │ xrag-k8-worker   │  │ xrag-k8-worker2  │     │
│  ├──────────────────┤  ├──────────────────┤     │
│  │ Pods:            │  │ Pods:            │     │
│  │ • Redis          │  │ • MinIO          │     │
│  │ • Kafka          │  │ • Weaviate       │     │
│  │ • Grafana        │  │                  │     │
│  │ • Prometheus     │  │                  │     │
│  └──────────────────┘  └──────────────────┘     │
│                                                 │
└─────────────────────────────────────────────────┘
```

### How to See Your Services

```bash
# See Docker containers (infrastructure):
docker ps

# See Kubernetes pods (actual services):
kubectl get pods -n rag-system

# See which pod runs on which node:
kubectl get pods -n rag-system -o wide

# See all resources:
kubectl get all -n rag-system
```

### Why Kubernetes Instead of Simple Docker?

The X-RAG project uses Kubernetes for production-grade features:
- **Independent scaling**: Scale search-api to 5 replicas, indexer to 10
- **Production parity**: Same setup in dev and production
- **Service discovery**: Automatic DNS (xrag-redis:6379)
- **Health checks**: Automatic pod restarts
- **Resource limits**: Prevent services from consuming all resources

## Common Issues

- **"Docker daemon not running"**: Start Docker Desktop or `sudo systemctl start docker`
- **"Port already in use"**: Run `make check` to identify the process
- **"Cluster not found"**: Run `make setup` first
- **"I only see 4 containers in docker ps"**: That's correct! Services run as pods inside worker nodes (see section above)
- **Any other issue**: Run `make check` for actionable error messages
