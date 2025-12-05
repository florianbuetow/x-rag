# X-RAG Quick Start Guide

Get X-RAG running in under 5 minutes.

## Prerequisites

Ensure you have the following installed:

- **Docker Desktop** (6GB+ RAM allocated, 4+ cores)
- **uv** (Python package manager) - [Install](https://docs.astral.sh/uv/getting-started/installation/)
- **Kind** (Kubernetes in Docker) - `brew install kind` or [other methods](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- **kubectl** - `brew install kubectl` or [other methods](https://kubernetes.io/docs/tasks/tools/)

## Setup

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/x-rag.git
cd x-rag

# Copy environment template and add your OpenAI API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

### 2. Validate Prerequisites

```bash
make check
```

This verifies all tools are installed and Docker has sufficient resources.

### 3. Start the Cluster

```bash
make init           # Install dependencies and generate gRPC code
make cluster-init   # Build Docker images
make cluster-start  # Start Kind cluster and deploy all services
```

Wait for all pods to be ready (typically 2-3 minutes):

```bash
make cluster-status
```

## Using X-RAG

### Access the Search UI

Open your browser to [http://localhost:8080](http://localhost:8080)

Or use the make command:

```bash
make open-search-ui
```

### Ingest a Document

Use the Ingestion API to add documents:

```bash
curl -X POST http://localhost:8082/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
    "metadata": {
      "title": "ML Introduction",
      "type": "text"
    },
    "namespace": "default"
  }'
```

**Note**: The metadata schema requires a `title` field and optionally accepts `source_file`, `type`, and `transcription_method`.

Or open the API docs at [http://localhost:8082/docs](http://localhost:8082/docs) to use the interactive interface.

### Search

Once documents are indexed (takes a few seconds), search via the UI or API:

```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "mode": "hybrid",
    "top_k": 5
  }'
```

## Common Commands

| Command | Description |
|---------|-------------|
| `make cluster-status` | Check cluster and pod health |
| `make cluster-stop` | Stop the cluster (preserves data) |
| `make cluster-start` | Restart a stopped cluster |
| `make cluster-clean` | Delete cluster and all data |
| `make logs-<service>` | View service logs (e.g., `make logs-indexer`) |
| `make test` | Run the test suite |

## Port Reference

| Port | Service |
|------|---------|
| 8080 | Search UI |
| 8081 | Weaviate |
| 8082 | Ingestion API |
| 3000 | Grafana (admin/admin) |
| 9090 | Prometheus |

## Next Steps

- **Architecture**: See [SYSTEM-DIAGRAM.md](./SYSTEM-DIAGRAM.md) for system design details
- **Project Plan**: See [PROJECT-PLAN.md](./PROJECT-PLAN.md) for comprehensive reference
- **Troubleshooting**: See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues
- **Development**: See [README.md](../README.md) for development workflow
