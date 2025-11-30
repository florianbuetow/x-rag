"""Prometheus metrics helpers for services.

Provides utilities for instrumenting services with Prometheus metrics.
"""

import time
from functools import wraps
from typing import Callable, Any

from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, REGISTRY


class MetricsRegistry:
    """Registry for service metrics.

    Provides a centralized place to create and manage Prometheus metrics
    for a service.

    Example:
        metrics = MetricsRegistry("search_api")
        metrics.request_counter.labels(method="search", status="success").inc()
        metrics.request_duration.labels(method="search").observe(0.5)
    """

    def __init__(self, service_name: str, registry: CollectorRegistry = REGISTRY):
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

    def add_counter(self, name: str, description: str, labels: list[str] = None) -> Counter:
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

    def add_histogram(
        self, name: str, description: str, labels: list[str] = None
    ) -> Histogram:
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

    def add_gauge(self, name: str, description: str, labels: list[str] = None) -> Gauge:
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

    def get_custom(self, name: str) -> Any:
        """Get a custom metric by name.

        Args:
            name: Metric name

        Returns:
            Prometheus metric object
        """
        return self._custom_metrics.get(name)


def track_time(metrics: MetricsRegistry, method_name: str):
    """Decorator to track function execution time.

    Args:
        metrics: MetricsRegistry instance
        method_name: Method name for labels

    Example:
        @track_time(metrics, "search")
        async def search(query: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            metrics.active_requests.labels(method=method_name).inc()
            try:
                result = await func(*args, **kwargs)
                metrics.request_counter.labels(method=method_name, status="success").inc()
                return result
            except Exception as e:
                metrics.request_counter.labels(method=method_name, status="error").inc()
                metrics.error_counter.labels(
                    method=method_name, error_type=type(e).__name__
                ).inc()
                raise
            finally:
                duration = time.time() - start
                metrics.request_duration.labels(method=method_name).observe(duration)
                metrics.active_requests.labels(method=method_name).dec()

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            metrics.active_requests.labels(method=method_name).inc()
            try:
                result = func(*args, **kwargs)
                metrics.request_counter.labels(method=method_name, status="success").inc()
                return result
            except Exception as e:
                metrics.request_counter.labels(method=method_name, status="error").inc()
                metrics.error_counter.labels(
                    method=method_name, error_type=type(e).__name__
                ).inc()
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


def track_counter(metrics: MetricsRegistry, method_name: str, counter_name: str = "requests"):
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

    def decorator(func: Callable) -> Callable:
        counter = metrics.get_custom(counter_name) or metrics.request_counter

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                counter.labels(method=method_name, status="success").inc()
                return result
            except Exception:
                counter.labels(method=method_name, status="error").inc()
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
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
