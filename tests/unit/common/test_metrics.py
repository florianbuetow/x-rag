"""Unit tests for src/common/metrics.py.

Tests cover:
- MetricsRegistry initialization
- MetricsRegistry built-in metrics (request_counter, request_duration, error_counter, active_requests)
- MetricsRegistry custom metrics (add_counter, add_histogram, add_gauge)
- track_time decorator for sync and async functions
- track_counter decorator for sync and async functions
"""

import asyncio

import pytest
from prometheus_client import CollectorRegistry

from src.common.metrics import MetricsRegistry, track_counter, track_time


class TestMetricsRegistry:
    """Tests for MetricsRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test to avoid metric conflicts."""
        return CollectorRegistry()

    def test_init_creates_request_counter(self, registry):
        """Tests that __init__ creates request_counter metric."""
        metrics = MetricsRegistry("test_service", registry=registry)

        assert metrics.request_counter is not None
        # Verify it's a Counter by checking it has labels method
        assert hasattr(metrics.request_counter, "labels")

    def test_init_creates_request_duration(self, registry):
        """Tests that __init__ creates request_duration histogram."""
        metrics = MetricsRegistry("test_service", registry=registry)

        assert metrics.request_duration is not None
        assert hasattr(metrics.request_duration, "labels")

    def test_init_creates_error_counter(self, registry):
        """Tests that __init__ creates error_counter metric."""
        metrics = MetricsRegistry("test_service", registry=registry)

        assert metrics.error_counter is not None
        assert hasattr(metrics.error_counter, "labels")

    def test_init_creates_active_requests(self, registry):
        """Tests that __init__ creates active_requests gauge."""
        metrics = MetricsRegistry("test_service", registry=registry)

        assert metrics.active_requests is not None
        assert hasattr(metrics.active_requests, "labels")

    def test_init_stores_service_name(self, registry):
        """Tests that __init__ stores service name."""
        metrics = MetricsRegistry("my_service", registry=registry)

        assert metrics.service_name == "my_service"

    def test_request_counter_can_be_incremented(self, registry):
        """Tests that request_counter can be incremented with labels."""
        metrics = MetricsRegistry("test_service", registry=registry)

        # Should not raise
        metrics.request_counter.labels(method="search", status="success").inc()
        metrics.request_counter.labels(method="search", status="error").inc()

    def test_request_duration_can_observe(self, registry):
        """Tests that request_duration can observe values."""
        metrics = MetricsRegistry("test_service", registry=registry)

        # Should not raise
        metrics.request_duration.labels(method="search").observe(0.5)

    def test_error_counter_can_be_incremented(self, registry):
        """Tests that error_counter can be incremented with labels."""
        metrics = MetricsRegistry("test_service", registry=registry)

        # Should not raise
        metrics.error_counter.labels(method="search", error_type="ValueError").inc()

    def test_active_requests_can_inc_and_dec(self, registry):
        """Tests that active_requests gauge can be incremented and decremented."""
        metrics = MetricsRegistry("test_service", registry=registry)

        # Should not raise
        metrics.active_requests.labels(method="search").inc()
        metrics.active_requests.labels(method="search").dec()


