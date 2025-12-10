"""Prometheus metrics helpers for services.

Provides utilities for instrumenting services with Prometheus metrics
following the four golden signals: latency, traffic, errors, saturation.

This module provides:
- BucketConfig: Histogram bucket configurations for different operation types
- OperationType: Enum for categorizing operation latency profiles
- track_latency: Context manager for timing code blocks
"""

import time
from collections.abc import Generator
from contextlib import contextmanager
from enum import Enum
from typing import cast

from prometheus_client import Histogram


class OperationType(Enum):
    """Operation latency profiles for bucket selection.

    Use these to categorize operations by their expected latency:
    - FAST: Operations completing in < 100ms (embeddings, cache lookups)
    - MEDIUM: Operations completing in < 500ms (DB queries, text processing)
    - SLOW: Operations completing in < 30s (LLM generation, full pipelines)
    - BATCH: Batch operations completing in < 5s (Kafka consume, batch embedding)
    """

    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    BATCH = "batch"


class BucketConfig:
    """Histogram bucket configurations for different operation types.

    Each bucket tuple defines the upper bounds (in seconds) for histogram buckets.
    Prometheus will automatically add a +Inf bucket.

    Example:
        buckets = BucketConfig.get(OperationType.FAST)
        histogram = Histogram("my_metric", "desc", buckets=buckets)
    """

    # Fast operations: embedding, cache lookups (target p99 < 100ms)
    # Buckets: 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s
    FAST: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

    # Medium operations: Weaviate retrieval, text processing (target p99 < 500ms)
    # Buckets: 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s
    MEDIUM: tuple[float, ...] = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    # Slow operations: LLM generation, full pipeline (target p99 < 30s)
    # Buckets: 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s, 20s, 30s, 60s
    SLOW: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0)

    # Batch operations: Kafka consume, batch embedding (target p99 < 5s)
    # Buckets: 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s, 30s, 60s
    BATCH: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

    @classmethod
    def get(cls, op_type: OperationType) -> tuple[float, ...]:
        """Get bucket configuration for an operation type.

        Args:
            op_type: The operation type

        Returns:
            Tuple of bucket upper bounds in seconds
        """
        return cast(tuple[float, ...], getattr(cls, op_type.value.upper()))


@contextmanager
def track_latency(
    histogram: Histogram,
    labels: dict[str, str] | None,
) -> Generator[None, None, None]:
    """Context manager to track operation latency with a histogram.

    Measures the duration of the code block and records it to the histogram.
    Uses time.perf_counter() for high-precision timing.

    Args:
        histogram: Prometheus Histogram to record the duration
        labels: Optional dict of label names to values

    Example:
        # Without labels
        with track_latency(my_histogram):
            do_something()

        # With labels
        with track_latency(my_histogram, {"method": "search", "mode": "hybrid"}):
            do_something()

    Yields:
        None
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if labels:
            histogram.labels(**labels).observe(duration)
        else:
            histogram.observe(duration)
