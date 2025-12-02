# RAG Platform Hackathon: Pre-Event Setup Guide

This document contains everything needed to prepare the development environment before the hackathon. The goal is to eliminate all infrastructure setup time so participants can write application code from minute one.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Summary](#architecture-summary)
3. [Pre-Hackathon Checklist](#pre-hackathon-checklist)
4. [Infrastructure Setup](#infrastructure-setup)
   - [Prerequisites](#prerequisites)
   - [Kind Installation](#kind-installation)
   - [Kind Cluster Setup](#kind-cluster-setup)
   - [Local Container Registry](#local-container-registry)
5. [Service Deployments](#service-deployments)
   - [Weaviate (Vector Database)](#weaviate-vector-database)
   - [Kafka (Message Queue)](#kafka-message-queue)
   - [MinIO (Document Storage)](#minio-document-storage)
   - [Redis (Caching)](#redis-caching)
   - [Prometheus & Grafana (Observability)](#prometheus--grafana-observability)
6. [Application Scaffolding](#application-scaffolding)
   - [Directory Structure](#directory-structure)
   - [Domain Core (Interfaces)](#domain-core-interfaces)
   - [Working Baseline Implementation](#working-baseline-implementation)
   - [Stub Implementations for Participants](#stub-implementations-for-participants)
7. [Sample Data Preparation](#sample-data-preparation)
8. [Developer Experience Setup](#developer-experience-setup)
   - [Makefile Commands](#makefile-commands)
   - [Environment Configuration](#environment-configuration)
9. [Testing Infrastructure](#testing-infrastructure)
10. [Documentation for Participants](#documentation-for-participants)
11. [Troubleshooting Guide](#troubleshooting-guide)
12. [Day-of Checklist](#day-of-checklist)

---

## Overview

### What Participants Get on Day 1

```bash
git clone https://github.com/your-org/rag-hackathon-starter
cd rag-hackathon-starter
make cluster-start
# → Everything running in 2-3 minutes
```

### System Capabilities (Post-Hackathon Target)

The full RAG platform design includes:

- **Three retrieval primitives**: Vector (Weaviate), Lexical (OpenSearch), Graph (Neo4j)
- **Orchestration strategies**: Single-hop, multi-hop, graph-augmented retrieval
- **Re-ranking**: Cross-encoder and LLM-based rerankers
- **Caching**: Redis for query and LLM response caching
- **Observability**: Prometheus, Grafana, structured logging
- **Evaluation**: Dedicated evaluation service with test datasets
- **Security**: Sidecar-based secrets management
- **Multi-namespace**: Per-domain isolation and scaling

### Hackathon Scope (72-Hour Target)

For the hackathon, we provide a working baseline with:

- ✅ Vector retrieval (Weaviate)
- ✅ Single-hop orchestration
- ✅ LLM answer generation (OpenAI)
- ✅ Document ingestion pipeline (Kafka + MinIO)
- ✅ Caching layer (Redis)
- ✅ Basic observability (Prometheus + Grafana)
- ✅ Clean interfaces for all future components

Participants can then implement:

- ⚡ Lexical search (OpenSearch integration)
- ⚡ Re-ranking (cross-encoder or LLM-based)
- ⚡ Multi-hop retrieval
- ⚡ Graph RAG (Neo4j integration)
- ⚡ Custom applications

---

## Architecture Summary

### System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      USERS                              │
└─────────────────────────────────────────────────────────┘
              │                         │
              ▼                         ▼
   ┌────────────────────┐    ┌────────────────────┐
   │    Search API      │    │   Ingestion API    │
   │    (FastAPI)       │    │   (FastAPI)        │
   │    - /search       │    │   - /ingest        │
   │    - /health       │    │   - /health        │
   │    - /metrics      │    │   - /metrics       │
   └────────────────────┘    └────────────────────┘
         │       │                    │       │
         │       │                    ▼       │
         │       │           ┌──────────────┐ │
         │       │           │    MinIO     │ │
         │       │           │(raw documents)│
         │       │           └──────────────┘ │
         │       │                    ▲       │
         ▼       ▼                    │       ▼
  ┌──────────────────┐                │  ┌──────────────┐
  │ Embedding Service│                │  │    Kafka     │
  │ - /embed         │                │  │ (doc-changes)│
  │ - /health        │                │  └──────────────┘
  │ - /metrics       │                │        │
  └──────────────────┘                │        ▼
         │    ▲                       │  ┌──────────────────┐
         │    │                       │  │     Indexer      │
         │    │                       │  │  - Kafka consumer│
         │    └───────────────────────┼──│  - Chunking      │
         │      query embeddings      │  │  - /health       │
         │                            │  │  - /metrics      │
         ▼                            │  └──────────────────┘
  ┌──────────────────┐                │        │
  │ Embedding Backend│                │        │ embed chunks
  │ (one of):        │                │        ▼
  │ - OpenAI API     │                │  ┌──────────────────┐
  │ - FastText       │                │  │ Embedding Service│
  │ - Sentence-Trans │                │  └──────────────────┘
  └──────────────────┘                │        │
                                      │        │ store vectors
         ┌────────────────────────────┼────────┘
         │                            │
         ▼                            │
  ┌──────────────────┐                │
  │    Weaviate      │◄───────────────┘
  │  - Vector search │    fetch docs
  │  - BM25 lexical  │
  │  - Hybrid search │
  └──────────────────┘
         ▲
         │ search queries
  ┌──────┴───────┐
  │  Search API  │
  └──────────────┘

  ┌──────────────┐
  │    Redis     │◄─────── Search API (caching)
  │   (cache)    │
  └──────────────┘

  ┌──────────────┐
  │  OpenAI API  │◄─────── Search API (LLM answer generation)
  │    (LLM)     │
  └──────────────┘

  ┌──────────────────┐      ┌──────────────────┐
  │    Prometheus    │◄────►│     Grafana      │
  │                  │      └──────────────────┘
  │ Scrapes /metrics │
  │ from all services│
  └──────────────────┘
```

### Weaviate Search Modes

Weaviate provides all three search modes in a single instance:

| Mode | How it works | Use case |
|------|--------------|----------|
| **Vector** | HNSW nearest neighbor on embeddings | Semantic similarity |
| **BM25** | Inverted index, term frequency | Keyword matching |
| **Hybrid** | Combines vector + BM25 with alpha weight | Best of both |

No need for separate instances - configure search mode per query:

```python
# Vector only
results = weaviate.query(query, mode="vector")

# BM25 only  
results = weaviate.query(query, mode="bm25")

# Hybrid (alpha=0.5 means 50% vector, 50% BM25)
results = weaviate.query(query, mode="hybrid", alpha=0.5)
```

### Component Responsibilities

| Component | Purpose | Endpoints | K8s Resource |
|-----------|---------|-----------|--------------|
| Search API | Search, LLM answer generation | `/search`, `/health`, `/metrics` | Deployment |
| Ingestion API | Document upload, publish to Kafka | `/ingest`, `/health`, `/metrics` | Deployment |
| Embedding Service | Generate embeddings (OpenAI/FastText/etc) | `/embed`, `/health`, `/metrics` | Deployment |
| Indexer | Chunking, call Embedding Service, Weaviate writes | `/health`, `/metrics` | Deployment |
| Weaviate | Vector + BM25 + Hybrid search | REST/GraphQL | StatefulSet |
| Kafka | Document change event streaming | - | StatefulSet |
| MinIO | Raw document storage | S3 API | StatefulSet |
| Redis | Query and LLM response caching | - | StatefulSet |
| Prometheus | Scrape `/metrics` from all services | - | Deployment |
| Grafana | Metrics visualization | - | Deployment |

---

## Pre-Hackathon Checklist

### 1 Week Before

- [ ] Repository created and tested on fresh machines (macOS, Linux, Windows/WSL2)
- [ ] All infrastructure manifests written and tested
- [ ] Kind cluster setup verified on all target platforms
- [ ] Sample data prepared (50-100 documents per domain)
- [ ] Working baseline implementation complete
- [ ] All stub implementations created with clear TODOs
- [ ] Test suite validates implementations
- [ ] Documentation reviewed by someone unfamiliar with project
- [ ] OpenAI API keys provisioned with spending limits ($50-100 per team)
- [ ] Backup API keys ready
- [ ] Mentor team identified and briefed

### 1 Day Before

- [ ] Fresh clone and `make cluster-start` tested on multiple machines
- [ ] Sample searches returning correct results
- [ ] Grafana dashboards loading correctly
- [ ] All test commands passing
- [ ] API key distribution plan confirmed

### Day Of (First 30 Minutes)

- [ ] Share repository link with participants
- [ ] Distribute API keys
- [ ] Have 2-3 mentors available for setup issues
- [ ] Verify at least one successful `make cluster-start` per team

---

## Infrastructure Setup

### Prerequisites

```bash
# Required tools
docker --version      # Docker 24.0+
kubectl version       # kubectl 1.28+
kind version          # Kind 0.20+
helm version          # Helm 3.12+
python --version      # Python 3.11+
make --version        # GNU Make
```

#### System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB free | 50 GB free |
| Docker Memory | 6 GB | 10 GB |

**Important**: Configure Docker Desktop to allocate at least 6GB RAM (Settings → Resources → Memory).

---

### Kind Installation

#### macOS

```bash
brew install kind
```

#### Linux

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

#### Windows (PowerShell as Administrator)

```powershell
choco install kind
```

#### Verify Installation

```bash
kind version
# Expected: kind v0.23.0 go1.21.x ...
```

---

### Kind Cluster Setup

#### Cluster Configuration

Create `infra/kind/cluster-config.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: rag-hackathon

nodes:
  - role: control-plane
    extraPortMappings:
      # Search API
      - containerPort: 30080
        hostPort: 8080
        protocol: TCP
      # Ingestion API
      - containerPort: 30082
        hostPort: 8082
        protocol: TCP
      # Grafana
      - containerPort: 30030
        hostPort: 3000
        protocol: TCP
      # Prometheus
      - containerPort: 30090
        hostPort: 9090
        protocol: TCP
      # Weaviate
      - containerPort: 30081
        hostPort: 8081
        protocol: TCP
    extraMounts:
      - hostPath: ./data/storage
        containerPath: /var/local-path-provisioner

  - role: worker
    extraMounts:
      - hostPath: ./data/storage
        containerPath: /var/local-path-provisioner

  - role: worker
    extraMounts:
      - hostPath: ./data/storage
        containerPath: /var/local-path-provisioner
```

#### Cluster Creation Script

Create `scripts/setup-kind-cluster.sh`:

```bash
#!/bin/bash
set -euo pipefail

CLUSTER_NAME="rag-hackathon"
REG_NAME="kind-registry"
REG_PORT="5000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

echo "=============================================="
echo "  RAG Hackathon - Kind Cluster Setup"
echo "=============================================="

# Check prerequisites
echo "[1/5] Checking prerequisites..."

for cmd in docker kind kubectl helm; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd is required but not installed."
        exit 1
    fi
    echo "  ✓ $cmd found"
done

if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running."
    exit 1
fi
echo "  ✓ Docker daemon running"

# Create local registry
echo "[2/5] Setting up local container registry..."

if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" != "true" ]; then
    docker rm -f "${REG_NAME}" 2>/dev/null || true
    docker run -d --restart=always -p "127.0.0.1:${REG_PORT}:5000" --name "${REG_NAME}" registry:2
    echo "  ✓ Registry created at localhost:${REG_PORT}"
else
    echo "  ✓ Registry already running"
fi

# Create Kind cluster
echo "[3/5] Creating Kind cluster..."

mkdir -p "${PROJECT_ROOT}/data/storage"

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "  Deleting existing cluster..."
    kind delete cluster --name "${CLUSTER_NAME}"
fi

cd "${PROJECT_ROOT}"
kind create cluster --config infra/kind/cluster-config.yaml --wait 120s
echo "  ✓ Cluster created"

# Connect registry to cluster network
echo "[4/5] Connecting registry to cluster..."

if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${REG_NAME}")" == 'null' ]; then
    docker network connect "kind" "${REG_NAME}"
fi

kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REG_PORT}"
EOF
echo "  ✓ Registry connected"

# Create namespace
echo "[5/5] Creating namespace..."

kubectl create namespace rag-system --dry-run=client -o yaml | kubectl apply -f -
echo "  ✓ Namespace created"

echo ""
echo "=============================================="
echo "  Cluster Ready!"
echo "=============================================="
echo ""
echo "Registry: localhost:${REG_PORT}"
echo "Nodes:    $(kubectl get nodes --no-headers | wc -l | tr -d ' ')"
echo ""
echo "Next: Run 'make deploy-services'"
```

Make executable:

```bash
chmod +x scripts/setup-kind-cluster.sh
```

---

### Local Container Registry

The setup script creates a local registry at `localhost:5000`. Use it like this:

```bash
# Build and push
docker build -t localhost:5000/rag-api:latest .
docker push localhost:5000/rag-api:latest

# Reference in K8s manifests
# image: localhost:5000/rag-api:latest
```

---

## Service Deployments

### Deployment Order

Deploy in this order due to dependencies:

1. Weaviate, Kafka, MinIO, Redis (storage/messaging)
2. Prometheus, Grafana (observability)
3. RAG API, Indexer (application)

---

### Weaviate (Vector Database)

Create `infra/k8s/weaviate/weaviate.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: weaviate
  namespace: rag-system
spec:
  type: NodePort
  ports:
    - port: 8080
      targetPort: 8080
      nodePort: 30081
  selector:
    app: weaviate
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: weaviate
  namespace: rag-system
spec:
  serviceName: weaviate
  replicas: 1
  selector:
    matchLabels:
      app: weaviate
  template:
    metadata:
      labels:
        app: weaviate
    spec:
      containers:
        - name: weaviate
          image: cr.weaviate.io/semitechnologies/weaviate:1.25.0
          ports:
            - containerPort: 8080
          env:
            - name: QUERY_DEFAULTS_LIMIT
              value: "25"
            - name: AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED
              value: "true"
            - name: PERSISTENCE_DATA_PATH
              value: "/var/lib/weaviate"
            - name: DEFAULT_VECTORIZER_MODULE
              value: "text2vec-openai"
            - name: ENABLE_MODULES
              value: "text2vec-openai,generative-openai"
            - name: CLUSTER_HOSTNAME
              value: "node1"
          volumeMounts:
            - name: data
              mountPath: /var/lib/weaviate
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2000m"
              memory: "4Gi"
          livenessProbe:
            httpGet:
              path: /v1/.well-known/ready
              port: 8080
            initialDelaySeconds: 120
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /v1/.well-known/ready
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

Create `infra/k8s/weaviate/schema-init.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: weaviate-schema-init
  namespace: rag-system
data:
  init-schema.py: |
    #!/usr/bin/env python3
    import os, sys, time, json, urllib.request, urllib.error
    
    WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://weaviate:8080")
    
    def wait_for_weaviate():
        for i in range(30):
            try:
                req = urllib.request.Request(f"{WEAVIATE_URL}/v1/.well-known/ready")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        return True
            except Exception as e:
                print(f"Waiting... {e}")
            time.sleep(2)
        return False
    
    def create_schema():
        schema = {
            "class": "DocumentChunk",
            "vectorizer": "text2vec-openai",
            "moduleConfig": {"text2vec-openai": {"model": "text-embedding-3-small"}},
            "properties": [
                {"name": "content", "dataType": ["text"]},
                {"name": "doc_id", "dataType": ["text"]},
                {"name": "chunk_index", "dataType": ["int"]},
                {"name": "namespace", "dataType": ["text"]},
                {"name": "source", "dataType": ["text"]},
                {"name": "title", "dataType": ["text"]},
                {"name": "metadata_json", "dataType": ["text"]}
            ]
        }
        
        try:
            req = urllib.request.Request(f"{WEAVIATE_URL}/v1/schema/DocumentChunk")
            urllib.request.urlopen(req)
            print("Schema exists")
            return True
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        
        data = json.dumps(schema).encode()
        req = urllib.request.Request(f"{WEAVIATE_URL}/v1/schema", data=data,
                                      headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print("Schema created")
        return True
    
    if not wait_for_weaviate():
        sys.exit(1)
    if not create_schema():
        sys.exit(1)
---
apiVersion: batch/v1
kind: Job
metadata:
  name: weaviate-schema-init
  namespace: rag-system
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: init
          image: python:3.11-slim
          command: ["python", "/scripts/init-schema.py"]
          env:
            - name: WEAVIATE_URL
              value: "http://weaviate:8080"
          volumeMounts:
            - name: scripts
              mountPath: /scripts
      volumes:
        - name: scripts
          configMap:
            name: weaviate-schema-init
```

Create `scripts/deploy-weaviate.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Deploying Weaviate ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
kubectl apply -f "${SCRIPT_DIR}/../infra/k8s/weaviate/"

echo "Waiting for Weaviate..."
kubectl wait --for=condition=Ready pod -l app=weaviate -n rag-system --timeout=180s

kubectl delete job weaviate-schema-init -n rag-system --ignore-not-found
kubectl apply -f "${SCRIPT_DIR}/../infra/k8s/weaviate/schema-init.yaml"
kubectl wait --for=condition=Complete job/weaviate-schema-init -n rag-system --timeout=120s

echo "✓ Weaviate deployed"
```

---

### Kafka (Message Queue)

Create `infra/k8s/kafka/kafka.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kafka
  namespace: rag-system
spec:
  ports:
    - port: 9092
      name: client
  selector:
    app: kafka
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
  namespace: rag-system
spec:
  serviceName: kafka
  replicas: 1
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      containers:
        - name: kafka
          image: bitnami/kafka:3.7
          ports:
            - containerPort: 9092
          env:
            - name: KAFKA_CFG_NODE_ID
              value: "0"
            - name: KAFKA_CFG_PROCESS_ROLES
              value: "controller,broker"
            - name: KAFKA_CFG_LISTENERS
              value: "PLAINTEXT://:9092,CONTROLLER://:9093"
            - name: KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP
              value: "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT"
            - name: KAFKA_CFG_CONTROLLER_QUORUM_VOTERS
              value: "0@kafka-0.kafka:9093"
            - name: KAFKA_CFG_CONTROLLER_LISTENER_NAMES
              value: "CONTROLLER"
            - name: KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE
              value: "true"
          volumeMounts:
            - name: data
              mountPath: /bitnami/kafka
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "2Gi"
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 8Gi
```

Create `scripts/deploy-kafka.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Deploying Kafka ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
kubectl apply -f "${SCRIPT_DIR}/../infra/k8s/kafka/"

echo "Waiting for Kafka..."
kubectl wait --for=condition=Ready pod -l app=kafka -n rag-system --timeout=180s

echo "✓ Kafka deployed"
```

---

### MinIO (Document Storage)

Create `infra/k8s/minio/minio.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: rag-system
spec:
  ports:
    - port: 9000
      name: api
    - port: 9001
      name: console
  selector:
    app: minio
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: minio
  namespace: rag-system
spec:
  serviceName: minio
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: minio/minio:latest
          args: ["server", "/data", "--console-address", ":9001"]
          ports:
            - containerPort: 9000
            - containerPort: 9001
          env:
            - name: MINIO_ROOT_USER
              value: "minioadmin"
            - name: MINIO_ROOT_PASSWORD
              value: "minioadmin123"
          volumeMounts:
            - name: data
              mountPath: /data
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "1Gi"
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

Create `scripts/deploy-minio.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Deploying MinIO ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
kubectl apply -f "${SCRIPT_DIR}/../infra/k8s/minio/"

echo "Waiting for MinIO..."
kubectl wait --for=condition=Ready pod -l app=minio -n rag-system --timeout=120s

echo "✓ MinIO deployed"
```

---

### Redis (Caching)

Create `infra/k8s/redis/redis.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: rag-system
spec:
  ports:
    - port: 6379
  selector:
    app: redis
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: rag-system
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          volumeMounts:
            - name: data
              mountPath: /data
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 2Gi
```

Create `scripts/deploy-redis.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Deploying Redis ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
kubectl apply -f "${SCRIPT_DIR}/../infra/k8s/redis/"

echo "Waiting for Redis..."
kubectl wait --for=condition=Ready pod -l app=redis -n rag-system --timeout=60s

echo "✓ Redis deployed"
```

---

### Prometheus & Grafana (Observability)

Create `infra/k8s/monitoring/prometheus.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: rag-system
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
      - job_name: 'search-api'
        static_configs:
          - targets: ['search-api:8080']
      - job_name: 'ingestion-api'
        static_configs:
          - targets: ['ingestion-api:8082']
      - job_name: 'embedding-service'
        static_configs:
          - targets: ['embedding-service:8083']
      - job_name: 'indexer'
        static_configs:
          - targets: ['indexer:8084']
      - job_name: 'prometheus'
        static_configs:
          - targets: ['localhost:9090']
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: rag-system
spec:
  type: NodePort
  ports:
    - port: 9090
      nodePort: 30090
  selector:
    app: prometheus
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: rag-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
        - name: prometheus
          image: prom/prometheus:v2.50.0
          args:
            - "--config.file=/etc/prometheus/prometheus.yml"
            - "--storage.tsdb.path=/prometheus"
          ports:
            - containerPort: 9090
          volumeMounts:
            - name: config
              mountPath: /etc/prometheus
            - name: data
              mountPath: /prometheus
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
      volumes:
        - name: config
          configMap:
            name: prometheus-config
        - name: data
          emptyDir: {}
```

Create `infra/k8s/monitoring/grafana.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: rag-system
spec:
  type: NodePort
  ports:
    - port: 3000
      nodePort: 30030
  selector:
    app: grafana
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: rag-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
        - name: grafana
          image: grafana/grafana:10.3.0
          ports:
            - containerPort: 3000
          env:
            - name: GF_SECURITY_ADMIN_PASSWORD
              value: "admin"
            - name: GF_AUTH_ANONYMOUS_ENABLED
              value: "true"
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
```

Create `scripts/deploy-monitoring.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Deploying Monitoring ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
kubectl apply -f "${SCRIPT_DIR}/../infra/k8s/monitoring/"

echo "Waiting for Prometheus..."
kubectl wait --for=condition=Ready pod -l app=prometheus -n rag-system --timeout=60s

echo "Waiting for Grafana..."
kubectl wait --for=condition=Ready pod -l app=grafana -n rag-system --timeout=60s

echo "✓ Monitoring deployed"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000 (admin/admin)"
```

---

## Application Scaffolding

### Directory Structure

```
rag-hackathon-starter/
├── Makefile
├── .env.example
├── pyproject.toml
├── README.md
│
├── data/
│   └── storage/                # Kind persistent volume mount
│
├── infra/
│   ├── kind/
│   │   └── cluster-config.yaml
│   ├── k8s/
│   │   ├── weaviate/
│   │   ├── kafka/
│   │   ├── minio/
│   │   ├── redis/
│   │   ├── monitoring/
│   │   ├── search-api/
│   │   ├── ingestion-api/
│   │   ├── embedding-service/
│   │   └── indexer/
│   └── docker/
│       ├── Dockerfile.search-api
│       ├── Dockerfile.ingestion-api
│       ├── Dockerfile.embedding-service
│       └── Dockerfile.indexer
│
├── scripts/
│   ├── setup-kind-cluster.sh
│   ├── deploy-weaviate.sh
│   ├── deploy-kafka.sh
│   ├── deploy-minio.sh
│   ├── deploy-redis.sh
│   ├── deploy-monitoring.sh
│   ├── deploy-all.sh
│   └── upload-sample-docs.py
│
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── interfaces.py       # ✅ All protocols
│   │   └── document.py         # ✅ CoreDocument
│   │
│   ├── retrievers/
│   │   ├── __init__.py
│   │   ├── weaviate.py         # ✅ Working (vector + BM25 + hybrid)
│   │   └── neo4j.py            # ⚡ STUB
│   │
│   ├── rerankers/
│   │   ├── __init__.py
│   │   ├── base.py             # ✅ Pass-through
│   │   ├── cross_encoder.py    # ⚡ STUB
│   │   └── llm_reranker.py     # ⚡ STUB
│   │
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── single_hop.py       # ✅ Working
│   │   ├── multi_hop.py        # ⚡ STUB
│   │   └── graph_augmented.py  # ⚡ STUB
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── openai.py           # ✅ Working
│   │
│   ├── cache/
│   │   ├── __init__.py
│   │   └── redis.py            # ✅ Working
│   │
│   ├── embedding_service/
│   │   ├── __init__.py
│   │   ├── main.py             # ✅ FastAPI app
│   │   ├── models.py           # ✅ Pydantic schemas
│   │   ├── config.py           # ✅ Configuration
│   │   └── backends/
│   │       ├── __init__.py
│   │       ├── base.py         # ✅ EmbeddingBackend protocol
│   │       ├── openai.py       # ✅ OpenAI embeddings
│   │       └── fasttext.py     # ⚡ STUB (local model)
│   │
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── main.py             # ✅ Entrypoint
│   │   ├── consumer.py         # ✅ Kafka consumer
│   │   └── chunker.py          # ✅ Basic chunking
│   │
│   ├── search_api/
│   │   ├── __init__.py
│   │   ├── main.py             # ✅ FastAPI app
│   │   ├── models.py           # ✅ Pydantic schemas
│   │   └── config.py           # ✅ Configuration
│   │
│   └── ingestion_api/
│       ├── __init__.py
│       ├── main.py             # ✅ FastAPI app
│       ├── models.py           # ✅ Pydantic schemas
│       └── config.py           # ✅ Configuration
│
├── tests/
│   ├── conftest.py
│   ├── test_retriever.py
│   ├── test_reranker.py
│   ├── test_embedding.py
│   └── test_e2e.py
│
└── docs/
    ├── QUICKSTART.md
    ├── ARCHITECTURE.md
    └── EXTENSION_GUIDE.md
```

### Domain Core (Interfaces)

Create `src/core/interfaces.py`:

```python
"""Core interfaces for the RAG platform."""

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Literal, Protocol, runtime_checkable
from .document import CoreDocument

SearchMode = Literal["vector", "bm25", "hybrid"]


@runtime_checkable
class Retriever(Protocol):
    """Protocol for document retrieval."""
    
    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        mode: SearchMode = "hybrid",
        namespace: str = "default",
    ) -> list[CoreDocument]:
        """Retrieve documents relevant to the query."""
        ...


@runtime_checkable
class GraphRetriever(Protocol):
    """Protocol for graph-based retrieval."""
    
    @abstractmethod
    def neighbors(
        self,
        doc_ids: list[str],
        top_k: int = 10,
        namespace: str = "default",
    ) -> list[CoreDocument]:
        """Find neighboring documents in the graph."""
        ...


@runtime_checkable
class Reranker(Protocol):
    """Protocol for document reranking."""
    
    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[CoreDocument],
        top_k: int | None = None,
    ) -> list[CoreDocument]:
        """Rerank documents by relevance."""
        ...


@runtime_checkable
class AnswerGenerator(Protocol):
    """Protocol for generating answers."""
    
    @abstractmethod
    def generate(
        self,
        query: str,
        documents: list[CoreDocument],
    ) -> str:
        """Generate an answer from documents."""
        ...


@runtime_checkable
class Cache(Protocol):
    """Protocol for caching."""
    
    @abstractmethod
    def get(self, key: str) -> Any | None:
        ...
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ...
```

Create `src/core/document.py`:

```python
"""Core document model."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CoreDocument:
    """Framework-agnostic document representation."""
    
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    
    @property
    def namespace(self) -> str:
        return self.metadata.get("namespace", "default")
    
    def with_score(self, score: float) -> "CoreDocument":
        return CoreDocument(
            id=self.id,
            content=self.content,
            metadata=self.metadata.copy(),
            score=score,
        )
```

---

## Sample Data Preparation

Create `scripts/upload-sample-docs.py`:

```python
#!/usr/bin/env python3
"""Upload sample documents for hackathon testing."""

import json
import os
from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")

SAMPLE_DOCS = [
    {
        "id": "wiki-ml-001",
        "title": "Machine Learning",
        "content": "Machine learning is a subset of artificial intelligence...",
        "namespace": "wiki",
        "source": "wikipedia"
    },
    {
        "id": "wiki-dl-001",
        "title": "Deep Learning",
        "content": "Deep learning is a type of machine learning based on...",
        "namespace": "wiki",
        "source": "wikipedia"
    },
    # Add more sample documents...
]

def main():
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode()
    )
    
    for doc in SAMPLE_DOCS:
        producer.send("document-changes", value=doc)
        print(f"Uploaded: {doc['id']}")
    
    producer.flush()
    print(f"✓ Uploaded {len(SAMPLE_DOCS)} documents")

if __name__ == "__main__":
    main()
```

---

## Developer Experience Setup

### Makefile

Create `Makefile`:

```makefile
.PHONY: help start stop reset dev test logs status

help:
	@echo "RAG Hackathon Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make cluster-start    - Create cluster and deploy services"
	@echo "  make cluster-stop     - Delete cluster"
	@echo "  make cluster-reset    - Delete and recreate everything"
	@echo ""
	@echo "Development:"
	@echo "  make dev-search    - Run Search API locally"
	@echo "  make dev-ingest    - Run Ingestion API locally"
	@echo "  make dev-embedding - Run Embedding Service locally"
	@echo "  make apps-build    - Build all Docker images"
	@echo "  make deploy        - Deploy applications to cluster"
	@echo ""
	@echo "Testing:"
	@echo "  make test     - Run all tests"
	@echo "  make test-e2e - Run end-to-end tests"
	@echo ""
	@echo "Data:"
	@echo "  make seed     - Upload sample documents"
	@echo ""
	@echo "Monitoring:"
	@echo "  make logs-search    - Tail Search API logs"
	@echo "  make logs-ingest    - Tail Ingestion API logs"
	@echo "  make logs-embedding - Tail Embedding Service logs"
	@echo "  make logs-indexer   - Tail Indexer logs"
	@echo "  make cluster-status         - Show cluster status"

start:
	@./scripts/setup-kind-cluster.sh
	@./scripts/deploy-all.sh
	@echo ""
	@echo "Ready! Run 'make seed' to upload sample data"

stop:
	kind delete cluster --name rag-hackathon || true

reset:
	$(MAKE) stop
	rm -rf ./data/storage/*
	$(MAKE) start

dev-search:
	cd src && uvicorn search_api.main:app --reload --port 8080

dev-ingest:
	cd src && uvicorn ingestion_api.main:app --reload --port 8082

dev-embedding:
	cd src && uvicorn embedding_service.main:app --reload --port 8083

build:
	docker build -t localhost:5000/search-api:latest -f infra/docker/Dockerfile.search-api .
	docker build -t localhost:5000/ingestion-api:latest -f infra/docker/Dockerfile.ingestion-api .
	docker build -t localhost:5000/embedding-service:latest -f infra/docker/Dockerfile.embedding-service .
	docker build -t localhost:5000/indexer:latest -f infra/docker/Dockerfile.indexer .
	docker push localhost:5000/search-api:latest
	docker push localhost:5000/ingestion-api:latest
	docker push localhost:5000/embedding-service:latest
	docker push localhost:5000/indexer:latest

deploy:
	kubectl apply -f infra/k8s/search-api/
	kubectl apply -f infra/k8s/ingestion-api/
	kubectl apply -f infra/k8s/embedding-service/
	kubectl apply -f infra/k8s/indexer/

test:
	pytest tests/ -v

test-e2e:
	pytest tests/test_e2e.py -v

seed:
	python scripts/upload-sample-docs.py

logs-search:
	kubectl logs -f -l app=search-api -n rag-system

logs-ingest:
	kubectl logs -f -l app=ingestion-api -n rag-system

logs-embedding:
	kubectl logs -f -l app=embedding-service -n rag-system

logs-indexer:
	kubectl logs -f -l app=indexer -n rag-system

status:
	@echo "=== Cluster ==="
	@kind get clusters
	@echo ""
	@echo "=== Pods ==="
	@kubectl get pods -n rag-system
```

### Environment Configuration

Create `.env.example`:

```bash
# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Services (K8s internal)
WEAVIATE_URL=http://weaviate:8080
KAFKA_BOOTSTRAP=kafka:9092
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
REDIS_URL=redis://redis:6379

# API
LOG_LEVEL=INFO
```

---

## Testing Infrastructure

Create `tests/conftest.py`:

```python
import pytest
from src.core.document import CoreDocument


@pytest.fixture
def sample_documents():
    return [
        CoreDocument(id="1", content="Machine learning basics", metadata={"namespace": "wiki"}),
        CoreDocument(id="2", content="Deep learning neural networks", metadata={"namespace": "wiki"}),
        CoreDocument(id="3", content="Natural language processing", metadata={"namespace": "wiki"}),
    ]


@pytest.fixture
def test_query():
    return "What is machine learning?"
```

Create `tests/test_retriever.py`:

```python
import pytest
from src.core.interfaces import Retriever
from src.retrievers.weaviate import WeaviateRetriever


class TestWeaviateRetriever:
    def test_implements_protocol(self):
        assert issubclass(WeaviateRetriever, Retriever)
    
    @pytest.mark.integration
    def test_retrieve(self, test_query):
        retriever = WeaviateRetriever()
        results = retriever.retrieve(test_query, top_k=5)
        assert len(results) <= 5
```

---

## Documentation for Participants

### QUICKSTART.md

Create `docs/QUICKSTART.md`:

```markdown
# RAG Hackathon Quickstart

## Setup (3 minutes)

```bash
git clone https://github.com/your-org/rag-hackathon-starter
cd rag-hackathon-starter
cp .env.example .env
# Add your OPENAI_API_KEY to .env
make cluster-start
make seed
```

## Test It

```bash
# Search for documents
curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is machine learning?", "namespace": "wiki"}'

# Ingest a new document
curl -X POST http://localhost:8082/ingest \
  -H "Content-Type: application/json" \
  -d '{"title": "My Doc", "content": "...", "namespace": "wiki"}'
```

## Challenge Tracks

1. **Reranking** (Beginner): `src/rerankers/cross_encoder.py`
2. **Lexical Search** (Intermediate): `src/retrievers/opensearch.py`
3. **Multi-Hop** (Intermediate): `src/orchestration/multi_hop.py`
4. **Graph RAG** (Advanced): `src/retrievers/neo4j.py`

## Commands

| Command | Description |
|---------|-------------|
| `make cluster-start` | Start cluster |
| `make cluster-stop` | Stop cluster |
| `make dev-search` | Run Search API locally |
| `make dev-ingest` | Run Ingestion API locally |
| `make test` | Run tests |
| `make logs-search` | View Search API logs |
| `make cluster-status` | Check pods |
```

---

## Troubleshooting Guide

| Issue | Symptom | Solution |
|-------|---------|----------|
| Docker memory | OOM kills | Increase Docker to 8GB+ |
| Port conflict | "Port in use" | `make cluster-stop` then `make cluster-start` |
| Weaviate not ready | Connection refused | Wait 60-90s |
| Pods stuck | Pending status | Check `kubectl describe pod` |

### Diagnostic Commands

```bash
# Check pods
kubectl get pods -n rag-system

# Check logs
kubectl logs -l app=weaviate -n rag-system

# Check events
kubectl get events -n rag-system --sort-by='.lastTimestamp'

# Test Weaviate
curl http://localhost:8081/v1/.well-known/ready

# Test Redis
kubectl exec -it redis-0 -n rag-system -- redis-cli ping
```

---

## Day-of Checklist

### Before Participants Arrive

- [ ] `git clone` + `make cluster-start` tested on fresh machine
- [ ] Sample searches return results
- [ ] Grafana loads at http://localhost:3000
- [ ] Mentor assignments ready

### First 30 Minutes

- [ ] Share repository link
- [ ] Walk through QUICKSTART.md
- [ ] Mentors circulating for setup issues
- [ ] Verify one team per table has working setup

---

## Full Deployment Script

Create `scripts/deploy-all.sh`:

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo "  Deploying All Services"
echo "=============================================="

"${SCRIPT_DIR}/deploy-redis.sh"
"${SCRIPT_DIR}/deploy-minio.sh"
"${SCRIPT_DIR}/deploy-kafka.sh"
"${SCRIPT_DIR}/deploy-weaviate.sh"
"${SCRIPT_DIR}/deploy-monitoring.sh"

echo ""
echo "=============================================="
echo "  All Services Deployed!"
echo "=============================================="
echo ""
echo "  Search API:    http://localhost:8080 (after app deploy)"
echo "  Ingestion API: http://localhost:8082 (after app deploy)"
echo "  Weaviate:      http://localhost:8081"
echo "  Grafana:       http://localhost:3000 (admin/admin)"
echo "  Prometheus:    http://localhost:9090"
echo ""
```

Make all scripts executable:

```bash
chmod +x scripts/*.sh
```

---

## Summary

This setup guide provides a focused RAG platform development environment:

1. **Kind cluster** with local registry and port mappings
2. **Core services**: Weaviate, Kafka, MinIO, Redis
3. **Basic observability**: Prometheus + Grafana
4. **Clean interfaces** for participants to extend
5. **Simple Makefile** for common operations

**Organizer setup time**: ~2-3 hours
**Participant startup time**: ~3 minutes
