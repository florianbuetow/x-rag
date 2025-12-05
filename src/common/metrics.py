"""Prometheus metrics helpers for services.

Provides utilities for instrumenting services with Prometheus metrics
following the four golden signals: latency, traffic, errors, saturation.

This module provides:
- BucketConfig: Histogram bucket configurations for different operation types
- OperationType: Enum for categorizing operation latency profiles
- track_latency: Context manager for timing code blocks
- MetricsRegistry: Legacy registry class (kept for backward compatibility)
- track_time/track_counter: Legacy decorators (kept for backward compatibility)
"""

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from enum import Enum
from functools import wraps
from typing import Any, cast

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram


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
    labels: dict[str, str] | None = None,
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


class MetricsRegistry:
    """Registry for service metrics.

    Provides a centralized place to create and manage Prometheus metrics
    for a service.

    Example:
        metrics = MetricsRegistry("search_api")
        metrics.request_counter.labels(method="search", status="success").inc()
        metrics.request_duration.labels(method="search").observe(0.5)
    """

    def __init__(self, service_name: str, registry: CollectorRegistry = REGISTRY) -> None:
        """Initialize metrics registry.

        Args:
            service_name: Service name for metric labels
            registry: Prometheus registry (default: global registry)
        """
        self.service_name = service_name
        self.registry = registry

        # Request metrics
        self.request_counter = Counter(
            f"{service_name}_requests_total",
            "Total number of requests",
            ["method", "status"],
            registry=registry,
        )

        self.request_duration = Histogram(
            f"{service_name}_request_duration_seconds",
            "Request duration in seconds",
            ["method"],
            registry=registry,
        )

        # Error metrics
        self.error_counter = Counter(
            f"{service_name}_errors_total",
            "Total number of errors",
            ["method", "error_type"],
            registry=registry,
        )

        # Active requests
        self.active_requests = Gauge(
            f"{service_name}_active_requests",
            "Number of active requests",
            ["method"],
            registry=registry,
        )

        # Custom metrics can be added as needed
        self._custom_metrics: dict[str, Any] = {}

    def add_counter(self, name: str, description: str, labels: list[str] | None = None) -> Counter:
        """Add a custom counter metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Label names

        Returns:
            Prometheus Counter
        """
        metric_name = f"{self.service_name}_{name}"
        counter = Counter(metric_name, description, labels or [], registry=self.registry)
        self._custom_metrics[name] = counter
        return counter

    def add_histogram(self, name: str, description: str, labels: list[str] | None = None) -> Histogram:
        """Add a custom histogram metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Label names

        Returns:
            Prometheus Histogram
        """
        metric_name = f"{self.service_name}_{name}"
        histogram = Histogram(metric_name, description, labels or [], registry=self.registry)
        self._custom_metrics[name] = histogram
        return histogram

    def add_gauge(self, name: str, description: str, labels: list[str] | None = None) -> Gauge:
        """Add a custom gauge metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Label names

        Returns:
            Prometheus Gauge
        """
        metric_name = f"{self.service_name}_{name}"
        gauge = Gauge(metric_name, description, labels or [], registry=self.registry)
        self._custom_metrics[name] = gauge
        return gauge

    def get_custom(self, name: str) -> Counter | Histogram | Gauge | None:
        """Get a custom metric by name.

        Args:
            name: Metric name

        Returns:
            Prometheus metric object
        """
        return self._custom_metrics.get(name)


def track_time(metrics: MetricsRegistry, method_name: str) -> Callable[..., Any]:
    """Decorator to track function execution time.

    Args:
        metrics: MetricsRegistry instance
        method_name: Method name for labels

    Example:
        @track_time(metrics, "search")
        async def search(query: str):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args: object, **kwargs: object) -> object:
            start = time.time()
            metrics.active_requests.labels(method=method_name).inc()
            try:
                result = await func(*args, **kwargs)
                metrics.request_counter.labels(method=method_name, status="success").inc()
                return result
            except Exception as e:
                metrics.request_counter.labels(method=method_name, status="error").inc()
                metrics.error_counter.labels(method=method_name, error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start
                metrics.request_duration.labels(method=method_name).observe(duration)
                metrics.active_requests.labels(method=method_name).dec()

        @wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            start = time.time()
            metrics.active_requests.labels(method=method_name).inc()
            try:
                result = func(*args, **kwargs)
                metrics.request_counter.labels(method=method_name, status="success").inc()
                return result
            except Exception as e:
                metrics.request_counter.labels(method=method_name, status="error").inc()
                metrics.error_counter.labels(method=method_name, error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start
                metrics.request_duration.labels(method=method_name).observe(duration)
                metrics.active_requests.labels(method=method_name).dec()

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_counter(metrics: MetricsRegistry, method_name: str, counter_name: str = "requests") -> Callable[..., Any]:
    """Decorator to track function calls with a counter.

    Args:
        metrics: MetricsRegistry instance
        method_name: Method name for labels
        counter_name: Name of custom counter metric

    Example:
        @track_counter(metrics, "embed", "embeddings")
        def embed(text: str):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        custom_counter = metrics.get_custom(counter_name)
        counter: Counter = custom_counter if isinstance(custom_counter, Counter) else metrics.request_counter

        @wraps(func)
        async def async_wrapper(*args: object, **kwargs: object) -> object:
            try:
                result = await func(*args, **kwargs)
                counter.labels(method=method_name, status="success").inc()
                return result
            except Exception:
                counter.labels(method=method_name, status="error").inc()
                raise

        @wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            try:
                result = func(*args, **kwargs)
                counter.labels(method=method_name, status="success").inc()
                return result
            except Exception:
                counter.labels(method=method_name, status="error").inc()
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
