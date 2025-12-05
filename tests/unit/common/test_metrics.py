"""Unit tests for src/common/metrics.py.

Tests cover:
- OperationType enum
- BucketConfig class
- track_latency context manager
"""

import pytest
from prometheus_client import CollectorRegistry, Histogram

from src.common.metrics import (
    BucketConfig,
    OperationType,
    track_latency,
)


class TestOperationType:
    """Tests for OperationType enum."""

    def test_operation_type_fast_value(self):
        """Tests that FAST has correct value."""
        assert OperationType.FAST.value == "fast"

    def test_operation_type_medium_value(self):
        """Tests that MEDIUM has correct value."""
        assert OperationType.MEDIUM.value == "medium"

    def test_operation_type_slow_value(self):
        """Tests that SLOW has correct value."""
        assert OperationType.SLOW.value == "slow"

    def test_operation_type_batch_value(self):
        """Tests that BATCH has correct value."""
        assert OperationType.BATCH.value == "batch"

    def test_operation_type_all_values(self):
        """Tests that all operation types are defined."""
        values = {op.value for op in OperationType}
        assert values == {"fast", "medium", "slow", "batch"}


class TestBucketConfig:
    """Tests for BucketConfig class."""

    def test_fast_buckets_defined(self):
        """Tests that FAST buckets are defined."""
        assert BucketConfig.FAST is not None
        assert isinstance(BucketConfig.FAST, tuple)
        assert len(BucketConfig.FAST) > 0

    def test_medium_buckets_defined(self):
        """Tests that MEDIUM buckets are defined."""
        assert BucketConfig.MEDIUM is not None
        assert isinstance(BucketConfig.MEDIUM, tuple)
        assert len(BucketConfig.MEDIUM) > 0

    def test_slow_buckets_defined(self):
        """Tests that SLOW buckets are defined."""
        assert BucketConfig.SLOW is not None
        assert isinstance(BucketConfig.SLOW, tuple)
        assert len(BucketConfig.SLOW) > 0

    def test_batch_buckets_defined(self):
        """Tests that BATCH buckets are defined."""
        assert BucketConfig.BATCH is not None
        assert isinstance(BucketConfig.BATCH, tuple)
        assert len(BucketConfig.BATCH) > 0

    def test_get_fast_buckets(self):
        """Tests that get() returns FAST buckets for FAST operation type."""
        buckets = BucketConfig.get(OperationType.FAST)
        assert buckets == BucketConfig.FAST

    def test_get_medium_buckets(self):
        """Tests that get() returns MEDIUM buckets for MEDIUM operation type."""
        buckets = BucketConfig.get(OperationType.MEDIUM)
        assert buckets == BucketConfig.MEDIUM

    def test_get_slow_buckets(self):
        """Tests that get() returns SLOW buckets for SLOW operation type."""
        buckets = BucketConfig.get(OperationType.SLOW)
        assert buckets == BucketConfig.SLOW

    def test_get_batch_buckets(self):
        """Tests that get() returns BATCH buckets for BATCH operation type."""
        buckets = BucketConfig.get(OperationType.BATCH)
        assert buckets == BucketConfig.BATCH

    def test_fast_buckets_are_sorted(self):
        """Tests that FAST buckets are in ascending order."""
        buckets = BucketConfig.FAST
        assert buckets == tuple(sorted(buckets))

    def test_medium_buckets_are_sorted(self):
        """Tests that MEDIUM buckets are in ascending order."""
        buckets = BucketConfig.MEDIUM
        assert buckets == tuple(sorted(buckets))

    def test_slow_buckets_are_sorted(self):
        """Tests that SLOW buckets are in ascending order."""
        buckets = BucketConfig.SLOW
        assert buckets == tuple(sorted(buckets))

    def test_batch_buckets_are_sorted(self):
        """Tests that BATCH buckets are in ascending order."""
        buckets = BucketConfig.BATCH
        assert buckets == tuple(sorted(buckets))

    def test_fast_buckets_contain_expected_values(self):
        """Tests that FAST buckets contain expected millisecond boundaries."""
        buckets = BucketConfig.FAST
        # Check key boundaries: 5ms, 100ms, 1s
        assert 0.005 in buckets  # 5ms
        assert 0.1 in buckets  # 100ms
        assert 1.0 in buckets  # 1s

    def test_slow_buckets_contain_expected_values(self):
        """Tests that SLOW buckets contain expected second boundaries."""
        buckets = BucketConfig.SLOW
        # Check key boundaries: 100ms, 5s, 30s
        assert 0.1 in buckets  # 100ms
        assert 5.0 in buckets  # 5s
        assert 30.0 in buckets  # 30s


