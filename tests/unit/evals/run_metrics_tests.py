#!/usr/bin/env python3
"""Run metrics unit tests directly.

Usage: uv run python tests/unit/evals/run_metrics_tests.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from evals.metrics.retrieval import (
    RetrievalMetrics,
    compute_hit_rate,
    compute_mrr,
    compute_ndcg,
    compute_precision,
    compute_recall,
    compute_retrieval_metrics,
)


def test_compute_recall():
    """Tests for compute_recall function."""
    # Perfect recall
    assert compute_recall(["a", "b", "c"], {"a", "b"}, k=3) == 1.0
    # Partial recall
    assert compute_recall(["a", "b", "c"], {"a", "d"}, k=3) == 0.5
    # Zero recall
    assert compute_recall(["x", "y", "z"], {"a", "b"}, k=3) == 0.0
    # K limit
    assert compute_recall(["x", "y", "a", "b"], {"a", "b"}, k=2) == 0.0
    assert compute_recall(["x", "y", "a", "b"], {"a", "b"}, k=3) == 0.5
    assert compute_recall(["x", "y", "a", "b"], {"a", "b"}, k=4) == 1.0
    # Empty relevant
    assert compute_recall(["a", "b", "c"], set(), k=3) == 1.0
    # Empty retrieved
    assert compute_recall([], {"a", "b"}, k=3) == 0.0
    print("✓ compute_recall: all tests passed")


def test_compute_precision():
    """Tests for compute_precision function."""
    # Perfect precision
    assert compute_precision(["a", "b"], {"a", "b", "c"}, k=2) == 1.0
    # Partial precision
    assert abs(compute_precision(["a", "b", "c"], {"a"}, k=3) - 1 / 3) < 0.001
    # Zero precision
    assert compute_precision(["x", "y", "z"], {"a", "b"}, k=3) == 0.0
    # K limit
    assert compute_precision(["a", "x", "y", "z"], {"a"}, k=1) == 1.0
    assert compute_precision(["a", "x", "y", "z"], {"a"}, k=2) == 0.5
    assert compute_precision(["a", "x", "y", "z"], {"a"}, k=4) == 0.25
    # Empty retrieved
    assert compute_precision([], {"a", "b"}, k=3) == 0.0
    print("✓ compute_precision: all tests passed")


def test_compute_hit_rate():
    """Tests for compute_hit_rate function."""
    # Hit
    assert compute_hit_rate(["x", "a", "y"], {"a", "b"}, k=3) == 1.0
    # No hit
    assert compute_hit_rate(["x", "y", "z"], {"a", "b"}, k=3) == 0.0
    # K limit
    assert compute_hit_rate(["x", "y", "a"], {"a"}, k=2) == 0.0
    assert compute_hit_rate(["x", "y", "a"], {"a"}, k=3) == 1.0
    # Empty relevant
    assert compute_hit_rate(["x", "y", "z"], set(), k=3) == 1.0
    print("✓ compute_hit_rate: all tests passed")


def test_compute_mrr():
    """Tests for compute_mrr function."""
    # First position
    assert compute_mrr(["a", "b", "c"], {"a"}) == 1.0
    # Second position
    assert compute_mrr(["x", "a", "b"], {"a"}) == 0.5
    # Third position
    assert abs(compute_mrr(["x", "y", "a"], {"a"}) - 1 / 3) < 0.001
    # Uses first relevant
    assert compute_mrr(["x", "a", "b"], {"a", "b"}) == 0.5
    # No relevant
    assert compute_mrr(["x", "y", "z"], {"a", "b"}) == 0.0
    # Empty relevant
    assert compute_mrr(["x", "y", "z"], set()) == 1.0
    print("✓ compute_mrr: all tests passed")


def test_compute_ndcg():
    """Tests for compute_ndcg function."""
    # Perfect ranking
    assert compute_ndcg(["a", "b", "c"], {"a"}, k=3) == 1.0
    # Suboptimal ranking
    result = compute_ndcg(["x", "a", "b"], {"a"}, k=3)
    assert abs(result - 0.630) < 0.01
    # Multiple relevant perfect
    assert compute_ndcg(["a", "b", "x"], {"a", "b"}, k=3) == 1.0
    # Multiple relevant suboptimal
    result = compute_ndcg(["x", "a", "b"], {"a", "b"}, k=3)
    assert abs(result - 0.693) < 0.01
    # No relevant
    assert compute_ndcg(["x", "y", "z"], {"a", "b"}, k=3) == 0.0
    # Empty relevant
    assert compute_ndcg(["x", "y", "z"], set(), k=3) == 1.0
    print("✓ compute_ndcg: all tests passed")


def test_compute_retrieval_metrics():
    """Tests for compute_retrieval_metrics aggregate function."""
    # Single sample
    metrics = compute_retrieval_metrics([["a", "b", "c"]], [{"a"}], k=3)
    assert metrics.k == 3
    assert metrics.num_samples == 1
    assert metrics.recall_at_k == 1.0
    assert abs(metrics.precision_at_k - 1 / 3) < 0.001
    assert metrics.hit_rate_at_k == 1.0
    assert metrics.mrr == 1.0
    assert metrics.ndcg_at_k == 1.0

    # Multiple samples averaging
    metrics = compute_retrieval_metrics([["a", "b", "c"], ["x", "y", "z"]], [{"a"}, {"x"}], k=3)
    assert metrics.num_samples == 2
    assert metrics.recall_at_k == 1.0
    assert abs(metrics.precision_at_k - 1 / 3) < 0.001
    assert metrics.hit_rate_at_k == 1.0
    assert metrics.mrr == 1.0

    # Mixed results
    metrics = compute_retrieval_metrics([["a", "b"], ["x", "y"]], [{"a"}, {"z"}], k=2)
    assert metrics.recall_at_k == 0.5
    assert metrics.hit_rate_at_k == 0.5

    # Empty samples
    metrics = compute_retrieval_metrics([], [], k=3)
    assert metrics.num_samples == 0
    assert metrics.recall_at_k == 0.0

    # Mismatched lengths
    try:
        compute_retrieval_metrics([["a"]], [{"a"}, {"b"}], k=3)
        raise AssertionError("Should raise ValueError")
    except ValueError as e:
        assert "Mismatched" in str(e)

    # Invalid k
    try:
        compute_retrieval_metrics([["a"]], [{"a"}], k=0)
        raise AssertionError("Should raise ValueError")
    except ValueError as e:
        assert "k must be positive" in str(e)

    # Per-sample metrics
    metrics = compute_retrieval_metrics([["a", "b"], ["x", "y"]], [{"a"}, {"z"}], k=2, include_per_sample=True)
    assert len(metrics.per_sample_metrics) == 2
    assert metrics.per_sample_metrics[0]["recall_at_k"] == 1.0
    assert metrics.per_sample_metrics[1]["recall_at_k"] == 0.0

    print("✓ compute_retrieval_metrics: all tests passed")


def test_retrieval_metrics_dataclass():
    """Tests for RetrievalMetrics dataclass."""
    metrics = RetrievalMetrics(
        recall_at_k=0.8,
        precision_at_k=0.6,
        hit_rate_at_k=0.9,
        mrr=0.7,
        ndcg_at_k=0.75,
        k=5,
        num_samples=100,
    )

    # to_dict
    d = metrics.to_dict()
    assert d["recall_at_k"] == 0.8
    assert d["precision_at_k"] == 0.6
    assert d["k"] == 5
    assert d["num_samples"] == 100

    # str representation
    s = str(metrics)
    assert "k=5" in s
    assert "n=100" in s

    # Frozen
    try:
        metrics.recall_at_k = 0.9  # type: ignore
        raise AssertionError("Should be frozen")
    except (AttributeError, TypeError):
        pass  # Expected - frozen dataclass raises on attribute assignment

    print("✓ RetrievalMetrics: all tests passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Running evals.metrics tests")
    print("=" * 60 + "\n")

    test_compute_recall()
    test_compute_precision()
    test_compute_hit_rate()
    test_compute_mrr()
    test_compute_ndcg()
    test_compute_retrieval_metrics()
    test_retrieval_metrics_dataclass()

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
