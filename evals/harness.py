"""Retrieval evaluation harness.

Provides the RetrievalEvaluator class for running evaluation experiments
and the EvalRunResult class for storing evaluation results.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from evals.datasets.loader import EvalDataset
from evals.metrics.retrieval import RetrievalMetrics, compute_retrieval_metrics

logger = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    """Protocol for embedding generation."""

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...


class IndexClient(Protocol):
    """Protocol for index search operations."""

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors."""
        ...


@dataclass(frozen=True)
class EvalRunResult:
    """Result of an evaluation run.

    Contains metrics, configuration, and metadata for a complete
    evaluation experiment.
    """

    run_id: str
    dataset_name: str
    metrics: RetrievalMetrics
    config: dict[str, Any]
    started_at: str
    completed_at: str
    duration_seconds: float
    per_sample_results: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "dataset_name": self.dataset_name,
            "metrics": self.metrics.to_dict(),
            "config": self.config,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "per_sample_results": list(self.per_sample_results),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalRunResult:
        """Create from dictionary."""
        metrics = RetrievalMetrics(
            recall_at_k=data["metrics"]["recall_at_k"],
            precision_at_k=data["metrics"]["precision_at_k"],
            hit_rate_at_k=data["metrics"]["hit_rate_at_k"],
            mrr=data["metrics"]["mrr"],
            ndcg_at_k=data["metrics"]["ndcg_at_k"],
            k=data["metrics"]["k"],
            num_samples=data["metrics"]["num_samples"],
        )
        return cls(
            run_id=data["run_id"],
            dataset_name=data["dataset_name"],
            metrics=metrics,
            config=data["config"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            duration_seconds=data["duration_seconds"],
            per_sample_results=tuple(data["per_sample_results"] if "per_sample_results" in data else []),
            metadata=data["metadata"] if "metadata" in data else {},
        )


def save_eval_run(result: EvalRunResult, path: str | Path) -> None:
    """Save evaluation run result to JSON file.

    Args:
        result: Evaluation run result
        path: Path to save to
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)


def load_eval_run(path: str | Path) -> EvalRunResult:
    """Load evaluation run result from JSON file.

    Args:
        path: Path to load from

    Returns:
        EvalRunResult instance
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return EvalRunResult.from_dict(data)


class RetrievalEvaluator:
    """Orchestrates retrieval evaluation experiments.

    This class runs retrieval experiments against an evaluation dataset
    and computes quality metrics.
    """

    def __init__(
        self,
        index_client: IndexClient,
        embedding_client: EmbeddingClient,
        collection: str,
        top_k: int,
    ) -> None:
        """Initialize the evaluator.

        Args:
            index_client: Client for vector index operations
            embedding_client: Client for generating embeddings
            collection: Collection/index name to search
            top_k: Number of results to retrieve per query
        """
        self.index_client = index_client
        self.embedding_client = embedding_client
        self.collection = collection
        self.top_k = top_k

    def evaluate(
        self,
        dataset: EvalDataset,
        run_id: str | None,
        include_per_sample: bool,
    ) -> EvalRunResult:
        """Run evaluation on a dataset.

        Args:
            dataset: Evaluation dataset to run against
            run_id: Optional run ID (auto-generated if not provided)
            include_per_sample: Whether to include per-sample results

        Returns:
            EvalRunResult with metrics and metadata
        """
        run_id = run_id or f"run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        started_at = datetime.utcnow().isoformat() + "Z"
        start_time = time.time()

        logger.info(f"Starting evaluation run {run_id} on dataset {dataset.name}")
        logger.info(f"Dataset has {len(dataset)} samples, using top_k={self.top_k}")

        # Collect results for each sample
        retrieved_ids_list: list[list[str]] = []
        relevant_ids_list: list[set[str]] = []
        per_sample_results: list[dict[str, Any]] = []

        for i, sample in enumerate(dataset.samples):
            if i > 0 and i % 10 == 0:
                logger.info(f"Processed {i}/{len(dataset)} samples")

            # Generate embedding for question
            query_vector = self.embedding_client.embed(sample.question)

            # Search for similar chunks
            results = self.index_client.search(
                collection=self.collection,
                vector=query_vector,
                top_k=self.top_k,
            )

            # Extract chunk IDs from results
            retrieved_ids = [r["chunk_id"] if "chunk_id" in r else (r["id"] if "id" in r else "") for r in results]
            retrieved_ids_list.append(retrieved_ids)
            relevant_ids_list.append(set(sample.relevant_chunk_ids))

            if include_per_sample:
                per_sample_results.append(
                    {
                        "sample_id": sample.sample_id,
                        "question": sample.question,
                        "retrieved_ids": retrieved_ids,
                        "relevant_ids": list(sample.relevant_chunk_ids),
                    }
                )

        # Compute metrics
        metrics = compute_retrieval_metrics(
            retrieved_ids_list,
            relevant_ids_list,
            k=self.top_k,
            include_per_sample=include_per_sample,
        )

        duration = time.time() - start_time
        completed_at = datetime.utcnow().isoformat() + "Z"

        logger.info(f"Evaluation complete in {duration:.2f}s")
        logger.info(
            f"Metrics: Recall@{self.top_k}={metrics.recall_at_k:.4f}, MRR={metrics.mrr:.4f}, NDCG@{self.top_k}={metrics.ndcg_at_k:.4f}"
        )

        return EvalRunResult(
            run_id=run_id,
            dataset_name=dataset.name,
            metrics=metrics,
            config={
                "collection": self.collection,
                "top_k": self.top_k,
                "chunk_config": dataset.chunk_config.to_dict(),
            },
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            per_sample_results=tuple(per_sample_results),
            metadata={
                "num_samples": len(dataset),
                "dataset_version": dataset.version,
            },
        )
