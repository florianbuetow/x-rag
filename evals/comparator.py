"""Evaluation run comparison and regression detection.

Provides utilities for comparing evaluation runs to detect
regressions or improvements in retrieval quality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evals.harness import EvalRunResult
from evals.metrics.retrieval import RetrievalMetrics


@dataclass(frozen=True)
class MetricDelta:
    """Change in a single metric between two runs."""

    metric_name: str
    baseline_value: float
    current_value: float
    absolute_change: float
    relative_change_percent: float

    @property
    def improved(self) -> bool:
        """Whether the metric improved (higher is better for all metrics)."""
        return self.absolute_change > 0

    @property
    def regressed(self) -> bool:
        """Whether the metric regressed."""
        return self.absolute_change < 0

    def __str__(self) -> str:
        """Human-readable representation."""
        direction = "↑" if self.improved else "↓" if self.regressed else "→"
        return (
            f"{self.metric_name}: {self.baseline_value:.4f} → {self.current_value:.4f} "
            f"({direction} {self.absolute_change:+.4f}, {self.relative_change_percent:+.1f}%)"
        )


@dataclass(frozen=True)
class ComparisonResult:
    """Result of comparing two evaluation runs.

    Provides delta for each metric and overall regression detection.
    """

    baseline_run_id: str
    current_run_id: str
    dataset_name: str
    deltas: tuple[MetricDelta, ...]
    regression_threshold: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_regression(self) -> bool:
        """Whether any metric regressed beyond the threshold."""
        return any(d.regressed and abs(d.relative_change_percent) > self.regression_threshold for d in self.deltas)

    @property
    def has_improvement(self) -> bool:
        """Whether any metric improved beyond the threshold."""
        return any(d.improved and d.relative_change_percent > self.regression_threshold for d in self.deltas)

    @property
    def regressed_metrics(self) -> list[MetricDelta]:
        """Metrics that regressed beyond threshold."""
        return [d for d in self.deltas if d.regressed and abs(d.relative_change_percent) > self.regression_threshold]

    @property
    def improved_metrics(self) -> list[MetricDelta]:
        """Metrics that improved beyond threshold."""
        return [d for d in self.deltas if d.improved and d.relative_change_percent > self.regression_threshold]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "baseline_run_id": self.baseline_run_id,
            "current_run_id": self.current_run_id,
            "dataset_name": self.dataset_name,
            "regression_threshold": self.regression_threshold,
            "has_regression": self.has_regression,
            "has_improvement": self.has_improvement,
            "deltas": [
                {
                    "metric_name": d.metric_name,
                    "baseline_value": d.baseline_value,
                    "current_value": d.current_value,
                    "absolute_change": d.absolute_change,
                    "relative_change_percent": d.relative_change_percent,
                    "improved": d.improved,
                    "regressed": d.regressed,
                }
                for d in self.deltas
            ],
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Comparison: {self.baseline_run_id} → {self.current_run_id}",
            f"Dataset: {self.dataset_name}",
            f"Regression threshold: {self.regression_threshold}%",
            "",
            "Metric Changes:",
        ]
        lines.extend(f"  {d}" for d in self.deltas)
        lines.append("")
        if self.has_regression:
            lines.append(f"⚠️  REGRESSION DETECTED in: {', '.join(d.metric_name for d in self.regressed_metrics)}")
        elif self.has_improvement:
            lines.append(f"✓ Improvement in: {', '.join(d.metric_name for d in self.improved_metrics)}")
        else:
            lines.append("→ No significant changes")
        return "\n".join(lines)


def _compute_metric_delta(name: str, baseline: float, current: float) -> MetricDelta:
    """Compute delta for a single metric.

    Args:
        name: Metric name
        baseline: Baseline value
        current: Current value

    Returns:
        MetricDelta with computed changes
    """
    absolute = current - baseline
    # Avoid division by zero
    relative = (100.0 if current > 0 else (0.0 if current == 0 else -100.0)) if baseline == 0 else (absolute / baseline) * 100

    return MetricDelta(
        metric_name=name,
        baseline_value=baseline,
        current_value=current,
        absolute_change=absolute,
        relative_change_percent=relative,
    )


def compare_metrics(
    baseline: RetrievalMetrics,
    current: RetrievalMetrics,
) -> list[MetricDelta]:
    """Compare two sets of retrieval metrics.

    Args:
        baseline: Baseline metrics
        current: Current metrics to compare against baseline

    Returns:
        List of MetricDelta for each metric
    """
    return [
        _compute_metric_delta("recall_at_k", baseline.recall_at_k, current.recall_at_k),
        _compute_metric_delta("precision_at_k", baseline.precision_at_k, current.precision_at_k),
        _compute_metric_delta("hit_rate_at_k", baseline.hit_rate_at_k, current.hit_rate_at_k),
        _compute_metric_delta("mrr", baseline.mrr, current.mrr),
        _compute_metric_delta("ndcg_at_k", baseline.ndcg_at_k, current.ndcg_at_k),
    ]


def compare_runs(
    baseline: EvalRunResult,
    current: EvalRunResult,
    regression_threshold: float = 5.0,
) -> ComparisonResult:
    """Compare two evaluation runs.

    Args:
        baseline: Baseline evaluation run
        current: Current evaluation run to compare
        regression_threshold: Percentage threshold for detecting regression (default 5%)

    Returns:
        ComparisonResult with deltas and regression detection

    Raises:
        ValueError: If runs are not comparable (different datasets)
    """
    if baseline.dataset_name != current.dataset_name:
        raise ValueError(f"Cannot compare runs from different datasets: {baseline.dataset_name} vs {current.dataset_name}")

    deltas = compare_metrics(baseline.metrics, current.metrics)

    return ComparisonResult(
        baseline_run_id=baseline.run_id,
        current_run_id=current.run_id,
        dataset_name=baseline.dataset_name,
        deltas=tuple(deltas),
        regression_threshold=regression_threshold,
        metadata={
            "baseline_config": baseline.config,
            "current_config": current.config,
            "baseline_num_samples": baseline.metrics.num_samples,
            "current_num_samples": current.metrics.num_samples,
        },
    )
