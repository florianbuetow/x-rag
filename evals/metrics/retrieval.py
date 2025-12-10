"""Retrieval quality metrics for RAG evaluation.

This module provides pure functions for computing retrieval metrics.
All functions are stateless and deterministic, making them easy to test
and compose.

Metrics implemented:
- Recall@K: Fraction of relevant items retrieved in top K
- Precision@K: Fraction of top K items that are relevant
- Hit Rate@K: Binary indicator if any relevant item in top K
- MRR (Mean Reciprocal Rank): 1/rank of first relevant item
- NDCG@K: Normalized Discounted Cumulative Gain

Reference:
- https://en.wikipedia.org/wiki/Discounted_cumulative_gain
- https://en.wikipedia.org/wiki/Mean_reciprocal_rank
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievalMetrics:
    """Container for retrieval quality metrics.

    All metrics are computed at a specific value of K (top-K retrieved items).
    Metrics are aggregated across all samples in the evaluation set.
    """

    recall_at_k: float
    precision_at_k: float
    hit_rate_at_k: float
    mrr: float
    ndcg_at_k: float
    k: int
    num_samples: int
    per_sample_metrics: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary with all metric values
        """
        return {
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "hit_rate_at_k": self.hit_rate_at_k,
            "mrr": self.mrr,
            "ndcg_at_k": self.ndcg_at_k,
            "k": self.k,
            "num_samples": self.num_samples,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"RetrievalMetrics(k={self.k}, n={self.num_samples})\n"
            f"  Recall@{self.k}:    {self.recall_at_k:.4f}\n"
            f"  Precision@{self.k}: {self.precision_at_k:.4f}\n"
            f"  Hit Rate@{self.k}:  {self.hit_rate_at_k:.4f}\n"
            f"  MRR:            {self.mrr:.4f}\n"
            f"  NDCG@{self.k}:      {self.ndcg_at_k:.4f}"
        )


def compute_recall(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int | None,
) -> float:
    """Compute Recall@K.

    Recall measures what fraction of relevant items were retrieved.
    Recall@K = |relevant ∩ retrieved[:k]| / |relevant|

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs
        relevant_ids: Set of relevant chunk IDs (ground truth)
        k: Consider only top-K retrieved items. If None, use all.

    Returns:
        Recall score between 0.0 and 1.0

    Examples:
        >>> compute_recall(["a", "b", "c"], {"a", "d"}, k=3)
        0.5  # Found 1 of 2 relevant items
    """
    if not relevant_ids:
        return 1.0  # No relevant items = perfect recall (vacuously true)

    top_k = retrieved_ids[:k] if k is not None else retrieved_ids
    retrieved_set = set(top_k)
    hits = len(relevant_ids & retrieved_set)

    return hits / len(relevant_ids)


def compute_precision(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int | None,
) -> float:
    """Compute Precision@K.

    Precision measures what fraction of retrieved items are relevant.
    Precision@K = |relevant ∩ retrieved[:k]| / k

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs
        relevant_ids: Set of relevant chunk IDs (ground truth)
        k: Consider only top-K retrieved items. If None, use all.

    Returns:
        Precision score between 0.0 and 1.0

    Examples:
        >>> compute_precision(["a", "b", "c"], {"a", "d"}, k=3)
        0.333...  # 1 of 3 retrieved items is relevant
    """
    top_k = retrieved_ids[:k] if k is not None else retrieved_ids

    if not top_k:
        return 0.0  # No items retrieved = zero precision

    retrieved_set = set(top_k)
    hits = len(relevant_ids & retrieved_set)

    return hits / len(top_k)


def compute_hit_rate(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int | None,
) -> float:
    """Compute Hit Rate@K (Success@K).

    Hit rate is 1.0 if at least one relevant item is in top K, else 0.0.
    Also known as Success@K or Binary Recall.

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs
        relevant_ids: Set of relevant chunk IDs (ground truth)
        k: Consider only top-K retrieved items. If None, use all.

    Returns:
        1.0 if any relevant item found, 0.0 otherwise

    Examples:
        >>> compute_hit_rate(["a", "b", "c"], {"a", "d"}, k=3)
        1.0  # Found at least one relevant item
        >>> compute_hit_rate(["x", "y", "z"], {"a", "d"}, k=3)
        0.0  # Found no relevant items
    """
    if not relevant_ids:
        return 1.0  # No relevant items = hit (vacuously true)

    top_k = retrieved_ids[:k] if k is not None else retrieved_ids
    retrieved_set = set(top_k)

    return 1.0 if (relevant_ids & retrieved_set) else 0.0


