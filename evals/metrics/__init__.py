"""Retrieval quality metrics.

Provides metrics for evaluating retrieval performance:
- Recall@K: Proportion of relevant documents retrieved
- Precision@K: Proportion of retrieved documents that are relevant
- Hit Rate@K: Whether any relevant document was retrieved
- MRR (Mean Reciprocal Rank): Average of reciprocal ranks
- NDCG@K: Normalized Discounted Cumulative Gain
"""

from evals.metrics.retrieval import (
    RetrievalMetrics,
    compute_hit_rate,
    compute_mrr,
    compute_ndcg,
    compute_precision,
    compute_recall,
    compute_retrieval_metrics,
)

__all__ = [
    "RetrievalMetrics",
    "compute_retrieval_metrics",
    "compute_recall",
    "compute_precision",
    "compute_hit_rate",
    "compute_mrr",
    "compute_ndcg",
]
