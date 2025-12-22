# X-RAG Project Guide for AI Agents

## 🚨 CRITICAL: Read the Project Plan First

**The complete project plan is located at:**
[docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md)

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
make help            # Show all commands
make check           # Validate prerequisites
make init            # Initialize local dev environment
make cluster-init    # Build Docker images
make cluster-start   # Start cluster and services
make cluster-stop    # Stop cluster
make cluster-status  # Show cluster status
make cluster-clean   # Delete cluster and data
make cluster-reset   # Reset cluster state
make cluster-destroy # Stop + delete images
make test            # Run tests
make code-style      # Check code style
make code-format     # Auto-fix code style
make ci              # Run all CI checks
make logs-*          # Tail service logs
```

### Port Mappings (External HTTP)
- **8080** = Search UI (web interface)
- **8081** = Weaviate
- **8082** = Ingestion API
- **3000** = Grafana
- **9090** = Prometheus

### Internal Service Ports
- **50051** = Embedding Service (gRPC)
- **50052** = Search Service (gRPC)
- **6379** = Redis
- **9092** = Kafka

### Kubernetes Namespaces
- **rag-system** = Application workloads (search-ui, embedding-service, indexer, etc.)
- **monitoring** = Observability stack (Prometheus, Grafana, Tempo, Loki, Alloy)
- **kubernetes-dashboard** = Kubernetes Dashboard

### Environment Setup
Copy `.env.example` to `.env` and add `OPENAI_API_KEY`

### Disabling Observability Stack
Set `OBSERVABILITY_ENABLED=false` in `.env` to disable the entire monitoring stack:
- Skips deployment of Prometheus, Grafana, Tempo, Loki, Alloy
- Skips kube-state-metrics, node-exporter, Kubernetes Dashboard
- Disables OTel metrics export in all services
- Services still expose local `/metrics` endpoints (just not scraped)

This saves significant resources when monitoring isn't needed for development.

## Development Principles

### No Default Values - Explicit Configuration Required
- **NEVER** use default values for configuration that could hide errors
- **ALL** provider/backend configuration must be explicitly set
- Missing configuration = immediate startup failure with clear error message
- This applies to: `EMBEDDING_GENERATOR`, `LLM_PROVIDER`, `LLM_API_KEY`, etc.
- Silent fallbacks are an anti-pattern - they hide configuration problems

### Always Use Makefile
- **NEVER** run scripts directly
- **ALWAYS** use `make` targets
- Example: Use `make check`, NOT `./scripts/check-prerequisites.sh`

### Opening Files and Folders
- When the user says "open [file|folder]", use the `open` command
- Example: `open /path/to/folder` or `open /path/to/file.txt`
- This opens the file/folder in Finder (macOS) or the default application

### Working with Symlinks in Data Folder
- The `data/` folder contains symlinks to external data sources
- **ALWAYS** use `find -L` to follow symlinks when searching in data/
- Example: `find -L /path/to/data -name "*.json"` (NOT `find /path/to/data -name "*.json"`)
- Without `-L`, find will not traverse into symlinked directories

### Makefile Conventions
When editing the Makefile:
- **ALWAYS** end every target with `@echo ""` for visual separation in terminal output
- This creates clean spacing between command outputs
- Example:
  ```makefile
  target-name: ## Description
      @echo "$(BLUE)=== Doing Something ===$(NC)"
      @./scripts/do-something.sh
      @echo ""  # ← Always include this at the end
  ```

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

### No Default Fallbacks in Code
When writing configuration classes or factory methods:
- **NEVER** provide default values for provider/backend selection
- Use `Field(...)` (Ellipsis = required) instead of `Field(default=...)`
- Factory methods must raise `ValueError` for unknown types
- Example:
  ```python
  # WRONG - silent fallback hides misconfiguration
  embedding_generator: str = Field(default="hash_based")

  # CORRECT - Ellipsis (...) means required, fails if not set
  embedding_generator: str = Field(..., description="Required - no default")
  ```

### Code Style
This project follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

**Checking compliance:**
```bash
make code-style   # Check code style (read-only)
make code-format  # Auto-fix style issues
```

### Fixing Check Failures
- **NEVER ignore files that fail a check** — fix the code, not the configuration
- Do NOT add per-file ignores to bypass linting/complexity rules
- Do NOT raise thresholds just to silence warnings
- If code is too complex, refactor it into smaller functions
- Generated code (e.g., `src/proto_gen/`) is already excluded in config — that's the only valid exclusion

Configuration: All linting and formatting rules are in `pyproject.toml` using Ruff with Google-style docstring conventions.

### Clean Code Principles
For comprehensive guidance on writing clean, maintainable code, see [docs/CLEAN_CODE_GUIDE.md](docs/CLEAN_CODE_GUIDE.md).

This guide covers:
- Naming conventions and intention-revealing names
- Function design and single responsibility
- SOLID principles with Python examples
- Error handling best practices
- Clean Architecture patterns
- Testing principles (F.I.R.S.T., AAA pattern)
- Component cohesion and coupling
- Complete multi-file architecture examples

**When to reference the guide:**
- Before writing new features or modules
- During code reviews
- When refactoring existing code
- When unsure about architectural decisions

### Logging Best Practices
For guidance on choosing appropriate log levels (ERROR, WARN, INFO, DEBUG), see [docs/LOGGING-GUIDE.md](docs/LOGGING-GUIDE.md).

**Key principle:** ERROR logs should be reserved for program-level failures requiring local action. Use WARN for operation-level failures and INFO for routine events.

### Future Tooling (Not Yet Implemented)

The following guides describe tools that may be added in the future:

- **[docs/HYPOTHESIS_GUIDE.md](docs/HYPOTHESIS_GUIDE.md)** - Property-based testing with Hypothesis
  - Generates random test inputs to find edge cases
  - Complements existing unit tests
  - Useful for testing chunking, serialization, and search invariants

- **[docs/SEMGREP_GUIDE.md](docs/SEMGREP_GUIDE.md)** - Semantic static analysis with Semgrep
  - Pattern-based code analysis (not regex-based like grep)
  - Encode architectural rules (e.g., "no direct Redis in domain layer")
  - Catches patterns that ruff/mypy/bandit cannot express

### Writing Tests
- **ALWAYS write tests for new Python code**
- **Update tests when code behavior is intentionally changed**
- **Do NOT change tests when the code's intention hasn't changed** — fix the code instead
- Tests are not optional — all new code requires corresponding tests

## Testing Workflow

When testing code changes, **ALWAYS** run these commands in order:

```bash
make code-format    # 1. Auto-fix code style issues
make code-style     # 2. Verify no linting errors remain
make code-deptry    # 3. Check dependency hygiene
make code-spell     # 4. Check spelling
make test           # 5. Run test suite
```

**All five must pass before committing code.** No exceptions.

Alternatively, run the full CI suite:
```bash
make ci  # Runs all checks: style + types + security + deps + spelling + tests
```

### Dependency Hygiene

This project uses **deptry** to enforce clean dependency management.

**Checking dependencies:**
```bash
make code-deptry  # Check dependency hygiene
```

**What deptry checks:**
- **DEP001**: Missing dependencies - imports not declared in pyproject.toml
- **DEP002**: Unused dependencies - declared deps never imported
- **DEP003**: Transitive dependencies - imports available only via transitive deps
- **DEP004**: Dev dependencies in production - dev deps imported in src/
- **DEP005**: Standard library declared - stdlib packages in dependencies

**Configuration:** All rules defined in `[tool.deptry]` section of `pyproject.toml`.

**When to update deptry configuration:**

1. **New non-runtime directories** (e.g., `benchmarks/`, `tools/`):
   - Add to `extend_exclude` in `[tool.deptry]`

2. **New first-party modules** (if project structure changes):
   - Add to `known_first_party` list

3. **New dev dependency groups** (e.g., `[project.optional-dependencies].benchmark`):
   - Add group name to `pep621_dev_dependency_groups`

4. **Legitimate dynamic dependencies** (loaded by name from config):
   - Add to `[tool.deptry.per_rule_ignores]` with justification comment
   - Example: `DEP002 = ["plugin-package"]  # Loaded dynamically by plugin system`

