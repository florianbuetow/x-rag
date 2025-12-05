# RAG Test Harness Implementation Guide

A comprehensive guide for implementing a retrieval evaluation test harness that reuses production components with configurable hyperparameters.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Production Code Requirements](#production-code-requirements)
4. [Configuration System](#configuration-system)
5. [Core Abstractions](#core-abstractions)
6. [Component Implementations](#component-implementations)
7. [Test Harness Implementation](#test-harness-implementation)
8. [Weaviate Setup](#weaviate-setup)
9. [Docker Environment](#docker-environment)
10. [Evaluation Datasets](#evaluation-datasets)
11. [Metrics](#metrics)
12. [Running Evaluations](#running-evaluations)
13. [CI/CD Integration](#cicd-integration)
14. [Regression Detection](#regression-detection)

---

## Overview

### Purpose

This test harness measures retrieval quality of a RAG system using programmatic metrics that require no human feedback or LLM-as-judge evaluation. It enables:

- Baseline establishment for retrieval performance
- Regression detection when changing embedding models, chunking strategies, or search parameters
- Comparison of different configurations (A/B testing offline)
- Reproducible evaluation runs with full configuration tracking

### Core Metrics

The harness computes these retrieval metrics:

| Metric | Description |
|--------|-------------|
| **Recall@K** | Of the relevant chunks, how many appear in top K results? |
| **Precision@K** | Of the K chunks returned, how many are relevant? |
| **Hit Rate@K** | Binary: did any relevant chunk appear in top K? |
| **MRR** | Mean Reciprocal Rank: where does the first relevant chunk appear? |
| **NDCG@K** | Normalized Discounted Cumulative Gain: ranking quality with position weighting |

### Scope

**In Scope:**
- Retrieval quality metrics (programmatic, no LLM required)
- Reranker evaluation
- Configuration comparison
- Offline execution in Docker
- Local Weaviate for reproducible testing

**Out of Scope (for now):**
- LLM-as-judge metrics (faithfulness, answer relevance, groundedness)
- Human feedback collection
- End-to-end generation quality
- Production logging infrastructure

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Test Harness                                │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   Dataset   │  │  Evaluator  │  │   Metrics   │  │  Reports   │ │
│  │   Loader    │  │             │  │  Computer   │  │  Writer    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ uses
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Production Components                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  Document   │  │   Chunker   │  │  Embedding  │  │   Index    │ │
│  │   Loader    │  │             │  │   Client    │  │   Client   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Indexer   │  │  Retriever  │  │  Reranker   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ configured by
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Configuration System                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  Chunking   │  │  Embedding  │  │  Retrieval  │  │  Reranker  │ │
│  │   Config    │  │   Config    │  │   Config    │  │   Config   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Production Code Requirements

These requirements must be met by the production code before implementing the test harness. The team should adjust existing code to conform to these specifications.

### Requirement 1: Pure Core Logic

Each component must separate its core logic from side effects (logging, HTTP handling, caching).

**Required Pattern:**
```
# Core function: input → output, no side effects
def retrieve(query: str, config: RetrievalConfig) -> RetrievalResult:
    ...

# Wrapper adds logging, caching, etc.
def retrieve_with_logging(query: str, config: RetrievalConfig) -> RetrievalResult:
    result = retrieve(query, config)
    logger.info(...)
    return result
```

**Anti-Pattern:**
```
# Don't embed logging inside core logic
def retrieve(query: str, config: RetrievalConfig) -> RetrievalResult:
    logger.info("Starting retrieval...")  # BAD: side effect in core
    ...
```

### Requirement 2: Explicit Return Types

All components must return structured dataclasses, not raw dicts or API responses.

**Required:**
```python
@dataclass
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk]
    latency_ms: float
    config: RetrievalConfig
```

**Not Acceptable:**
```python
def retrieve(query: str) -> dict:  # BAD: untyped
    return {"results": [...], "meta": {...}}
```

### Requirement 3: Injectable Dependencies

Components must accept dependencies via constructor, not instantiate them internally.

**Required:**
```python
class Retriever:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        index_client: IndexClient,
        config: RetrievalConfig,
    ):
        self.embedding_client = embedding_client
        self.index_client = index_client
        self.config = config
```

**Not Acceptable:**
```python
class Retriever:
    def __init__(self):
        self.embedding_client = OpenAIEmbeddings()  # BAD: hardcoded
        self.index_client = WeaviateClient(os.environ["WEAVIATE_URL"])  # BAD
```

### Requirement 4: Configuration Objects

All hyperparameters must be encapsulated in serializable, immutable configuration objects.

**Required:**
```python
@dataclass(frozen=True)
class ChunkingConfig:
    strategy: str
    chunk_size: int
    chunk_overlap: int
```

**Not Acceptable:**
```python
def chunk_document(doc, size=512, overlap=50):  # BAD: magic defaults
    ...

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 512))  # BAD: env var inside logic
```

### Requirement 5: Deterministic Chunk IDs

Chunk IDs must be reproducible given the same document and configuration.

**Acceptable Patterns:**
```python
# Sequential (deterministic if chunking is deterministic)
chunk_id = f"{doc_id}-chunk-{index}"

# Content-based hash
chunk_id = f"{doc_id}-{hashlib.md5(content.encode()).hexdigest()[:8]}"
```

**Not Acceptable:**
```python
chunk_id = str(uuid.uuid4())  # BAD: random
chunk_id = f"{doc_id}-{time.time()}"  # BAD: non-reproducible
```

### Requirement 6: Stateless Query Handling

Each call to retrieval/reranking must be independent with no hidden state.

**Required:**
```python
# Each call is independent
result1 = retriever.retrieve("query 1")
result2 = retriever.retrieve("query 2")  # Not affected by result1
```

**Not Acceptable:**
```python
class Retriever:
    def retrieve(self, query: str):
        self.last_query = query  # BAD: stateful
        if self.cache.get(query):  # BAD: hidden cache affecting results
            ...
```

### Requirement 7: Abstract Interfaces

Define abstract base classes for all swappable components.

```python
from abc import ABC, abstractmethod

class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        pass

class IndexClient(ABC):
    @abstractmethod
    def create_collection(self, name: str, config: CollectionConfig) -> None:
        pass

    @abstractmethod
    def insert_batch(self, collection: str, chunks: list[IndexedChunk]) -> None:
        pass

    @abstractmethod
    def search(self, collection: str, vector: list[float], top_k: int) -> list[SearchResult]:
        pass
```

### Requirement 8: Separation of Indexing and Querying

The indexing pipeline and query pipeline must be separate components.

```
Indexer: documents → chunks → vectors → index
Retriever: query → vector → search → results
```

These share configuration and clients but are instantiated independently.

---

## Configuration System

### Configuration Hierarchy

```python
from dataclasses import dataclass, field
from typing import Literal
import json

@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for document chunking."""
    strategy: Literal["fixed", "sentence", "semantic"] = "fixed"
    chunk_size: int = 512
    chunk_overlap: int = 50
    
    # Strategy-specific options
    sentence_max_sentences: int | None = None
    semantic_similarity_threshold: float | None = None


@dataclass(frozen=True)
class EmbeddingConfig:
    """Configuration for embedding generation."""
    provider: Literal["openai", "cohere", "local"] = "openai"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 100
    
    # Provider-specific options
    api_base: str | None = None


@dataclass(frozen=True)
class IndexConfig:
    """Configuration for vector index."""
    provider: Literal["weaviate", "pinecone", "qdrant"] = "weaviate"
    collection_name: str = "documents"
    distance_metric: Literal["cosine", "l2", "dot"] = "cosine"
    
    # Weaviate-specific
    weaviate_url: str | None = None
    weaviate_api_key: str | None = None
    weaviate_embedded: bool = False


@dataclass(frozen=True)
class RetrievalConfig:
    """Configuration for retrieval."""
    top_k: int = 10
    similarity_threshold: float | None = None
    use_hybrid_search: bool = False
    hybrid_alpha: float = 0.5  # Balance between vector and keyword search


@dataclass(frozen=True)
class RerankerConfig:
    """Configuration for reranking."""
    enabled: bool = False
    provider: Literal["cohere", "cross-encoder", "none"] = "none"
    model: str | None = None
    top_k: int = 5  # Final number of results after reranking


@dataclass(frozen=True)
class RAGConfig:
    """Complete RAG pipeline configuration."""
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        import dataclasses
        return dataclasses.asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "RAGConfig":
        """Deserialize from dictionary."""
        return cls(
            chunking=ChunkingConfig(**data.get("chunking", {})),
            embedding=EmbeddingConfig(**data.get("embedding", {})),
            index=IndexConfig(**data.get("index", {})),
            retrieval=RetrievalConfig(**data.get("retrieval", {})),
            reranker=RerankerConfig(**data.get("reranker", {})),
        )
    
    @classmethod
    def from_yaml(cls, path: str) -> "RAGConfig":
        """Load from YAML file."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def to_yaml(self, path: str) -> None:
        """Save to YAML file."""
        import yaml
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
```

### Example Configuration File

```yaml
# config/eval_baseline.yaml
chunking:
  strategy: fixed
  chunk_size: 512
  chunk_overlap: 50

embedding:
  provider: openai
  model: text-embedding-3-small
  dimensions: 1536
  batch_size: 100

index:
  provider: weaviate
  collection_name: eval_documents
  distance_metric: cosine
  weaviate_embedded: true  # Use embedded Weaviate for testing

retrieval:
  top_k: 10
  similarity_threshold: null
  use_hybrid_search: false

reranker:
  enabled: false
  provider: none
```

---

## Core Abstractions

### Data Types

```python
# rag/types.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Document:
    """A source document to be indexed."""
    doc_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.doc_id:
            raise ValueError("doc_id cannot be empty")


@dataclass
class Chunk:
    """A chunk of a document after splitting."""
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Position information
    start_char: int | None = None
    end_char: int | None = None
    chunk_index: int | None = None


@dataclass
class IndexedChunk:
    """A chunk with its embedding, ready for indexing."""
    chunk_id: str
    doc_id: str
    content: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """A chunk returned from search."""
    chunk_id: str
    score: float
    content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Complete result of a retrieval operation."""
    query: str
    chunks: list[RetrievedChunk]
    latency_ms: float
    config_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexResult:
    """Result of an indexing operation."""
    num_documents: int
    num_chunks: int
    collection_name: str
    duration_seconds: float
    config_snapshot: dict[str, Any] = field(default_factory=dict)
```

### Abstract Interfaces

```python
# rag/interfaces.py
from abc import ABC, abstractmethod
from typing import Iterator
from rag.types import Document, Chunk, IndexedChunk, RetrievedChunk
from rag.config import ChunkingConfig, EmbeddingConfig

class DocumentLoader(ABC):
    """Abstract interface for loading documents."""
    
    @abstractmethod
    def load(self) -> Iterator[Document]:
        """Yield documents from the source."""
        pass


class Chunker(ABC):
    """Abstract interface for document chunking."""
    
    @abstractmethod
    def chunk(self, document: Document) -> list[Chunk]:
        """Split a document into chunks."""
        pass
    
    @property
    @abstractmethod
    def config(self) -> ChunkingConfig:
        """Return the chunking configuration."""
        pass


class EmbeddingClient(ABC):
    """Abstract interface for embedding generation."""
    
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @property
    @abstractmethod
    def config(self) -> EmbeddingConfig:
        """Return the embedding configuration."""
        pass


class IndexClient(ABC):
    """Abstract interface for vector index operations."""
    
    @abstractmethod
    def create_collection(
        self, 
        name: str, 
        dimensions: int,
        distance_metric: str,
        drop_if_exists: bool = False,
    ) -> None:
        """Create a new collection."""
        pass
    
    @abstractmethod
    def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        pass
    
    @abstractmethod
    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists."""
        pass
    
    @abstractmethod
    def insert_batch(self, collection: str, chunks: list[IndexedChunk]) -> int:
        """Insert a batch of chunks. Returns number inserted."""
        pass
    
    @abstractmethod
    def search(
        self, 
        collection: str, 
        vector: list[float], 
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    def hybrid_search(
        self,
        collection: str,
        vector: list[float],
        query_text: str,
        top_k: int,
        alpha: float,
    ) -> list[RetrievedChunk]:
        """Hybrid search combining vector and keyword search."""
        pass


class Reranker(ABC):
    """Abstract interface for reranking results."""
    
    @abstractmethod
    def rerank(
        self, 
        query: str, 
        chunks: list[RetrievedChunk], 
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Rerank chunks by relevance to query."""
        pass
```

---

## Component Implementations

### Document Loaders

```python
# rag/loaders.py
from pathlib import Path
from typing import Iterator
import json
from rag.interfaces import DocumentLoader
from rag.types import Document

class FileSystemLoader(DocumentLoader):
    """Load documents from a directory."""
    
    def __init__(
        self, 
        path: Path, 
        glob_pattern: str = "**/*.txt",
        encoding: str = "utf-8",
    ):
        self.path = Path(path)
        self.glob_pattern = glob_pattern
        self.encoding = encoding
    
    def load(self) -> Iterator[Document]:
        for file_path in self.path.glob(self.glob_pattern):
            if file_path.is_file():
                content = file_path.read_text(encoding=self.encoding)
                doc_id = str(file_path.relative_to(self.path))
                yield Document(
                    doc_id=doc_id,
                    content=content,
                    metadata={
                        "source_path": str(file_path),
                        "filename": file_path.name,
                    },
                )


class JSONLoader(DocumentLoader):
    """Load documents from a JSON file."""
    
    def __init__(self, path: Path):
        self.path = Path(path)
    
    def load(self) -> Iterator[Document]:
        with open(self.path) as f:
            data = json.load(f)
        
        for item in data:
            yield Document(
                doc_id=item["doc_id"],
                content=item["content"],
                metadata=item.get("metadata", {}),
            )


class InMemoryLoader(DocumentLoader):
    """Load documents from an in-memory list. Useful for testing."""
    
    def __init__(self, documents: list[Document]):
        self.documents = documents
    
    def load(self) -> Iterator[Document]:
        yield from self.documents
```

### Chunkers

```python
# rag/chunkers.py
import hashlib
from rag.interfaces import Chunker
from rag.types import Document, Chunk
from rag.config import ChunkingConfig

class FixedSizeChunker(Chunker):
    """Split documents into fixed-size chunks with overlap."""
    
    def __init__(self, config: ChunkingConfig):
        if config.strategy != "fixed":
            raise ValueError(f"Expected 'fixed' strategy, got '{config.strategy}'")
        self._config = config
    
    @property
    def config(self) -> ChunkingConfig:
        return self._config
    
    def chunk(self, document: Document) -> list[Chunk]:
        chunks = []
        content = document.content
        chunk_size = self._config.chunk_size
        overlap = self._config.chunk_overlap
        
        start = 0
        chunk_index = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk_content = content[start:end]
            
            # Deterministic chunk ID based on document and position
            chunk_id = f"{document.doc_id}-chunk-{chunk_index}"
            
            chunks.append(Chunk(
                chunk_id=chunk_id,
                doc_id=document.doc_id,
                content=chunk_content,
                metadata={**document.metadata},
                start_char=start,
                end_char=end,
                chunk_index=chunk_index,
            ))
            
            start += chunk_size - overlap
            chunk_index += 1
        
        return chunks


class SentenceChunker(Chunker):
    """Split documents by sentences with configurable grouping."""
    
    def __init__(self, config: ChunkingConfig):
        if config.strategy != "sentence":
            raise ValueError(f"Expected 'sentence' strategy, got '{config.strategy}'")
        self._config = config
        
        # Lazy import for optional dependency
        try:
            import nltk
            nltk.download('punkt', quiet=True)
            self._sent_tokenize = nltk.sent_tokenize
        except ImportError:
            raise ImportError("nltk is required for SentenceChunker")
    
    @property
    def config(self) -> ChunkingConfig:
        return self._config
    
    def chunk(self, document: Document) -> list[Chunk]:
        sentences = self._sent_tokenize(document.content)
        max_sentences = self._config.sentence_max_sentences or 5
        overlap_sentences = self._config.chunk_overlap  # Reuse as sentence count
        
        chunks = []
        chunk_index = 0
        i = 0
        
        while i < len(sentences):
            chunk_sentences = sentences[i:i + max_sentences]
            chunk_content = " ".join(chunk_sentences)
            
            chunk_id = f"{document.doc_id}-chunk-{chunk_index}"
            
            chunks.append(Chunk(
                chunk_id=chunk_id,
                doc_id=document.doc_id,
                content=chunk_content,
                metadata={
                    **document.metadata,
                    "sentence_start": i,
                    "sentence_end": i + len(chunk_sentences),
                },
                chunk_index=chunk_index,
            ))
            
            i += max_sentences - overlap_sentences
            chunk_index += 1
        
        return chunks


def create_chunker(config: ChunkingConfig) -> Chunker:
    """Factory function to create the appropriate chunker."""
    if config.strategy == "fixed":
        return FixedSizeChunker(config)
    elif config.strategy == "sentence":
        return SentenceChunker(config)
    else:
        raise ValueError(f"Unknown chunking strategy: {config.strategy}")
```

### Embedding Clients

```python
# rag/embeddings.py
from pathlib import Path
import json
import hashlib
from rag.interfaces import EmbeddingClient
from rag.config import EmbeddingConfig

class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI embedding client."""
    
    def __init__(self, config: EmbeddingConfig, api_key: str | None = None):
        if config.provider != "openai":
            raise ValueError(f"Expected 'openai' provider, got '{config.provider}'")
        self._config = config
        
        import openai
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=config.api_base,
        )
    
    @property
    def config(self) -> EmbeddingConfig:
        return self._config
    
    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=self._config.model,
            input=text,
        )
        return response.data[0].embedding
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        batch_size = self._config.batch_size
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self._client.embeddings.create(
                model=self._config.model,
                input=batch,
            )
            embeddings.extend([d.embedding for d in response.data])
        
        return embeddings


class CachedEmbeddingClient(EmbeddingClient):
    """Wrapper that caches embeddings to disk. Useful for repeated test runs."""
    
    def __init__(self, delegate: EmbeddingClient, cache_dir: Path):
        self._delegate = delegate
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self._cache_dir / f"embeddings_{self._config.model}.json"
        self._cache = self._load_cache()
    
    @property
    def config(self) -> EmbeddingConfig:
        return self._delegate.config
    
    @property
    def _config(self) -> EmbeddingConfig:
        return self._delegate.config
    
    def _load_cache(self) -> dict[str, list[float]]:
        if self._cache_file.exists():
            with open(self._cache_file) as f:
                return json.load(f)
        return {}
    
    def _save_cache(self) -> None:
        with open(self._cache_file, "w") as f:
            json.dump(self._cache, f)
    
    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
    
    def embed(self, text: str) -> list[float]:
        key = self._cache_key(text)
        if key not in self._cache:
            self._cache[key] = self._delegate.embed(text)
            self._save_cache()
        return self._cache[key]
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append(None)  # Placeholder
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        if uncached_texts:
            new_embeddings = self._delegate.embed_batch(uncached_texts)
            for idx, text, embedding in zip(uncached_indices, uncached_texts, new_embeddings):
                key = self._cache_key(text)
                self._cache[key] = embedding
                results[idx] = embedding
            self._save_cache()
        
        return results


def create_embedding_client(
    config: EmbeddingConfig, 
    api_key: str | None = None,
    cache_dir: Path | None = None,
) -> EmbeddingClient:
    """Factory function to create the appropriate embedding client."""
    if config.provider == "openai":
        client = OpenAIEmbeddingClient(config, api_key)
    else:
        raise ValueError(f"Unknown embedding provider: {config.provider}")
    
    if cache_dir:
        client = CachedEmbeddingClient(client, cache_dir)
    
    return client
```

### Weaviate Index Client

```python
# rag/index_clients/weaviate_client.py
import weaviate
from weaviate.embedded import EmbeddedOptions
from rag.interfaces import IndexClient
from rag.types import IndexedChunk, RetrievedChunk
from rag.config import IndexConfig

class WeaviateIndexClient(IndexClient):
    """Weaviate implementation of IndexClient."""
    
    def __init__(self, client: weaviate.Client, config: IndexConfig):
        self._client = client
        self._config = config
    
    @classmethod
    def from_config(cls, config: IndexConfig) -> "WeaviateIndexClient":
        """Create client from configuration."""
        if config.weaviate_embedded:
            client = weaviate.Client(embedded_options=EmbeddedOptions())
        else:
            auth = None
            if config.weaviate_api_key:
                auth = weaviate.AuthApiKey(config.weaviate_api_key)
            client = weaviate.Client(
                url=config.weaviate_url,
                auth_client_secret=auth,
            )
        return cls(client, config)
    
    @classmethod
    def embedded(cls, config: IndexConfig | None = None) -> "WeaviateIndexClient":
        """Create an embedded Weaviate client for testing."""
        config = config or IndexConfig(weaviate_embedded=True)
        client = weaviate.Client(embedded_options=EmbeddedOptions())
        return cls(client, config)
    
    def create_collection(
        self,
        name: str,
        dimensions: int,
        distance_metric: str,
        drop_if_exists: bool = False,
    ) -> None:
        if drop_if_exists and self.collection_exists(name):
            self.delete_collection(name)
        
        # Map distance metric to Weaviate format
        distance_map = {
            "cosine": "cosine",
            "l2": "l2-squared",
            "dot": "dot",
        }
        
        class_obj = {
            "class": name,
            "vectorizer": "none",  # We provide our own vectors
            "vectorIndexConfig": {
                "distance": distance_map.get(distance_metric, "cosine"),
            },
            "properties": [
                {"name": "chunk_id", "dataType": ["text"]},
                {"name": "doc_id", "dataType": ["text"]},
                {"name": "content", "dataType": ["text"]},
                {"name": "metadata", "dataType": ["text"]},  # JSON string
            ],
        }
        
        self._client.schema.create_class(class_obj)
    
    def delete_collection(self, name: str) -> None:
        self._client.schema.delete_class(name)
    
    def collection_exists(self, name: str) -> bool:
        try:
            self._client.schema.get(name)
            return True
        except weaviate.exceptions.UnexpectedStatusCodeException:
            return False
    
    def insert_batch(self, collection: str, chunks: list[IndexedChunk]) -> int:
        import json
        
        with self._client.batch as batch:
            for chunk in chunks:
                properties = {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "content": chunk.content,
                    "metadata": json.dumps(chunk.metadata),
                }
                batch.add_data_object(
                    data_object=properties,
                    class_name=collection,
                    vector=chunk.vector,
                )
        
        return len(chunks)
    
    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        import json
        
        response = (
            self._client.query
            .get(collection, ["chunk_id", "doc_id", "content", "metadata"])
            .with_near_vector({"vector": vector})
            .with_limit(top_k)
            .with_additional(["distance", "id"])
            .do()
        )
        
        results = response.get("data", {}).get("Get", {}).get(collection, [])
        
        return [
            RetrievedChunk(
                chunk_id=r["chunk_id"],
                score=1 - r["_additional"]["distance"],  # Convert distance to similarity
                content=r.get("content"),
                metadata=json.loads(r.get("metadata", "{}")),
            )
            for r in results
        ]
    
    def hybrid_search(
        self,
        collection: str,
        vector: list[float],
        query_text: str,
        top_k: int,
        alpha: float,
    ) -> list[RetrievedChunk]:
        import json
        
        response = (
            self._client.query
            .get(collection, ["chunk_id", "doc_id", "content", "metadata"])
            .with_hybrid(
                query=query_text,
                vector=vector,
                alpha=alpha,
            )
            .with_limit(top_k)
            .with_additional(["score"])
            .do()
        )
        
        results = response.get("data", {}).get("Get", {}).get(collection, [])
        
        return [
            RetrievedChunk(
                chunk_id=r["chunk_id"],
                score=r["_additional"]["score"],
                content=r.get("content"),
                metadata=json.loads(r.get("metadata", "{}")),
            )
            for r in results
        ]
    
    def close(self) -> None:
        """Close the client connection."""
        pass  # Weaviate client doesn't require explicit closing
```

### Rerankers

```python
# rag/rerankers.py
from rag.interfaces import Reranker
from rag.types import RetrievedChunk
from rag.config import RerankerConfig

class CohereReranker(Reranker):
    """Cohere reranker implementation."""
    
    def __init__(self, config: RerankerConfig, api_key: str | None = None):
        self._config = config
        
        import cohere
        self._client = cohere.Client(api_key)
    
    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        
        documents = [c.content or "" for c in chunks]
        
        response = self._client.rerank(
            model=self._config.model or "rerank-english-v2.0",
            query=query,
            documents=documents,
            top_n=top_k,
        )
        
        reranked = []
        for result in response.results:
            original_chunk = chunks[result.index]
            reranked.append(RetrievedChunk(
                chunk_id=original_chunk.chunk_id,
                score=result.relevance_score,
                content=original_chunk.content,
                metadata=original_chunk.metadata,
            ))
        
        return reranked


class NoOpReranker(Reranker):
    """Pass-through reranker that returns top_k results unchanged."""
    
    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        return chunks[:top_k]


def create_reranker(config: RerankerConfig, api_key: str | None = None) -> Reranker:
    """Factory function to create the appropriate reranker."""
    if not config.enabled or config.provider == "none":
        return NoOpReranker()
    elif config.provider == "cohere":
        return CohereReranker(config, api_key)
    else:
        raise ValueError(f"Unknown reranker provider: {config.provider}")
```

### Indexer

```python
# rag/indexer.py
import time
from typing import Callable
from rag.interfaces import DocumentLoader, Chunker, EmbeddingClient, IndexClient
from rag.types import Document, Chunk, IndexedChunk, IndexResult
from rag.config import RAGConfig

class Indexer:
    """Indexes documents into a vector store."""
    
    def __init__(
        self,
        document_loader: DocumentLoader,
        chunker: Chunker,
        embedding_client: EmbeddingClient,
        index_client: IndexClient,
        config: RAGConfig,
    ):
        self.document_loader = document_loader
        self.chunker = chunker
        self.embedding_client = embedding_client
        self.index_client = index_client
        self.config = config
    
    def index(
        self,
        drop_if_exists: bool = True,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> IndexResult:
        """
        Index all documents from the loader.
        
        Args:
            drop_if_exists: Whether to drop existing collection
            on_progress: Callback for progress updates (stage, current, total)
        
        Returns:
            IndexResult with statistics
        """
        start_time = time.time()
        collection_name = self.config.index.collection_name
        
        # Create collection
        self.index_client.create_collection(
            name=collection_name,
            dimensions=self.config.embedding.dimensions,
            distance_metric=self.config.index.distance_metric,
            drop_if_exists=drop_if_exists,
        )
        
        # Load and chunk documents
        documents = list(self.document_loader.load())
        if on_progress:
            on_progress("loading", len(documents), len(documents))
        
        all_chunks: list[Chunk] = []
        for i, doc in enumerate(documents):
            chunks = self.chunker.chunk(doc)
            all_chunks.extend(chunks)
            if on_progress:
                on_progress("chunking", i + 1, len(documents))
        
        # Generate embeddings
        chunk_contents = [c.content for c in all_chunks]
        embeddings = self.embedding_client.embed_batch(chunk_contents)
        if on_progress:
            on_progress("embedding", len(embeddings), len(embeddings))
        
        # Create indexed chunks
        indexed_chunks = [
            IndexedChunk(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                content=chunk.content,
                vector=vector,
                metadata=chunk.metadata,
            )
            for chunk, vector in zip(all_chunks, embeddings)
        ]
        
        # Insert into index
        batch_size = 100
        for i in range(0, len(indexed_chunks), batch_size):
            batch = indexed_chunks[i:i + batch_size]
            self.index_client.insert_batch(collection_name, batch)
            if on_progress:
                on_progress("indexing", min(i + batch_size, len(indexed_chunks)), len(indexed_chunks))
        
        duration = time.time() - start_time
        
        return IndexResult(
            num_documents=len(documents),
            num_chunks=len(all_chunks),
            collection_name=collection_name,
            duration_seconds=duration,
            config_snapshot=self.config.to_dict(),
        )
```

### Retriever

```python
# rag/retriever.py
import time
from rag.interfaces import EmbeddingClient, IndexClient, Reranker
from rag.types import RetrievalResult, RetrievedChunk
from rag.config import RAGConfig

class Retriever:
    """Retrieves relevant chunks for a query."""
    
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        index_client: IndexClient,
        reranker: Reranker,
        config: RAGConfig,
    ):
        self.embedding_client = embedding_client
        self.index_client = index_client
        self.reranker = reranker
        self.config = config
    
    def retrieve(self, query: str) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: The search query
        
        Returns:
            RetrievalResult with ranked chunks
        """
        start_time = time.time()
        
        # Generate query embedding
        query_vector = self.embedding_client.embed(query)
        
        # Search
        collection_name = self.config.index.collection_name
        retrieval_config = self.config.retrieval
        
        if retrieval_config.use_hybrid_search:
            chunks = self.index_client.hybrid_search(
                collection=collection_name,
                vector=query_vector,
                query_text=query,
                top_k=retrieval_config.top_k,
                alpha=retrieval_config.hybrid_alpha,
            )
        else:
            chunks = self.index_client.search(
                collection=collection_name,
                vector=query_vector,
                top_k=retrieval_config.top_k,
            )
        
        # Apply similarity threshold if configured
        if retrieval_config.similarity_threshold:
            chunks = [
                c for c in chunks 
                if c.score >= retrieval_config.similarity_threshold
            ]
        
        # Rerank if enabled
        if self.config.reranker.enabled:
            chunks = self.reranker.rerank(
                query=query,
                chunks=chunks,
                top_k=self.config.reranker.top_k,
            )
        
        latency_ms = (time.time() - start_time) * 1000
        
        return RetrievalResult(
            query=query,
            chunks=chunks,
            latency_ms=latency_ms,
            config_snapshot=self.config.to_dict(),
        )
```

---

## Test Harness Implementation

### Directory Structure

```
project_root/
├── rag/                          # Production code
│   ├── __init__.py
│   ├── config.py                 # Configuration classes
│   ├── types.py                  # Data types
│   ├── interfaces.py             # Abstract interfaces
│   ├── loaders.py                # Document loaders
│   ├── chunkers.py               # Chunking strategies
│   ├── embeddings.py             # Embedding clients
│   ├── rerankers.py              # Reranker implementations
│   ├── indexer.py                # Indexing pipeline
│   ├── retriever.py              # Retrieval pipeline
│   └── index_clients/
│       ├── __init__.py
│       └── weaviate_client.py
│
├── evals/                        # Test harness
│   ├── __init__.py
│   ├── datasets/
│   │   ├── __init__.py
│   │   ├── loader.py             # Dataset loading utilities
│   │   ├── generator.py          # Synthetic QA generation
│   │   └── fixtures/             # Test documents and QA pairs
│   │       ├── documents/
│   │       │   ├── doc1.txt
│   │       │   └── doc2.txt
│   │       └── synthetic_qa_v1.json
│   ├── metrics/
│   │   ├── __init__.py
│   │   └── retrieval.py          # Metric computation
│   ├── harness.py                # Core evaluation runner
│   ├── comparator.py             # Compare evaluation runs
│   ├── reports/                  # Generated reports
│   │   └── .gitkeep
│   └── configs/                  # Evaluation configurations
│       ├── baseline.yaml
│       └── experiment_1.yaml
│
├── tests/                        # Unit and integration tests
│   ├── unit/
│   └── integration/
│
├── docker/
│   ├── Dockerfile.eval           # Evaluation container
│   └── docker-compose.eval.yaml  # Compose for eval environment
│
├── scripts/
│   ├── run_eval.py               # CLI for running evaluations
│   ├── compare_runs.py           # CLI for comparing runs
│   └── generate_synthetic_qa.py  # CLI for generating test data
│
└── pyproject.toml
```

### Metrics Module

```python
# evals/metrics/retrieval.py
from dataclasses import dataclass
import math

@dataclass
class RetrievalMetrics:
    """Computed retrieval metrics."""
    recall_at_k: float
    precision_at_k: float
    hit_rate_at_k: float
    mrr: float
    ndcg_at_k: float
    k: int
    num_queries: int
    avg_latency_ms: float
    
    def to_dict(self) -> dict:
        return {
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "hit_rate_at_k": self.hit_rate_at_k,
            "mrr": self.mrr,
            "ndcg_at_k": self.ndcg_at_k,
            "k": self.k,
            "num_queries": self.num_queries,
            "avg_latency_ms": self.avg_latency_ms,
        }


def dcg_at_k(relevances: list[int], k: int) -> float:
    """Compute Discounted Cumulative Gain at k."""
    relevances = relevances[:k]
    if not relevances:
        return 0.0
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(relevances: list[int], k: int) -> float:
    """Compute Normalized DCG at k."""
    dcg = dcg_at_k(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = dcg_at_k(ideal_relevances, k)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def compute_retrieval_metrics(
    results: list[dict],
    k: int,
) -> RetrievalMetrics:
    """
    Compute retrieval metrics from evaluation results.
    
    Args:
        results: List of dicts with keys:
            - expected: list[str] of relevant chunk IDs
            - retrieved: list[str] of retrieved chunk IDs (ordered)
            - latency_ms: float
        k: Number of top results to consider
    
    Returns:
        RetrievalMetrics with computed values
    """
    if not results:
        raise ValueError("Cannot compute metrics on empty results")
    
    recalls = []
    precisions = []
    hits = []
    reciprocal_ranks = []
    ndcgs = []
    latencies = []
    
    for r in results:
        expected = set(r["expected"])
        retrieved = r["retrieved"][:k]
        retrieved_set = set(retrieved)
        latencies.append(r.get("latency_ms", 0))
        
        # Recall@K: fraction of relevant docs retrieved
        if expected:
            recall = len(expected & retrieved_set) / len(expected)
        else:
            recall = 1.0  # No relevant docs means perfect recall vacuously
        recalls.append(recall)
        
        # Precision@K: fraction of retrieved docs that are relevant
        if retrieved:
            precision = len(expected & retrieved_set) / len(retrieved)
        else:
            precision = 0.0
        precisions.append(precision)
        
        # Hit Rate@K: did we retrieve at least one relevant doc?
        hit = 1.0 if expected & retrieved_set else 0.0
        hits.append(hit)
        
        # MRR: reciprocal of rank of first relevant doc
        rr = 0.0
        for i, chunk_id in enumerate(retrieved, start=1):
            if chunk_id in expected:
                rr = 1.0 / i
                break
        reciprocal_ranks.append(rr)
        
        # NDCG@K: ranking quality
        relevances = [1 if cid in expected else 0 for cid in retrieved]
        ndcgs.append(ndcg_at_k(relevances, k))
    
    n = len(results)
    
    return RetrievalMetrics(
        recall_at_k=sum(recalls) / n,
        precision_at_k=sum(precisions) / n,
        hit_rate_at_k=sum(hits) / n,
        mrr=sum(reciprocal_ranks) / n,
        ndcg_at_k=sum(ndcgs) / n,
        k=k,
        num_queries=n,
        avg_latency_ms=sum(latencies) / n if latencies else 0,
    )
```

### Dataset Loader

```python
# evals/datasets/loader.py
from dataclasses import dataclass
from pathlib import Path
import json

@dataclass
class EvalSample:
    """A single evaluation sample."""
    query_id: str
    query_text: str
    relevant_chunks: list[str]
    metadata: dict | None = None


@dataclass
class EvalDataset:
    """A complete evaluation dataset."""
    name: str
    version: str
    samples: list[EvalSample]
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __iter__(self):
        return iter(self.samples)


def load_dataset(path: Path) -> EvalDataset:
    """Load an evaluation dataset from JSON."""
    with open(path) as f:
        data = json.load(f)
    
    return EvalDataset(
        name=data["name"],
        version=data["version"],
        samples=[
            EvalSample(
                query_id=s["query_id"],
                query_text=s["query_text"],
                relevant_chunks=s["relevant_chunks"],
                metadata=s.get("metadata"),
            )
            for s in data["samples"]
        ],
    )


def save_dataset(dataset: EvalDataset, path: Path) -> None:
    """Save an evaluation dataset to JSON."""
    data = {
        "name": dataset.name,
        "version": dataset.version,
        "samples": [
            {
                "query_id": s.query_id,
                "query_text": s.query_text,
                "relevant_chunks": s.relevant_chunks,
                "metadata": s.metadata,
            }
            for s in dataset.samples
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
```

### Synthetic QA Generator

```python
# evals/datasets/generator.py
from dataclasses import dataclass
from rag.types import Chunk
from evals.datasets.loader import EvalSample, EvalDataset

@dataclass
class QAGeneratorConfig:
    """Configuration for synthetic QA generation."""
    questions_per_chunk: int = 3
    model: str = "gpt-4o-mini"
    temperature: float = 0.7


class SyntheticQAGenerator:
    """Generate synthetic QA pairs from chunks using an LLM."""
    
    def __init__(self, config: QAGeneratorConfig, api_key: str | None = None):
        self.config = config
        
        import openai
        self._client = openai.OpenAI(api_key=api_key)
    
    def generate_questions(self, chunk: Chunk) -> list[str]:
        """Generate questions that this chunk can answer."""
        prompt = f"""Given the following text, generate {self.config.questions_per_chunk} diverse questions that can be answered using ONLY the information in this text.

The questions should:
- Be specific and answerable from the text
- Vary in complexity (some simple, some requiring synthesis)
- Not reference "the text" or "the passage" directly

Text:
{chunk.content}

Generate exactly {self.config.questions_per_chunk} questions, one per line. Output only the questions, nothing else."""

        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
        )
        
        questions = response.choices[0].message.content.strip().split("\n")
        return [q.strip().lstrip("0123456789.-) ") for q in questions if q.strip()]
    
    def generate_dataset(
        self,
        chunks: list[Chunk],
        dataset_name: str,
        dataset_version: str,
    ) -> EvalDataset:
        """Generate a complete evaluation dataset from chunks."""
        samples = []
        query_counter = 0
        
        for chunk in chunks:
            questions = self.generate_questions(chunk)
            
            for question in questions:
                samples.append(EvalSample(
                    query_id=f"q-{query_counter:04d}",
                    query_text=question,
                    relevant_chunks=[chunk.chunk_id],
                    metadata={
                        "source_chunk": chunk.chunk_id,
                        "source_doc": chunk.doc_id,
                    },
                ))
                query_counter += 1
        
        return EvalDataset(
            name=dataset_name,
            version=dataset_version,
            samples=samples,
        )
```

### Evaluation Harness

```python
# evals/harness.py
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
from typing import Callable

from rag.retriever import Retriever
from rag.config import RAGConfig
from evals.datasets.loader import EvalDataset
from evals.metrics.retrieval import compute_retrieval_metrics, RetrievalMetrics

@dataclass
class EvalRunResult:
    """Complete result of an evaluation run."""
    run_id: str
    timestamp: str
    dataset_name: str
    dataset_version: str
    config: dict
    metrics: RetrievalMetrics
    per_query_results: list[dict]
    
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "config": self.config,
            "metrics": self.metrics.to_dict(),
            "per_query_results": self.per_query_results,
        }


class RetrievalEvaluator:
    """Evaluates retrieval quality against a ground truth dataset."""
    
    def __init__(self, retriever: Retriever):
        self.retriever = retriever
    
    def evaluate(
        self,
        dataset: EvalDataset,
        k: int | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> EvalRunResult:
        """
        Run evaluation on a dataset.
        
        Args:
            dataset: The evaluation dataset
            k: Number of top results to evaluate (defaults to config.retrieval.top_k)
            on_progress: Optional callback (current, total)
        
        Returns:
            EvalRunResult with metrics and per-query details
        """
        if k is None:
            k = self.retriever.config.retrieval.top_k
        
        per_query_results = []
        
        for i, sample in enumerate(dataset.samples):
            result = self.retriever.retrieve(sample.query_text)
            retrieved_ids = [c.chunk_id for c in result.chunks]
            
            per_query_results.append({
                "query_id": sample.query_id,
                "query_text": sample.query_text,
                "expected": sample.relevant_chunks,
                "retrieved": retrieved_ids,
                "scores": [c.score for c in result.chunks],
                "latency_ms": result.latency_ms,
            })
            
            if on_progress:
                on_progress(i + 1, len(dataset.samples))
        
        metrics = compute_retrieval_metrics(per_query_results, k=k)
        
        return EvalRunResult(
            run_id=f"eval-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            timestamp=datetime.utcnow().isoformat(),
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            config=self.retriever.config.to_dict(),
            metrics=metrics,
            per_query_results=per_query_results,
        )


def save_eval_run(run: EvalRunResult, output_dir: Path) -> Path:
    """Save evaluation run to JSON file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / f"{run.run_id}.json"
    with open(report_path, "w") as f:
        json.dump(run.to_dict(), f, indent=2)
    
    return report_path


def load_eval_run(path: Path) -> EvalRunResult:
    """Load evaluation run from JSON file."""
    with open(path) as f:
        data = json.load(f)
    
    return EvalRunResult(
        run_id=data["run_id"],
        timestamp=data["timestamp"],
        dataset_name=data["dataset_name"],
        dataset_version=data["dataset_version"],
        config=data["config"],
        metrics=RetrievalMetrics(**data["metrics"]),
        per_query_results=data["per_query_results"],
    )
```

### Run Comparator

```python
# evals/comparator.py
from dataclasses import dataclass
from evals.harness import EvalRunResult

@dataclass
class MetricDelta:
    """Change in a metric between two runs."""
    metric_name: str
    baseline_value: float
    current_value: float
    absolute_delta: float
    relative_delta_percent: float
    is_improvement: bool
    is_regression: bool
    threshold: float


@dataclass
class ComparisonResult:
    """Result of comparing two evaluation runs."""
    baseline_run_id: str
    current_run_id: str
    deltas: list[MetricDelta]
    has_regressions: bool
    config_differences: dict
    

def compare_runs(
    baseline: EvalRunResult,
    current: EvalRunResult,
    regression_thresholds: dict[str, float] | None = None,
) -> ComparisonResult:
    """
    Compare two evaluation runs.
    
    Args:
        baseline: The baseline run to compare against
        current: The current run
        regression_thresholds: Dict of metric_name -> max allowed decrease
            Default: {"recall_at_k": 0.02, "mrr": 0.02, "hit_rate_at_k": 0.02}
    
    Returns:
        ComparisonResult with deltas and regression flags
    """
    if regression_thresholds is None:
        regression_thresholds = {
            "recall_at_k": 0.02,
            "precision_at_k": 0.02,
            "hit_rate_at_k": 0.02,
            "mrr": 0.02,
            "ndcg_at_k": 0.02,
        }
    
    deltas = []
    has_regressions = False
    
    baseline_metrics = baseline.metrics.to_dict()
    current_metrics = current.metrics.to_dict()
    
    for metric_name in ["recall_at_k", "precision_at_k", "hit_rate_at_k", "mrr", "ndcg_at_k"]:
        baseline_val = baseline_metrics[metric_name]
        current_val = current_metrics[metric_name]
        absolute_delta = current_val - baseline_val
        
        if baseline_val != 0:
            relative_delta = (absolute_delta / baseline_val) * 100
        else:
            relative_delta = 0 if current_val == 0 else float('inf')
        
        threshold = regression_thresholds.get(metric_name, 0.02)
        is_regression = absolute_delta < -threshold
        is_improvement = absolute_delta > threshold
        
        if is_regression:
            has_regressions = True
        
        deltas.append(MetricDelta(
            metric_name=metric_name,
            baseline_value=baseline_val,
            current_value=current_val,
            absolute_delta=absolute_delta,
            relative_delta_percent=relative_delta,
            is_improvement=is_improvement,
            is_regression=is_regression,
            threshold=threshold,
        ))
    
    # Find config differences
    config_differences = _find_config_differences(baseline.config, current.config)
    
    return ComparisonResult(
        baseline_run_id=baseline.run_id,
        current_run_id=current.run_id,
        deltas=deltas,
        has_regressions=has_regressions,
        config_differences=config_differences,
    )


def _find_config_differences(config1: dict, config2: dict, prefix: str = "") -> dict:
    """Recursively find differences between two config dicts."""
    differences = {}
    
    all_keys = set(config1.keys()) | set(config2.keys())
    
    for key in all_keys:
        full_key = f"{prefix}.{key}" if prefix else key
        
        if key not in config1:
            differences[full_key] = {"baseline": None, "current": config2[key]}
        elif key not in config2:
            differences[full_key] = {"baseline": config1[key], "current": None}
        elif isinstance(config1[key], dict) and isinstance(config2[key], dict):
            nested_diff = _find_config_differences(config1[key], config2[key], full_key)
            differences.update(nested_diff)
        elif config1[key] != config2[key]:
            differences[full_key] = {"baseline": config1[key], "current": config2[key]}
    
    return differences


def format_comparison_report(comparison: ComparisonResult) -> str:
    """Format a comparison result as a human-readable report."""
    lines = [
        f"Comparison: {comparison.baseline_run_id} → {comparison.current_run_id}",
        "=" * 60,
        "",
        "Metrics:",
    ]
    
    for delta in comparison.deltas:
        status = "✓" if delta.is_improvement else ("✗" if delta.is_regression else " ")
        sign = "+" if delta.absolute_delta >= 0 else ""
        lines.append(
            f"  {status} {delta.metric_name}: "
            f"{delta.baseline_value:.4f} → {delta.current_value:.4f} "
            f"({sign}{delta.absolute_delta:.4f}, {sign}{delta.relative_delta_percent:.1f}%)"
        )
    
    if comparison.config_differences:
        lines.extend(["", "Configuration Changes:"])
        for key, change in comparison.config_differences.items():
            lines.append(f"  {key}: {change['baseline']} → {change['current']}")
    
    if comparison.has_regressions:
        lines.extend(["", "⚠️  REGRESSIONS DETECTED"])
    
    return "\n".join(lines)
```

---

## Weaviate Setup

### Option 1: Embedded Weaviate (Recommended for Tests)

Embedded Weaviate runs in-process—no external dependencies.

```python
# In your test setup
from rag.index_clients.weaviate_client import WeaviateIndexClient
from rag.config import IndexConfig

config = IndexConfig(
    provider="weaviate",
    collection_name="test_documents",
    distance_metric="cosine",
    weaviate_embedded=True,
)

index_client = WeaviateIndexClient.from_config(config)
```

**Requirements:**
- Python 3.10+
- `weaviate-client[embedded]` package

**Limitations:**
- Data is not persisted between runs by default
- Single-process only
- May have performance differences from production

### Option 2: Docker Compose (CI/CD)

```yaml
# docker/docker-compose.eval.yaml
version: '3.8'

services:
  weaviate:
    image: semitechnologies/weaviate:1.24.1
    ports:
      - "8080:8080"
    environment:
      QUERY_DEFAULTS_LIMIT: 100
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
      CLUSTER_HOSTNAME: 'node1'
    volumes:
      - weaviate_data:/var/lib/weaviate
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/v1/.well-known/ready"]
      interval: 5s
      timeout: 3s
      retries: 10

  eval-runner:
    build:
      context: ..
      dockerfile: docker/Dockerfile.eval
    depends_on:
      weaviate:
        condition: service_healthy
    environment:
      WEAVIATE_URL: "http://weaviate:8080"
      OPENAI_API_KEY: "${OPENAI_API_KEY}"
    volumes:
      - ../evals:/app/evals
      - eval_cache:/app/.cache

volumes:
  weaviate_data:
  eval_cache:
```

### Option 3: Persistent Test Instance

For teams that want a stable test environment:

```yaml
# docker/docker-compose.eval-persistent.yaml
version: '3.8'

services:
  weaviate-test:
    image: semitechnologies/weaviate:1.24.1
    ports:
      - "8081:8080"  # Different port from production
    environment:
      QUERY_DEFAULTS_LIMIT: 100
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
    volumes:
      - ./data/weaviate-test:/var/lib/weaviate
```

---

## Docker Environment

### Evaluation Dockerfile

```dockerfile
# docker/Dockerfile.eval
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml poetry.lock* ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Copy application code
COPY rag/ ./rag/
COPY evals/ ./evals/
COPY scripts/ ./scripts/

# Create directories for outputs
RUN mkdir -p /app/evals/reports /app/.cache

# Default command
CMD ["python", "-m", "scripts.run_eval"]
```

### Running Evaluations in Docker

```bash
# Build the evaluation image
docker build -f docker/Dockerfile.eval -t rag-eval .

# Run with embedded Weaviate (fully offline except embeddings)
docker run --rm \
    -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
    -v $(pwd)/evals/reports:/app/evals/reports \
    rag-eval \
    python -m scripts.run_eval --config evals/configs/baseline.yaml

# Run with Docker Compose (Weaviate + eval runner)
docker compose -f docker/docker-compose.eval.yaml up --build

# Run with cached embeddings (fully offline)
docker run --rm \
    -v $(pwd)/evals/reports:/app/evals/reports \
    -v $(pwd)/.cache:/app/.cache \
    rag-eval \
    python -m scripts.run_eval --config evals/configs/baseline.yaml --use-cache
```

---

## Evaluation Datasets

### Dataset JSON Format

```json
{
  "name": "synthetic-qa-v1",
  "version": "1.0.0",
  "description": "Synthetic QA pairs generated from documentation",
  "created_at": "2024-12-05T10:00:00Z",
  "generation_config": {
    "model": "gpt-4o-mini",
    "questions_per_chunk": 3
  },
  "samples": [
    {
      "query_id": "q-0001",
      "query_text": "What are the GDPR consent requirements?",
      "relevant_chunks": ["gdpr-guide.pdf-chunk-3", "gdpr-guide.pdf-chunk-4"],
      "metadata": {
        "source_doc": "gdpr-guide.pdf",
        "difficulty": "medium"
      }
    },
    {
      "query_id": "q-0002",
      "query_text": "How long must consent records be retained?",
      "relevant_chunks": ["gdpr-guide.pdf-chunk-7"],
      "metadata": {
        "source_doc": "gdpr-guide.pdf",
        "difficulty": "easy"
      }
    }
  ]
}
```

### Generating Synthetic QA Pairs

```python
# scripts/generate_synthetic_qa.py
import argparse
from pathlib import Path

from rag.loaders import FileSystemLoader
from rag.chunkers import create_chunker
from rag.config import ChunkingConfig
from evals.datasets.generator import SyntheticQAGenerator, QAGeneratorConfig
from evals.datasets.loader import save_dataset

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-name", default="synthetic-qa")
    parser.add_argument("--dataset-version", default="1.0.0")
    parser.add_argument("--questions-per-chunk", type=int, default=3)
    args = parser.parse_args()
    
    # Load and chunk documents
    loader = FileSystemLoader(args.documents_dir, glob_pattern="**/*.txt")
    chunker = create_chunker(ChunkingConfig(
        strategy="fixed",
        chunk_size=512,
        chunk_overlap=50,
    ))
    
    all_chunks = []
    for doc in loader.load():
        chunks = chunker.chunk(doc)
        all_chunks.extend(chunks)
    
    print(f"Generated {len(all_chunks)} chunks from documents")
    
    # Generate QA pairs
    generator = SyntheticQAGenerator(QAGeneratorConfig(
        questions_per_chunk=args.questions_per_chunk,
    ))
    
    dataset = generator.generate_dataset(
        chunks=all_chunks,
        dataset_name=args.dataset_name,
        dataset_version=args.dataset_version,
    )
    
    print(f"Generated {len(dataset)} QA pairs")
    
    # Save dataset
    save_dataset(dataset, args.output)
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
```

---

## Running Evaluations

### CLI Script

```python
# scripts/run_eval.py
import argparse
from pathlib import Path
import sys

from rag.config import RAGConfig
from rag.loaders import FileSystemLoader
from rag.chunkers import create_chunker
from rag.embeddings import create_embedding_client
from rag.rerankers import create_reranker
from rag.index_clients.weaviate_client import WeaviateIndexClient
from rag.indexer import Indexer
from rag.retriever import Retriever
from evals.datasets.loader import load_dataset
from evals.harness import RetrievalEvaluator, save_eval_run

def main():
    parser = argparse.ArgumentParser(description="Run RAG retrieval evaluation")
    parser.add_argument("--config", type=Path, required=True, help="Path to config YAML")
    parser.add_argument("--dataset", type=Path, required=True, help="Path to evaluation dataset")
    parser.add_argument("--documents-dir", type=Path, help="Path to documents (for indexing)")
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    parser.add_argument("--k", type=int, help="Override top-k for metrics")
    parser.add_argument("--skip-indexing", action="store_true", help="Skip indexing step")
    parser.add_argument("--use-cache", action="store_true", help="Use embedding cache")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/embeddings"))
    args = parser.parse_args()
    
    # Load configuration
    config = RAGConfig.from_yaml(args.config)
    print(f"Loaded config from {args.config}")
    
    # Create clients
    embedding_client = create_embedding_client(
        config.embedding,
        cache_dir=args.cache_dir if args.use_cache else None,
    )
    index_client = WeaviateIndexClient.from_config(config.index)
    reranker = create_reranker(config.reranker)
    
    # Index documents if needed
    if not args.skip_indexing:
        if not args.documents_dir:
            parser.error("--documents-dir required unless --skip-indexing")
        
        print("Indexing documents...")
        loader = FileSystemLoader(args.documents_dir)
        chunker = create_chunker(config.chunking)
        
        indexer = Indexer(
            document_loader=loader,
            chunker=chunker,
            embedding_client=embedding_client,
            index_client=index_client,
            config=config,
        )
        
        def on_progress(stage: str, current: int, total: int):
            print(f"  {stage}: {current}/{total}", end="\r")
        
        index_result = indexer.index(drop_if_exists=True, on_progress=on_progress)
        print(f"\nIndexed {index_result.num_documents} documents, "
              f"{index_result.num_chunks} chunks in {index_result.duration_seconds:.1f}s")
    
    # Create retriever
    retriever = Retriever(
        embedding_client=embedding_client,
        index_client=index_client,
        reranker=reranker,
        config=config,
    )
    
    # Load dataset and run evaluation
    print(f"Loading dataset from {args.dataset}")
    dataset = load_dataset(args.dataset)
    print(f"Loaded {len(dataset)} samples")
    
    print("Running evaluation...")
    evaluator = RetrievalEvaluator(retriever)
    
    def on_progress(current: int, total: int):
        print(f"  Evaluating: {current}/{total}", end="\r")
    
    k = args.k or config.retrieval.top_k
    run = evaluator.evaluate(dataset, k=k, on_progress=on_progress)
    
    # Save report
    report_path = save_eval_run(run, args.output_dir)
    
    # Print summary
    print(f"\n{'=' * 50}")
    print(f"Evaluation Complete: {run.run_id}")
    print(f"{'=' * 50}")
    print(f"  Dataset:      {run.dataset_name} v{run.dataset_version}")
    print(f"  Queries:      {run.metrics.num_queries}")
    print(f"  k:            {run.metrics.k}")
    print(f"{'=' * 50}")
    print(f"  Recall@{k}:    {run.metrics.recall_at_k:.4f}")
    print(f"  Precision@{k}: {run.metrics.precision_at_k:.4f}")
    print(f"  Hit Rate@{k}:  {run.metrics.hit_rate_at_k:.4f}")
    print(f"  MRR:          {run.metrics.mrr:.4f}")
    print(f"  NDCG@{k}:      {run.metrics.ndcg_at_k:.4f}")
    print(f"  Avg Latency:  {run.metrics.avg_latency_ms:.1f}ms")
    print(f"{'=' * 50}")
    print(f"Report saved to: {report_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Compare Runs Script

```python
# scripts/compare_runs.py
import argparse
from pathlib import Path
import sys

from evals.harness import load_eval_run
from evals.comparator import compare_runs, format_comparison_report

def main():
    parser = argparse.ArgumentParser(description="Compare two evaluation runs")
    parser.add_argument("baseline", type=Path, help="Baseline run JSON")
    parser.add_argument("current", type=Path, help="Current run JSON")
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()
    
    baseline = load_eval_run(args.baseline)
    current = load_eval_run(args.current)
    
    comparison = compare_runs(baseline, current)
    report = format_comparison_report(comparison)
    print(report)
    
    if args.fail_on_regression and comparison.has_regressions:
        print("\n❌ Failing due to regressions")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/rag-eval.yaml
name: RAG Retrieval Evaluation

on:
  push:
    paths:
      - 'rag/**'
      - 'evals/**'
  pull_request:
    paths:
      - 'rag/**'
      - 'evals/**'
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2am
  workflow_dispatch:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/pyproject.toml') }}
      
      - name: Cache embeddings
        uses: actions/cache@v4
        with:
          path: .cache/embeddings
          key: embeddings-${{ hashFiles('evals/datasets/fixtures/**') }}
      
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      
      - name: Run evaluation
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m scripts.run_eval \
            --config evals/configs/baseline.yaml \
            --dataset evals/datasets/fixtures/synthetic_qa_v1.json \
            --documents-dir evals/datasets/fixtures/documents \
            --use-cache
      
      - name: Compare with baseline
        if: github.event_name == 'pull_request'
        run: |
          python -m scripts.compare_runs \
            evals/reports/baseline.json \
            evals/reports/eval-*.json \
            --fail-on-regression
      
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: evals/reports/
```

### Pre-commit Hook (Optional)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: rag-eval-smoke
        name: RAG Eval Smoke Test
        entry: python -m scripts.run_eval --config evals/configs/smoke.yaml --skip-indexing
        language: system
        pass_filenames: false
        stages: [push]
```

---

## Regression Detection

### Establishing Baselines

1. Run evaluation on a known-good version
2. Save the report as `baseline.json`
3. Commit to version control

```bash
# Generate and save baseline
python -m scripts.run_eval \
    --config evals/configs/baseline.yaml \
    --dataset evals/datasets/fixtures/synthetic_qa_v1.json \
    --documents-dir evals/datasets/fixtures/documents

# Rename to baseline
cp evals/reports/eval-*.json evals/reports/baseline.json
git add evals/reports/baseline.json
git commit -m "Establish retrieval baseline"
```

### Threshold Configuration

```python
# evals/thresholds.py
DEFAULT_REGRESSION_THRESHOLDS = {
    "recall_at_k": 0.02,      # Fail if recall drops by more than 2%
    "precision_at_k": 0.02,   # Fail if precision drops by more than 2%
    "hit_rate_at_k": 0.02,
    "mrr": 0.02,
    "ndcg_at_k": 0.02,
}

# Stricter thresholds for critical metrics
STRICT_THRESHOLDS = {
    "recall_at_k": 0.01,
    "hit_rate_at_k": 0.01,
}
```

### Tracking Over Time

Store evaluation runs with timestamps for trend analysis:

```
evals/reports/
├── baseline.json
├── eval-20241201-100000.json
├── eval-20241202-100000.json
├── eval-20241203-100000.json
└── ...
```

---

## Summary Checklist

### Production Code Requirements

- [ ] Pure core logic (no side effects)
- [ ] Explicit return types (dataclasses)
- [ ] Injectable dependencies
- [ ] Configuration objects (frozen dataclasses)
- [ ] Deterministic chunk IDs
- [ ] Stateless query handling
- [ ] Abstract interfaces for all swappable components
- [ ] Separate indexing and querying pipelines

### Test Harness Components

- [ ] Dataset loader and format
- [ ] Synthetic QA generator
- [ ] Metrics computation (Recall, Precision, Hit Rate, MRR, NDCG)
- [ ] Evaluation harness
- [ ] Run comparator
- [ ] Report storage and loading

### Infrastructure

- [ ] Weaviate setup (embedded for tests, Docker for CI)
- [ ] Dockerfile for evaluation container
- [ ] Docker Compose for isolated environment
- [ ] Embedding cache for offline runs
- [ ] CI/CD pipeline configuration

### Operational

- [ ] Baseline establishment process
- [ ] Regression threshold configuration
- [ ] Comparison and alerting scripts
- [ ] Documentation for running evaluations