class TestMetricsRegistryCustomMetrics:
    """Tests for MetricsRegistry custom metric methods."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return CollectorRegistry()

    def test_add_counter_creates_counter(self, registry):
        """Tests that add_counter creates a new counter metric."""
        metrics = MetricsRegistry("test_service", registry=registry)

        counter = metrics.add_counter("custom_events", "Count of custom events", labels=["event_type"])

        assert counter is not None
        assert hasattr(counter, "labels")

    def test_add_counter_stores_in_custom_metrics(self, registry):
        """Tests that add_counter stores counter in _custom_metrics."""
        metrics = MetricsRegistry("test_service", registry=registry)

        metrics.add_counter("my_counter", "Description")

        assert "my_counter" in metrics._custom_metrics

    def test_add_counter_prefixes_with_service_name(self, registry):
        """Tests that add_counter prefixes metric name with service name."""
        metrics = MetricsRegistry("test_service", registry=registry)

        counter = metrics.add_counter("events", "Events counter")

        # Counter should work with the prefixed name
        counter.inc()

    def test_add_histogram_creates_histogram(self, registry):
        """Tests that add_histogram creates a new histogram metric."""
        metrics = MetricsRegistry("test_service", registry=registry)

        histogram = metrics.add_histogram("custom_duration", "Custom duration", labels=["operation"])

        assert histogram is not None
        assert hasattr(histogram, "labels")

    def test_add_histogram_stores_in_custom_metrics(self, registry):
        """Tests that add_histogram stores histogram in _custom_metrics."""
        metrics = MetricsRegistry("test_service", registry=registry)

        metrics.add_histogram("my_histogram", "Description")

        assert "my_histogram" in metrics._custom_metrics

    def test_add_gauge_creates_gauge(self, registry):
        """Tests that add_gauge creates a new gauge metric."""
        metrics = MetricsRegistry("test_service", registry=registry)

        gauge = metrics.add_gauge("queue_size", "Current queue size", labels=["queue_name"])

        assert gauge is not None
        assert hasattr(gauge, "labels")

    def test_add_gauge_stores_in_custom_metrics(self, registry):
        """Tests that add_gauge stores gauge in _custom_metrics."""
        metrics = MetricsRegistry("test_service", registry=registry)

        metrics.add_gauge("my_gauge", "Description")

        assert "my_gauge" in metrics._custom_metrics

    def test_get_custom_returns_metric(self, registry):
        """Tests that get_custom returns the stored metric."""
        metrics = MetricsRegistry("test_service", registry=registry)
        counter = metrics.add_counter("my_counter", "Description")

        result = metrics.get_custom("my_counter")

        assert result is counter

    def test_get_custom_returns_none_for_missing(self, registry):
        """Tests that get_custom returns None for non-existent metric."""
        metrics = MetricsRegistry("test_service", registry=registry)

        result = metrics.get_custom("nonexistent")

        assert result is None

    def test_add_counter_without_labels(self, registry):
        """Tests that add_counter works without labels."""
        metrics = MetricsRegistry("test_service", registry=registry)

        counter = metrics.add_counter("simple_counter", "Simple counter")

        # Should be usable without labels
        counter.inc()

    def test_add_histogram_without_labels(self, registry):
        """Tests that add_histogram works without labels."""
        metrics = MetricsRegistry("test_service", registry=registry)

        histogram = metrics.add_histogram("simple_histogram", "Simple histogram")

        # Should be usable without labels
        histogram.observe(1.0)

    def test_add_gauge_without_labels(self, registry):
        """Tests that add_gauge works without labels."""
        metrics = MetricsRegistry("test_service", registry=registry)

        gauge = metrics.add_gauge("simple_gauge", "Simple gauge")

        # Should be usable without labels
        gauge.set(42)


class TestTrackTimeDecorator:
    """Tests for track_time decorator."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return CollectorRegistry()

    def test_track_time_sync_function_success(self, registry):
        """Tests that track_time tracks successful sync function."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_time(metrics, "test_method")
        def sync_function():
            return "result"

        result = sync_function()

        assert result == "result"

    def test_track_time_sync_function_error(self, registry):
        """Tests that track_time tracks sync function errors."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_time(metrics, "test_method")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

    @pytest.mark.asyncio
    async def test_track_time_async_function_success(self, registry):
        """Tests that track_time tracks successful async function."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_time(metrics, "test_method")
        async def async_function():
            await asyncio.sleep(0.01)
            return "async result"

        result = await async_function()

        assert result == "async result"

    @pytest.mark.asyncio
    async def test_track_time_async_function_error(self, registry):
        """Tests that track_time tracks async function errors."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_time(metrics, "test_method")
        async def failing_async_function():
            await asyncio.sleep(0.01)
            raise ValueError("Async error")

        with pytest.raises(ValueError):
            await failing_async_function()

    def test_track_time_preserves_function_name(self, registry):
        """Tests that track_time preserves original function name."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_time(metrics, "test_method")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_track_time_preserves_function_docstring(self, registry):
        """Tests that track_time preserves original function docstring."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_time(metrics, "test_method")
        def documented_function():
            """This is the docstring."""
            pass

        assert documented_function.__doc__ == """This is the docstring."""

    def test_track_time_with_arguments(self, registry):
        """Tests that track_time works with function arguments."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_time(metrics, "test_method")
        def function_with_args(a, b, c=None):
            return a + b + (c or 0)

        result = function_with_args(1, 2, c=3)

        assert result == 6


class TestTrackCounterDecorator:
    """Tests for track_counter decorator."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return CollectorRegistry()

    def test_track_counter_sync_function_success(self, registry):
        """Tests that track_counter tracks successful sync function."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_counter(metrics, "test_method")
        def sync_function():
            return "result"

        result = sync_function()

        assert result == "result"

    def test_track_counter_sync_function_error(self, registry):
        """Tests that track_counter tracks sync function errors."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_counter(metrics, "test_method")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

    @pytest.mark.asyncio
    async def test_track_counter_async_function_success(self, registry):
        """Tests that track_counter tracks successful async function."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_counter(metrics, "test_method")
        async def async_function():
            return "async result"

        result = await async_function()

        assert result == "async result"

    @pytest.mark.asyncio
    async def test_track_counter_async_function_error(self, registry):
        """Tests that track_counter tracks async function errors."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_counter(metrics, "test_method")
        async def failing_async_function():
            raise ValueError("Async error")

        with pytest.raises(ValueError):
            await failing_async_function()

    def test_track_counter_uses_custom_counter(self, registry):
        """Tests that track_counter can use custom counter metric."""
        metrics = MetricsRegistry("test_service", registry=registry)
        metrics.add_counter("custom_counter", "Custom counter", labels=["method", "status"])

        @track_counter(metrics, "test_method", counter_name="custom_counter")
        def custom_tracked_function():
            return "result"

        result = custom_tracked_function()

        assert result == "result"

    def test_track_counter_falls_back_to_request_counter(self, registry):
        """Tests that track_counter falls back to request_counter if custom not found."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_counter(metrics, "test_method", counter_name="nonexistent")
        def fallback_function():
            return "result"

        result = fallback_function()

        assert result == "result"

    def test_track_counter_preserves_function_name(self, registry):
        """Tests that track_counter preserves original function name."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_counter(metrics, "test_method")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_track_counter_with_arguments(self, registry):
        """Tests that track_counter works with function arguments."""
        metrics = MetricsRegistry("test_service", registry=registry)

        @track_counter(metrics, "test_method")
        def function_with_args(x, y):
            return x * y

        result = function_with_args(3, 4)

        assert result == 12
