# X-RAG Project Guide for AI Agents

## 🚨 CRITICAL: Read the Project Plan First

**The complete project plan is located at:**
`/Users/flo/.claude/plans/mighty-jumping-bachman.md`

**You MUST read the project plan before working on this project.**

This file (AGENTS.md) contains only **operational rules** and **current status**.

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
- **Port Mappings**: See project plan (8080=UI, 8081=Weaviate, 8082=Ingestion, 3000=Grafana, 9090=Prometheus)
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

## Common Issues

- **"Docker daemon not running"**: Start Docker Desktop or `sudo systemctl start docker`
- **"Port already in use"**: Run `make check` to identify the process
- **"Cluster not found"**: Run `make setup` first
- **Any other issue**: Run `make check` for actionable error messages
