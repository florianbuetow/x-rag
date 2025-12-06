"""RAG Evaluation Harness.

This module provides tools for evaluating retrieval quality in RAG systems.
It includes metrics computation, dataset management, and evaluation orchestration.

Main components:
- metrics: Retrieval quality metrics (Recall@K, Precision@K, MRR, NDCG)
- datasets: Evaluation dataset loading and saving
- harness: Evaluation orchestration (RetrievalEvaluator)
- comparator: Run comparison and regression detection

Configuration is done via YAML files that map to production config classes.
See evals/configs/ for examples.

Usage:
    # Run evaluation with config file
    uv run python -m evals.run_eval --config evals/configs/production.yaml

    # Or use programmatically
    from evals import load_dataset
    from evals.metrics import compute_retrieval_metrics

    dataset = load_dataset("data/eval/.../dataset.json")
"""

from evals.comparator import ComparisonResult, compare_runs
from evals.datasets.loader import EvalDataset, EvalSample, load_dataset, save_dataset
from evals.harness import EvalRunResult, RetrievalEvaluator
from evals.metrics import RetrievalMetrics, compute_retrieval_metrics

__all__ = [
    # Metrics
    "RetrievalMetrics",
    "compute_retrieval_metrics",
    # Datasets
    "EvalDataset",
    "EvalSample",
    "load_dataset",
    "save_dataset",
    # Harness
    "RetrievalEvaluator",
    "EvalRunResult",
    # Comparator
    "ComparisonResult",
    "compare_runs",
]
