# ⚠️ ARCHIVED DOCUMENT

> **This document is archived and no longer maintained.**
>
> This was the original hackathon setup guide. For current documentation, see:
> - [QUICKSTART.md](../QUICKSTART.md) - Quick start guide
> - [SYSTEM-DIAGRAM.md](../SYSTEM-DIAGRAM.md) - Architecture diagram
> - [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - Common issues
> - [README.md](../../README.md) - Main project documentation

---

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

*[Rest of original content preserved for historical reference]*