**Do NOT disable entire rules.** Use `per_rule_ignores` for specific packages only.

### Spellchecking

This project uses **codespell** to catch typos in code and documentation.

**Checking spelling:**
```bash
make code-spell  # Check spelling in src, tests, docs, scripts, infra, proto
```

**Configuration:** Defined in `[tool.codespell]` section of `pyproject.toml`.

**Ignore file:** Domain-specific terms are listed in `config/codespell-ignore.txt`. Add new terms when you encounter false positives.

**When to update the ignore list:**
- New technology/library names (e.g., `grpcio`, `weaviate`)
- Project-specific terms (e.g., `xrag`)
- Legitimate technical terms flagged as typos

## Version Control

### Git Commands
- **NEVER** use `git -C` command format
- **ALWAYS** run git commands directly from the repository root
- If in a different directory, `cd` to the repo first

### Git Commits
- **NEVER** attribute AI in commit messages
- Commit after each milestone
- Use conventional format: `<type>: <description>`
- Types: feat, fix, docs, infra, test, refactor, chore

## Implementation Status

### ✅ Completed (13/13 phases = 100%)
- Phase 0: .gitignore
- Phase 1: Foundation (Makefile, scripts, pyproject.toml, .env.example, directory structure)
- Phase 2: Infrastructure Implementation (Kind cluster, K8s manifests)
- Phase 3: gRPC Protocol Definitions
- Phase 4: Common Modules (health checks, config, domain models)
- Phase 5: Embedding Service (gRPC server, OpenAI backend, Dockerfile, K8s manifests)
- Phase 6: Ingestion API (FastAPI + Kafka + MinIO)
- Phase 7: Indexer (Kafka consumer + document processing)
- Phase 8: Search Service (gRPC server, Haystack RAG pipeline, hybrid search)
- Phase 9: Search UI (FastAPI web interface, Jinja2 templates, async gRPC client)
- Phase 10: Haystack Integration (DocumentCleaner, DocumentSplitter with overlap support)
- Phase 11: Testing (546 tests: 538 unit + 8 integration, 78% coverage)
- Phase 12: Documentation (README, QUICKSTART, TROUBLESHOOTING, SYSTEM-DIAGRAM)
- Phase 13: Validation (completed December 2025)

