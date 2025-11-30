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
│  ┌──────────────────┐  ┌──────────────────┐    │
│  │ xrag-k8-worker   │  │ xrag-k8-worker2  │    │
│  ├──────────────────┤  ├──────────────────┤    │
│  │ Pods:            │  │ Pods:            │    │
│  │ • Redis          │  │ • MinIO          │    │
│  │ • Kafka          │  │ • Weaviate       │    │
│  │ • Grafana        │  │                  │    │
│  │ • Prometheus     │  │                  │    │
│  └──────────────────┘  └──────────────────┘    │
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