class TestTrackLatencyContextManager:
    """Tests for track_latency context manager."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return CollectorRegistry()

    def test_track_latency_observes_duration(self, registry):
        """Tests that track_latency observes duration to histogram."""
        histogram = Histogram(
            "test_duration_seconds",
            "Test duration",
            registry=registry,
        )

        with track_latency(histogram):
            pass  # Minimal work

        # Check that something was observed
        count = registry.get_sample_value("test_duration_seconds_count")
        assert count == 1

    def test_track_latency_with_labels(self, registry):
        """Tests that track_latency works with labeled histogram."""
        histogram = Histogram(
            "test_labeled_duration_seconds",
            "Test labeled duration",
            ["method"],
            registry=registry,
        )

        with track_latency(histogram, {"method": "search"}):
            pass

        # Should not raise

    def test_track_latency_propagates_exception(self, registry):
        """Tests that track_latency propagates exceptions."""
        histogram = Histogram(
            "test_error_duration_seconds",
            "Test error duration",
            registry=registry,
        )

        with pytest.raises(ValueError, match="Test error"), track_latency(histogram):
            raise ValueError("Test error")

    def test_track_latency_records_even_on_exception(self, registry):
        """Tests that track_latency records duration even when exception occurs."""
        histogram = Histogram(
            "test_exception_duration_seconds",
            "Test exception duration",
            registry=registry,
        )

        with pytest.raises(ValueError), track_latency(histogram):
            raise ValueError("Error")

        # Duration should have been recorded despite exception
        count = registry.get_sample_value("test_exception_duration_seconds_count")
        assert count == 1

    def test_track_latency_measures_reasonable_duration(self, registry):
        """Tests that track_latency measures reasonable durations."""
        import time

        histogram = Histogram(
            "test_sleep_duration_seconds",
            "Test sleep duration",
            buckets=(0.01, 0.05, 0.1, 0.5),
            registry=registry,
        )

        with track_latency(histogram):
            time.sleep(0.05)  # Sleep 50ms

        # Check that the recorded value is in the expected range
        count = registry.get_sample_value("test_sleep_duration_seconds_count")
        assert count == 1

        # Sum should be approximately 0.05 seconds (with some tolerance)
        sum_value = registry.get_sample_value("test_sleep_duration_seconds_sum")
        assert sum_value is not None
        assert 0.04 < sum_value < 0.15  # Allow for some variation

    def test_track_latency_without_labels(self, registry):
        """Tests that track_latency works without labels."""
        histogram = Histogram(
            "test_no_labels_duration_seconds",
            "Test no labels duration",
            registry=registry,
        )

        with track_latency(histogram):
            pass

        count = registry.get_sample_value("test_no_labels_duration_seconds_count")
        assert count == 1

    def test_track_latency_multiple_calls(self, registry):
        """Tests that track_latency accumulates multiple observations."""
        histogram = Histogram(
            "test_multi_duration_seconds",
            "Test multi duration",
            registry=registry,
        )

        for _ in range(3):
            with track_latency(histogram):
                pass

        count = registry.get_sample_value("test_multi_duration_seconds_count")
        assert count == 3