### 📋 Pending
- None - all phases complete!

### 🚀 Production Ready
The system has been validated end-to-end with:
- 53 documents ingested from video transcripts
- 4,467 chunks indexed in Weaviate
- Hybrid search returning AI-generated answers with sources

## Recent Fixes

### December 2025 - Phase 13 Validation Results

**Validation Summary**: All systems operational
- ✅ `make check` - All prerequisites validated (Docker, kubectl, Kind, Helm, uv)
- ✅ Cluster running with 15/15 pods healthy
- ✅ Search endpoint working (POST http://localhost:8080/api/search)
- ✅ Ingestion endpoint working (POST http://localhost:8082/ingest)
- ✅ Prometheus collecting metrics from all 6 services
- ✅ Grafana accessible at http://localhost:3000

**Issues Fixed During Validation:**
1. **Prometheus scrape targets misconfigured** (infra/k8s/monitoring/prometheus.yaml)
   - Issue: Prometheus was scraping wrong ports for several services
   - Fix: Updated scrape targets to correct metrics ports:
     - search-ui: 9091 (was 8080)
     - search-service: 8080 (was 50051)
     - embedding-service: 8080 (was 50051)
     - indexer: 8081 (was 8084)

2. **search-ui service missing metrics port** (infra/k8s/search-ui/service.yaml)
   - Issue: Service only exposed port 8080, but metrics server runs on 9091
   - Fix: Added metrics port (9091) to service definition

**Notes:**
- LLM backend (LM Studio) requires initial model loading on first search request
- First search request may fail while model loads; subsequent requests work normally

### December 2025 - Phase 7 Validation & Bug Fixes

**Testing Summary**: 546/546 tests passing (100% success rate)
- ✅ 538/538 unit tests passed
- ✅ 8/8 integration tests passed
- ✅ 78.10% line coverage
- ✅ E2E document ingestion flow working
- ✅ Cluster lifecycle robust and reliable

**New Test Files Added (December 2025):**
- `tests/unit/core/test_document.py` - CoreDocument tests (100% coverage)
- `tests/unit/core/test_errors.py` - Error hierarchy tests (100% coverage)
- `tests/unit/core/test_interfaces.py` - Protocol tests (100% coverage)
- `tests/unit/common/test_grpc_utils.py` - gRPC utilities tests (87% coverage)
- `tests/unit/common/test_metrics.py` - Prometheus metrics tests (100% coverage)
- `tests/unit/llm/test_openai_client.py` - LLM client tests (100% coverage)
- `tests/unit/embedding_service/generators/test_factory.py` - Factory tests (100% coverage)
- `tests/unit/embedding_service/generators/test_hash_based_generator.py` - Hash generator tests (98% coverage)
- `tests/unit/embedding_service/generators/test_openai_generator.py` - OpenAI generator tests (100% coverage)
- `tests/unit/ingestion_api/test_kafka_client.py` - Kafka client tests (94% coverage)
- `tests/unit/ingestion_api/test_minio_client.py` - MinIO client tests (100% coverage)
- `tests/unit/indexer/test_grpc_clients.py` - Indexer gRPC client tests (100% coverage)
- `tests/unit/search_service/test_grpc_clients.py` - Search service gRPC client tests (100% coverage)

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

## Prometheus Metrics System

All services expose Prometheus metrics following the **Four Golden Signals** pattern.

### Metric Types

| Signal | Type | Purpose |
|--------|------|---------|
| Latency | Histogram | Request/operation duration with percentiles (p50, p95, p99) |
| Traffic | Counter | Request counts, documents processed |
| Errors | Counter | Error counts by type |
| Saturation | Gauge | Active requests, queue depths |

### Histogram Buckets

Histograms use explicit buckets for accurate percentile calculation:

| Type | Target p99 | Use Case |
|------|------------|----------|
| FAST | < 100ms | Embedding, cache lookups |
| MEDIUM | < 500ms | Weaviate queries, text processing |
| SLOW | < 30s | LLM generation, full search pipeline |
| BATCH | < 5s | Kafka consume, batch operations |

### Adding Metrics to Code

```python
from src.common.metrics import track_latency, BucketConfig, OperationType
from prometheus_client import Histogram

# Define histogram with appropriate buckets
my_duration = Histogram(
    "my_service_operation_seconds",
    "Operation duration",
    ["method"],  # optional labels
    buckets=BucketConfig.get(OperationType.FAST),
)

# Use context manager to track latency
with track_latency(my_duration, {"method": "search"}):
    result = do_operation()
```

### Service Metrics Modules

Each service has a dedicated metrics module:
- `src/search_service/metrics.py`
- `src/embedding_service/metrics.py`
- `src/indexer/metrics.py`
- `src/ingestion_api/metrics.py`
- `src/search_ui/metrics.py`

### Documentation

Complete metric catalog with PromQL examples: [docs/METRICS.md](docs/METRICS.md)

### Testing Metrics

```bash
# Run metrics unit tests
uv run pytest tests/unit/common/test_metrics*.py -v

# Verify metrics endpoint (after cluster start)
kubectl port-forward svc/search-service 9090:8080
curl -s http://localhost:9090/metrics | grep search_service
```

## Retrieval Evaluation

The eval harness measures retrieval quality using standard IR metrics. It reuses production components - no duplicate configs or clients.

### Running Evaluations

```bash
make eval                                    # Run with production.yaml (default)
make eval CONFIG=evals/configs/baseline.yaml # Run with specific config
```

### Configuration

YAML configs in `evals/configs/` specify embedding provider and search parameters:

```yaml
name: production-v1
dataset_path: data/eval/.../dataset.json
embedding:
  provider: local  # Uses EmbeddingConfig.for_local()
  model: text-embedding-bge-large-en-v1.5
  base_url: http://localhost:1234/v1
search:
  mode: hybrid
  top_k: 10
  alpha: 0.5
```

Providers:
- `local` → LM Studio/Ollama (requires running server)
- `hash_based` → Deterministic hashing (no network, for testing)
- `openai` → OpenAI API (requires `OPENAI_API_KEY`)

### Metrics

| Metric | Description |
|--------|-------------|
| Recall@K | % of relevant chunks retrieved in top K |
| Precision@K | % of top K results that are relevant |
| Hit Rate@K | % of queries with at least 1 relevant result |
| MRR | Mean Reciprocal Rank of first relevant result |
| NDCG@K | Normalized Discounted Cumulative Gain |

### Reports

Results saved to `evals/reports/{config-name}-{timestamp}.json`:

```json
{
  "run_id": "production-v1-20251205-224957",
  "metrics": {
    "recall_at_k": 0.588,
    "mrr": 0.411,
    "ndcg_at_k": 0.468
  }
}
```

### Key Design Principle

The eval harness uses **production components directly**:
- `EmbeddingConfig` from `src/llm/config.py`
- `EmbeddingGeneratorFactory` from `src/embedding_service/generators/factory.py`
- Embedded Weaviate for isolated testing

No duplicate configs or clients. The eval is just a thin orchestrator.

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
   - Prometheus metrics now implemented (see "Prometheus Metrics System" section)
   - Still missing: request correlation across services
   - Enhancement: Add OpenTelemetry + Jaeger for trace context propagation

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

### Advanced Kind and Pod Access

For advanced operations like copying files to/from pods, debugging containers without shells, inspecting containerd, and accessing services externally, see [docs/KIND-ACCESS-CHEAT-SHEET.md](docs/KIND-ACCESS-CHEAT-SHEET.md).

## Common Issues

- **"Docker daemon not running"**: Start Docker Desktop or `sudo systemctl start docker`
- **"Port already in use"**: Run `make check` to identify the process
- **"Cluster not found"**: Run `make setup` first
- **"I only see 4 containers in docker ps"**: That's correct! Services run as pods inside worker nodes (see section above)
- **Any other issue**: Run `make check` for actionable error messages
