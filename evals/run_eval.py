#!/usr/bin/env python3
"""Run evaluation using production components.

This is a thin wrapper that:
1. Loads a YAML config file
2. Uses production factory methods to create components
3. Runs evaluation using the same code paths as production

Usage:
    uv run python -m evals.run_eval --config evals/configs/production.yaml
    uv run python -m evals.run_eval --config evals/configs/baseline.yaml --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import weaviate
import yaml
from dotenv import load_dotenv
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import Filter

# Eval-specific imports (metrics, dataset, harness)
from evals.datasets.loader import load_dataset
from evals.harness import EvalRunResult
from evals.metrics.retrieval import compute_retrieval_metrics
from src.embedding_service.generators.embedding_generator import EmbeddingGenerator
from src.embedding_service.generators.factory import EmbeddingGeneratorFactory
from src.embedding_service.generators.openai_generator import OpenAIEmbeddingGenerator

# Production imports - reuse exactly what production uses
from src.llm.config import EmbeddingConfig

# Load .env at module import
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_config(path: str | Path) -> dict[str, Any]:
    """Load YAML config file."""
    with open(path) as f:
        return yaml.safe_load(f)


def create_embedding_generator(config: dict[str, Any]) -> tuple[EmbeddingGenerator, str, int]:
    """Create embedding generator using production factory.

    Args:
        config: Parsed YAML config dict

    Returns:
        Tuple of (generator, model_name, dimension)
    """
    embed_cfg = config.get("embedding", {})
    provider = embed_cfg.get("provider", "hash_based")

    # Create production EmbeddingConfig using factory methods
    if provider == "hash_based":
        dimension = embed_cfg.get("dimension", 1024)
        embedding_config = EmbeddingConfig.for_hash_based(dimension=dimension)
        model = "hash-based"
    elif provider == "local":
        base_url = embed_cfg.get("base_url") or os.environ.get("OPENAI_API_BASE")
        model = embed_cfg.get("model", "text-embedding-bge-large-en-v1.5")
        embedding_config = EmbeddingConfig.for_local(
            base_url=base_url,
            model=model,
            api_key=os.environ.get("OPENAI_API_KEY", "local"),
        )
        dimension = OpenAIEmbeddingGenerator.MODEL_DIMENSIONS.get(model, embed_cfg.get("dimension", 1024))
    elif provider == "openai":
        model = embed_cfg.get("model", "text-embedding-3-small")
        embedding_config = EmbeddingConfig.for_openai(
            api_key=os.environ.get("OPENAI_API_KEY"),
            model=model,
        )
        dimension = OpenAIEmbeddingGenerator.MODEL_DIMENSIONS.get(model, 1536)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")

    # Use production factory
    generator = EmbeddingGeneratorFactory.create_from_config(embedding_config)
    return generator, model, dimension


class SyncEmbeddingWrapper:
    """Sync wrapper for async embedding generator."""

    def __init__(self, generator: EmbeddingGenerator, model: str) -> None:
        self.generator = generator
        self.model = model
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        return self._get_loop().run_until_complete(self.generator.embed(text, self.model))

    def embed_batch(self, texts: list[str], batch_size: int = 50) -> list[list[float]]:
        """Embed a batch of texts."""
        loop = self._get_loop()
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = loop.run_until_complete(self.generator.embed_batch(batch, self.model))
            all_embeddings.extend(embeddings)
        return all_embeddings


class EmbeddedWeaviateClient:
    """Embedded Weaviate for evaluation - no network required."""

    def __init__(self, collection_name: str = "DocumentChunk") -> None:
        self.collection_name = collection_name
        self.client: weaviate.WeaviateClient | None = None

    def connect(self) -> None:
        """Start embedded Weaviate instance."""
        logger.info("Starting embedded Weaviate...")
        self.client = weaviate.connect_to_embedded(
            port=8079,
            grpc_port=50050,
            persistence_data_path="/tmp/weaviate_eval",
        )
        logger.info("Embedded Weaviate started")

    def close(self) -> None:
        """Close Weaviate connection."""
        if self.client:
            self.client.close()
            self.client = None

    def create_collection(self, dimension: int) -> None:
        """Create or recreate the vector collection."""
        if not self.client:
            raise RuntimeError("Not connected")
        if self.client.collections.exists(self.collection_name):
            self.client.collections.delete(self.collection_name)
        self.client.collections.create(
            name=self.collection_name,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="content", data_type=DataType.TEXT),
                Property(name="doc_id", data_type=DataType.TEXT),
                Property(name="chunk_index", data_type=DataType.INT),
                Property(name="namespace", data_type=DataType.TEXT),
                Property(name="source", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
            ],
        )
        logger.info(f"Created collection: {self.collection_name}")

    def index_chunks(self, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> int:
        """Index chunks with their embeddings."""
        if not self.client:
            raise RuntimeError("Not connected")
        collection = self.client.collections.get(self.collection_name)
        with collection.batch.dynamic() as batch:
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                batch.add_object(
                    properties={
                        "content": chunk["content"],
                        "doc_id": chunk["doc_id"],
                        "chunk_index": chunk["chunk_index"],
                        "namespace": chunk.get("namespace", "default"),
                        "source": chunk.get("source", ""),
                        "title": chunk.get("title", ""),
                    },
                    vector=embedding,
                )
        return len(chunks)

    def search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int,
        mode: Literal["vector", "bm25", "hybrid"],
        alpha: float,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks."""
        if not self.client:
            raise RuntimeError("Not connected")
        collection = self.client.collections.get(self.collection_name)
        filters = Filter.by_property("namespace").equal(namespace) if namespace else None

        if mode == "vector":
            result = collection.query.near_vector(near_vector=query_embedding, limit=top_k, return_metadata=["distance"], filters=filters)
        elif mode == "bm25":
            result = collection.query.bm25(query=query, limit=top_k, return_metadata=["score"], filters=filters)
        else:  # hybrid
            result = collection.query.hybrid(
                query=query, vector=query_embedding, alpha=alpha, limit=top_k, return_metadata=["score"], filters=filters
            )

        results = []
        for obj in result.objects:
            doc_id = obj.properties.get("doc_id", "")
            chunk_index = obj.properties.get("chunk_index", 0)
            chunk_id = f"{doc_id}-chunk-{chunk_index}"
            if mode == "vector":
                distance = obj.metadata.distance or 0.0
                score = 1.0 / (1.0 + distance)
            else:
                score = obj.metadata.score or 0.0
            results.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_index": chunk_index,
                    "content": obj.properties.get("content", ""),
                    "score": score,
                }
            )
        return results


