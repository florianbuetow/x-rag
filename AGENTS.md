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

## Quick Reference

### Available Make Targets
**ALWAYS use Makefile, NEVER run scripts directly:**

```bash
make help         # Show all commands
make check        # Validate prerequisites
make setup        # One-time setup
make start        # Build and deploy apps
make stop         # Stop services
make status       # Show status
make test         # Run tests
make lint         # Check code style
make format       # Auto-fix code style
make clean        # Delete everything
make destroy      # Stop + delete images
make logs-*       # Tail service logs
```

### Port Mappings
- **8080** = Search UI
- **8081** = Weaviate
- **8082** = Ingestion API
- **3000** = Grafana
- **9090** = Prometheus
- **6379** = Redis
- **9092** = Kafka

### Environment Setup
Copy `.env.example` to `.env` and add `OPENAI_API_KEY`

## Development Principles

### Always Use Makefile
- **NEVER** run scripts directly
- **ALWAYS** use `make` targets
- Example: Use `make check`, NOT `./scripts/check-prerequisites.sh`

### Everything Runs in Kubernetes
- **NO local development outside Kind cluster**
- All services run inside the cluster
- No `dev-*` targets in Makefile

### Python & Dependencies
- Python version managed by `uv` (defined in pyproject.toml)
- Don't check for Python version in prerequisites
- All dependencies in pyproject.toml
- **ALWAYS** use `uv run python` instead of `python` directly
- **NEVER** run Python outside the virtual environment

### Docker Configuration
- Minimum: 6GB RAM, 4 cores
- Recommended: 10GB RAM, 8 cores
- Use "cores" not "CPUs" in all messaging
- Resource check output format:
  ```
  System Resources:
    Recommended: 10GB RAM, 8 cores
    Available: 31GB RAM, 16 cores (via docker configuration) ✓
  ```

## Coding Guidelines

### Code Style
This project follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

**Checking compliance:**
```bash
make lint    # Check code style (read-only)
make format  # Auto-fix style issues
```

Configuration: All linting and formatting rules are in `pyproject.toml` using Ruff with Google-style docstring conventions.

### Writing Tests
- **ALWAYS write tests for new Python code**
- **Update tests when code behavior is intentionally changed**
- **Do NOT change tests when the code's intention hasn't changed** — fix the code instead
- Tests are not optional — all new code requires corresponding tests

## Testing Workflow

When testing code changes, **ALWAYS** run these commands in order:

```bash
make format  # 1. Auto-fix code style issues
make lint    # 2. Verify no linting errors remain
make test    # 3. Run test suite
```

**All three must pass before committing code.** No exceptions.

## Version Control

### Git Commits
- **NEVER** attribute AI in commit messages
- Commit after each milestone
- Use conventional format: `<type>: <description>`
- Types: feat, fix, docs, infra, test, refactor, chore

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

## Recent Fixes

### December 2025 - Phase 7 Validation & Bug Fixes

**Testing Summary**: 20/20 tests passing (100% success rate)
- ✅ 15/15 unit tests passed
- ✅ 5/5 integration tests passed
- ✅ E2E document ingestion flow working
- ✅ Cluster lifecycle robust and reliable

### First Round: Quick Fixes (6 items)
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

### Second Round: Critical Bug Fixes (4 items)

7. **Race condition in duplicate detection** (src/indexer/processor.py:374-415) - ✅ FIXED
   - Issue: Multiple indexer replicas could process same document simultaneously
   - Root Cause: Check-then-insert pattern without atomic operations
   - Fix: Implemented distributed locking using Redis
   - Implementation:
     - Added Redis client to DocumentProcessor
     - Created `document_lock()` context manager
     - Wrapped duplicate check and processing in distributed lock
     - Lock timeout: 300 seconds (configurable)
     - Lock blocks other replicas for up to 10 seconds before timeout
   - Impact: Indexer can now safely scale to multiple replicas without duplicates

8. **Blocking operations in indexer** (src/indexer/processor.py:374-415) - ✅ FIXED
   - Issue: Synchronous MinIO/Weaviate/gRPC calls blocked async event loop
   - Root Cause: `async def process_event()` called synchronous blocking methods
   - Fix: Wrapped all blocking I/O in `asyncio.to_thread()`
   - Operations now running in thread pool:
     - MinIO document loading
     - Text chunking (CPU-bound)
     - gRPC embedding requests
     - Weaviate queries and inserts
   - Impact: Event loop remains responsive, supports concurrent document processing

9. **Weaviate connection thread safety** (src/indexer/processor.py:92-138) - ✅ FIXED
   - Issue: Lazy initialization had race condition without synchronization
   - Root Cause: Multiple threads could see `weaviate_client is None` and both connect
   - Fix: Implemented double-checked locking pattern with `threading.Lock()`
   - Pattern: Fast path (check without lock) + slow path (acquire lock and double-check)
   - Impact: Only one Weaviate connection created, thread-safe initialization

10. **MinIO credentials exposed** (infra/k8s/minio/) - ✅ FIXED
    - Issue: Default credentials hardcoded in plain text in minio.yaml
    - Security Risk: Credentials visible in git history
    - Fix: Moved credentials to Kubernetes Secret
    - Files changed:
      - Created `infra/k8s/minio/secret.yaml` with credentials
      - Updated `infra/k8s/minio/minio.yaml` to use secretKeyRef
      - Deployment script automatically applies secret (directory-based apply)
    - Impact: Credentials no longer in plain text in tracked files

## Design Choices (Intentional for Dev Environment)

These are NOT bugs - they are intentional configuration choices for local development:

1. **No TLS for inter-service communication**
   - All gRPC and HTTP traffic unencrypted within cluster
   - Intentional: Simplifies local development
   - Production: Must enable mTLS

2. **Weaviate anonymous access enabled**
   - Authentication disabled for development
   - Intentional: Easier local testing
   - Production: Require API keys and RBAC

3. **Kafka replication factor = 1** (infra/k8s/kafka/kafka.yaml)
   - Single replica = no high availability
   - Intentional: Single-node Kind cluster, limited resources
   - Production: Increase to 3 replicas with proper HA setup

4. **Redis without authentication**
   - No password required for Redis connections
   - Intentional: Dev environment within cluster
   - Production: Enable AUTH and ACLs

## Future Enhancements (Not Required for Phase 7)

5. **Service list duplication** (scripts/build-images.sh, scripts/deploy-apps.sh)
   - Service names hardcoded in multiple scripts
   - Priority: Low (works fine, just not DRY)
   - Enhancement: Centralize in Makefile variable

6. **Missing dev-* targets**
   - No `dev-embedding`, `dev-ingest`, `dev-indexer` targets
   - Note: User explicitly rejected dev-* targets (everything runs in K8s)
   - Enhancement: Could add for faster iteration with --reload

7. **No distributed tracing**
   - Difficult to debug cross-service issues
   - Phase: 8+ (Observability)
   - Enhancement: Add OpenTelemetry + Jaeger

8. **Chunk overlap not implemented** (src/indexer/processor.py)
   - Current: Fixed-size non-overlapping chunks
   - Works as designed for MVP
   - Enhancement: Add sliding window with configurable overlap

9. **Complex health check probes** (K8s deployments)
   - Using Python exec commands for gRPC health checks
   - Works correctly, just verbose
   - Enhancement: Could simplify to TCP probes (loses semantic health info)

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