def compute_mrr(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    """Compute Mean Reciprocal Rank (MRR).

    MRR is the reciprocal of the rank of the first relevant item.
    MRR = 1/rank of first relevant item (or 0 if none found)

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs
        relevant_ids: Set of relevant chunk IDs (ground truth)

    Returns:
        Reciprocal rank between 0.0 and 1.0

    Examples:
        >>> compute_mrr(["a", "b", "c"], {"b"})
        0.5  # First relevant item at rank 2 → 1/2
        >>> compute_mrr(["a", "b", "c"], {"a"})
        1.0  # First relevant item at rank 1 → 1/1
    """
    if not relevant_ids:
        return 1.0  # No relevant items = perfect score (vacuously true)

    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank

    return 0.0  # No relevant items found


def compute_ndcg(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int | None,
) -> float:
    """Compute Normalized Discounted Cumulative Gain (NDCG@K).

    NDCG measures ranking quality by considering both relevance and position.
    Uses binary relevance (1 if relevant, 0 otherwise).

    DCG@K = Σ(rel_i / log2(i+1)) for i in 1..K
    NDCG@K = DCG@K / IDCG@K

    where IDCG is the ideal DCG (perfect ranking).

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs
        relevant_ids: Set of relevant chunk IDs (ground truth)
        k: Consider only top-K retrieved items. If None, use all.

    Returns:
        NDCG score between 0.0 and 1.0

    Examples:
        >>> compute_ndcg(["a", "b", "c"], {"a"}, k=3)
        1.0  # Relevant item at top position
        >>> compute_ndcg(["x", "a", "b"], {"a"}, k=3)
        0.630...  # Relevant item at position 2
    """
    if not relevant_ids:
        return 1.0  # No relevant items = perfect score (vacuously true)

    top_k = retrieved_ids[:k] if k is not None else retrieved_ids

    # Compute DCG
    dcg = 0.0
    for i, doc_id in enumerate(top_k):
        if doc_id in relevant_ids:
            # Binary relevance: rel_i = 1 for relevant items
            # Position discount: log2(i+2) where i is 0-indexed
            dcg += 1.0 / math.log2(i + 2)

    # Compute IDCG (ideal DCG: all relevant items at top positions)
    num_relevant_in_k = min(len(relevant_ids), len(top_k))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(num_relevant_in_k))

    if idcg == 0:
        return 0.0

    return dcg / idcg


def compute_retrieval_metrics(
    retrieved_ids_list: list[list[str]],
    relevant_ids_list: list[set[str]],
    k: int,
    include_per_sample: bool,
) -> RetrievalMetrics:
    """Compute aggregate retrieval metrics across multiple samples.

    This function computes metrics for each sample and returns aggregated
    (mean) values across all samples.

    Args:
        retrieved_ids_list: List of retrieved ID lists (one per sample)
        relevant_ids_list: List of relevant ID sets (one per sample)
        k: K value for @K metrics
        include_per_sample: Whether to include per-sample metrics in result

    Returns:
        RetrievalMetrics with aggregated values

    Raises:
        ValueError: If list lengths don't match or k <= 0

    Examples:
        >>> retrieved = [["a", "b"], ["x", "y"]]
        >>> relevant = [{"a"}, {"z"}]
        >>> metrics = compute_retrieval_metrics(retrieved, relevant, k=2)
        >>> metrics.recall_at_k
        0.5  # Average of 1.0 and 0.0
    """
    if len(retrieved_ids_list) != len(relevant_ids_list):
        raise ValueError(f"Mismatched list lengths: {len(retrieved_ids_list)} retrieved vs {len(relevant_ids_list)} relevant")

    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    num_samples = len(retrieved_ids_list)
    if num_samples == 0:
        return RetrievalMetrics(
            recall_at_k=0.0,
            precision_at_k=0.0,
            hit_rate_at_k=0.0,
            mrr=0.0,
            ndcg_at_k=0.0,
            k=k,
            num_samples=0,
            per_sample_metrics=(),
        )

    # Compute per-sample metrics
    recalls = []
    precisions = []
    hit_rates = []
    mrrs = []
    ndcgs = []
    per_sample: list[dict[str, Any]] = []

    for retrieved, relevant in zip(retrieved_ids_list, relevant_ids_list, strict=True):
        recall = compute_recall(retrieved, relevant, k)
        precision = compute_precision(retrieved, relevant, k)
        hit_rate = compute_hit_rate(retrieved, relevant, k)
        mrr = compute_mrr(retrieved, relevant)
        ndcg = compute_ndcg(retrieved, relevant, k)

        recalls.append(recall)
        precisions.append(precision)
        hit_rates.append(hit_rate)
        mrrs.append(mrr)
        ndcgs.append(ndcg)

        if include_per_sample:
            per_sample.append(
                {
                    "recall_at_k": recall,
                    "precision_at_k": precision,
                    "hit_rate_at_k": hit_rate,
                    "mrr": mrr,
                    "ndcg_at_k": ndcg,
                    "num_retrieved": len(retrieved),
                    "num_relevant": len(relevant),
                }
            )

    # Aggregate: mean across samples
    return RetrievalMetrics(
        recall_at_k=sum(recalls) / num_samples,
        precision_at_k=sum(precisions) / num_samples,
        hit_rate_at_k=sum(hit_rates) / num_samples,
        mrr=sum(mrrs) / num_samples,
        ndcg_at_k=sum(ndcgs) / num_samples,
        k=k,
        num_samples=num_samples,
        per_sample_metrics=tuple(per_sample) if include_per_sample else (),
    )