def load_and_chunk_documents(documents_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[dict[str, Any]]:
    """Load documents and split into chunks."""
    docs_path = Path(documents_path)
    if not docs_path.exists():
        raise FileNotFoundError(f"Documents path not found: {documents_path}")

    chunks = []
    txt_files = list(docs_path.glob("*.txt"))
    logger.info(f"Found {len(txt_files)} documents in {documents_path}")

    for txt_file in txt_files:
        content = txt_file.read_text(encoding="utf-8")
        doc_id = re.sub(r"[^\w\s-]", "", txt_file.stem)
        doc_id = re.sub(r"\s+", "_", doc_id)
        doc_id = doc_id.lower()

        start = 0
        chunk_index = 0
        while start < len(content):
            end = start + chunk_size
            chunk_content = content[start:end]
            if chunk_content.strip():
                chunks.append(
                    {
                        "content": chunk_content,
                        "doc_id": doc_id,
                        "chunk_index": chunk_index,
                        "source": txt_file.name,
                        "title": txt_file.stem,
                        "namespace": "default",
                    }
                )
                chunk_index += 1
            start += chunk_size - chunk_overlap

    logger.info(f"Created {len(chunks)} chunks from {len(txt_files)} documents")
    return chunks


def run_evaluation(config: dict[str, Any]) -> EvalRunResult:
    """Run evaluation using production components."""
    name = config.get("name", "unnamed")
    run_id = f"{name}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    start_time = time.time()

    # Extract config sections
    dataset_path = config["dataset_path"]
    index_cfg = config.get("index", {})
    search_cfg = config.get("search", {})
    chunking_cfg = config.get("chunking", {})

    logger.info("=" * 60)
    logger.info(f"Evaluation Run: {run_id}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Dataset: {dataset_path}")
    logger.info(f"  Documents: {index_cfg.get('documents_path')}")

    # Create embedding generator using production factory
    generator, model, dimension = create_embedding_generator(config)
    embedding_client = SyncEmbeddingWrapper(generator, model)
    logger.info(f"  Embeddings: {config.get('embedding', {}).get('provider')} ({model}, dim={dimension})")
    logger.info(f"  Search: mode={search_cfg.get('mode', 'hybrid')}, top_k={search_cfg.get('top_k', 10)}")
    logger.info("")

    # Load dataset
    logger.info("Loading evaluation dataset...")
    dataset = load_dataset(dataset_path)
    logger.info(f"  Loaded {len(dataset)} QA samples")

    # Start embedded Weaviate
    weaviate_client = EmbeddedWeaviateClient(collection_name=index_cfg.get("collection", "DocumentChunk"))
    weaviate_client.connect()
    weaviate_client.create_collection(dimension=dimension)

    # Load and chunk documents
    logger.info("")
    logger.info("Loading and chunking documents...")
    chunks = load_and_chunk_documents(
        index_cfg.get("documents_path"),
        chunk_size=chunking_cfg.get("chunk_size", 500),
        chunk_overlap=chunking_cfg.get("chunk_overlap", 50),
    )

    # Generate embeddings
    logger.info("Generating embeddings for chunks...")
    chunk_texts = [c["content"] for c in chunks]
    batch_size = config.get("embedding", {}).get("batch_size", 50)
    chunk_embeddings = embedding_client.embed_batch(chunk_texts, batch_size=batch_size)
    logger.info(f"  Generated {len(chunk_embeddings)} embeddings")

    # Index chunks
    logger.info("Indexing chunks into embedded Weaviate...")
    indexed = weaviate_client.index_chunks(chunks, chunk_embeddings)
    logger.info(f"  Indexed {indexed} chunks")

    # Run evaluation
    logger.info("")
    logger.info("Running evaluation...")
    retrieved_ids_list: list[list[str]] = []
    relevant_ids_list: list[set[str]] = []
    per_sample_results: list[dict] = []

    top_k = search_cfg.get("top_k", 10)
    mode = search_cfg.get("mode", "hybrid")
    alpha = search_cfg.get("alpha", 0.5)
    namespace = search_cfg.get("namespace")
    include_per_sample = config.get("include_per_sample", False)

    for i, sample in enumerate(dataset.samples):
        if (i + 1) % 50 == 0 or i == 0:
            logger.info(f"  Processing sample {i + 1}/{len(dataset)}...")

        query_embedding = embedding_client.embed(sample.question)
        results = weaviate_client.search(
            query=sample.question,
            query_embedding=query_embedding,
            top_k=top_k,
            mode=mode,
            alpha=alpha,
            namespace=namespace,
        )

        retrieved_ids = [r["chunk_id"] for r in results]
        retrieved_ids_list.append(retrieved_ids)
        relevant_ids_list.append(set(sample.relevant_chunk_ids))

        if include_per_sample:
            per_sample_results.append(
                {
                    "sample_id": sample.sample_id,
                    "question": sample.question,
                    "retrieved_ids": retrieved_ids,
                    "relevant_ids": list(sample.relevant_chunk_ids),
                    "scores": [r["score"] for r in results],
                }
            )

    # Compute metrics
    logger.info("")
    logger.info("Computing metrics...")
    metrics = compute_retrieval_metrics(retrieved_ids_list, relevant_ids_list, k=top_k, include_per_sample=include_per_sample)

    # Cleanup
    weaviate_client.close()

    duration = time.time() - start_time
    completed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    result = EvalRunResult(
        run_id=run_id,
        dataset_name=dataset.name,
        metrics=metrics,
        config=config,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration,
        per_sample_results=tuple(per_sample_results),
        metadata={
            "num_samples": len(dataset),
            "num_chunks": len(chunks),
            "num_documents": len(set(c["doc_id"] for c in chunks)),
            "dataset_version": dataset.version,
            "embedding_provider": config.get("embedding", {}).get("provider"),
            "embedding_model": model,
            "embedding_dimension": dimension,
            "weaviate_type": "embedded",
        },
    )

    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("Results")
    logger.info("=" * 60)
    logger.info(f"  Recall@{top_k}:    {metrics.recall_at_k:.4f}")
    logger.info(f"  Precision@{top_k}: {metrics.precision_at_k:.4f}")
    logger.info(f"  Hit Rate@{top_k}:  {metrics.hit_rate_at_k:.4f}")
    logger.info(f"  MRR:              {metrics.mrr:.4f}")
    logger.info(f"  NDCG@{top_k}:       {metrics.ndcg_at_k:.4f}")
    logger.info("")
    logger.info(f"Duration: {duration:.2f}s ({len(chunks)} chunks indexed)")
    logger.info("=" * 60)

    return result


def save_result(result: EvalRunResult, output_dir: str) -> Path:
    """Save evaluation result to JSON file."""
    output_path = Path(output_dir) / f"{result.run_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    return output_path


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument("--config", type=Path, required=True, help="Path to evaluation config YAML")
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit")
    parser.add_argument("--output-dir", type=str, help="Override output directory")

    args = parser.parse_args()

    if not args.config.exists():
        logger.error(f"Config file not found: {args.config}")
        return 1

    config = load_config(args.config)

    if args.output_dir:
        config["output_dir"] = args.output_dir

    if args.dry_run:
        logger.info("Dry run - configuration:")
        logger.info(json.dumps(config, indent=2))
        return 0

    # Validate paths
    if not Path(config["dataset_path"]).exists():
        logger.error(f"Dataset not found: {config['dataset_path']}")
        return 1

    index_cfg = config.get("index", {})
    if not Path(index_cfg.get("documents_path", "")).exists():
        logger.error(f"Documents not found: {index_cfg.get('documents_path')}")
        return 1

    try:
        result = run_evaluation(config)
        output_path = save_result(result, config.get("output_dir", "evals/reports"))
        logger.info(f"\nResults saved to: {output_path}")
        return 0
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main())
