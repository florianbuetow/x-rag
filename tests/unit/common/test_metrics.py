"""Unit tests for src/common/metrics.py.

Tests cover:
- OperationType enum
- get_buckets function
- track_latency context manager with OTel histograms
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.common.metrics import (
    HISTOGRAM_BUCKETS,
    OperationType,
    get_buckets,
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


class TestGetBuckets:
    """Tests for get_buckets function."""

    def test_get_fast_buckets(self):
        """Tests that get_buckets returns FAST buckets for FAST operation type."""
        buckets = get_buckets(OperationType.FAST)
        assert buckets == HISTOGRAM_BUCKETS[OperationType.FAST]

    def test_get_medium_buckets(self):
        """Tests that get_buckets returns MEDIUM buckets for MEDIUM operation type."""
        buckets = get_buckets(OperationType.MEDIUM)
        assert buckets == HISTOGRAM_BUCKETS[OperationType.MEDIUM]

    def test_get_slow_buckets(self):
        """Tests that get_buckets returns SLOW buckets for SLOW operation type."""
        buckets = get_buckets(OperationType.SLOW)
        assert buckets == HISTOGRAM_BUCKETS[OperationType.SLOW]

    def test_get_batch_buckets(self):
        """Tests that get_buckets returns BATCH buckets for BATCH operation type."""
        buckets = get_buckets(OperationType.BATCH)
        assert buckets == HISTOGRAM_BUCKETS[OperationType.BATCH]

    def test_fast_buckets_are_sorted(self):
        """Tests that FAST buckets are in ascending order."""
        buckets = get_buckets(OperationType.FAST)
        assert buckets == tuple(sorted(buckets))

    def test_medium_buckets_are_sorted(self):
        """Tests that MEDIUM buckets are in ascending order."""
        buckets = get_buckets(OperationType.MEDIUM)
        assert buckets == tuple(sorted(buckets))

    def test_slow_buckets_are_sorted(self):
        """Tests that SLOW buckets are in ascending order."""
        buckets = get_buckets(OperationType.SLOW)
        assert buckets == tuple(sorted(buckets))

    def test_batch_buckets_are_sorted(self):
        """Tests that BATCH buckets are in ascending order."""
        buckets = get_buckets(OperationType.BATCH)
        assert buckets == tuple(sorted(buckets))

    def test_fast_buckets_contain_expected_values(self):
        """Tests that FAST buckets contain expected millisecond boundaries."""
        buckets = get_buckets(OperationType.FAST)
        # Check key boundaries: 5ms, 100ms
        assert 0.005 in buckets  # 5ms
        assert 0.1 in buckets  # 100ms

    def test_slow_buckets_contain_expected_values(self):
        """Tests that SLOW buckets contain expected second boundaries."""
        buckets = get_buckets(OperationType.SLOW)
        # Check key boundaries: 100ms, 5s, 30s
        assert 0.1 in buckets  # 100ms
        assert 5.0 in buckets  # 5s
        assert 30.0 in buckets  # 30s


class TestTrackLatencyContextManager:
    """Tests for track_latency context manager."""

    def test_track_latency_records_duration(self):
        """Tests that track_latency calls histogram.record()."""
        mock_histogram = MagicMock()

        with track_latency(mock_histogram, {}):
            pass

        mock_histogram.record.assert_called_once()
        # Duration should be a positive float
        call_args = mock_histogram.record.call_args
        duration = call_args[0][0]
        assert isinstance(duration, float)
        assert duration >= 0

    def test_track_latency_with_attributes(self):
        """Tests that track_latency passes attributes."""
        mock_histogram = MagicMock()
        attrs = {"method": "Search"}

        with track_latency(mock_histogram, attrs):
            pass

        call_args = mock_histogram.record.call_args
        passed_attrs = call_args[0][1]
        assert passed_attrs == attrs

    def test_track_latency_propagates_exception(self):
        """Tests that track_latency propagates exceptions."""
        mock_histogram = MagicMock()

        with pytest.raises(ValueError, match="Test error"):
            with track_latency(mock_histogram, {}):
                raise ValueError("Test error")

    def test_track_latency_records_even_on_exception(self):
        """Tests that track_latency records duration even when exception occurs."""
        mock_histogram = MagicMock()

        with pytest.raises(ValueError):
            with track_latency(mock_histogram, {}):
                raise ValueError("Error")

        # Duration should have been recorded despite exception
        mock_histogram.record.assert_called_once()

    def test_track_latency_measures_reasonable_duration(self):
        """Tests that track_latency measures reasonable durations."""
        mock_histogram = MagicMock()

        with track_latency(mock_histogram, {}):
            time.sleep(0.05)  # Sleep 50ms

        call_args = mock_histogram.record.call_args
        duration = call_args[0][0]
        # Should be approximately 0.05 seconds (with tolerance)
        assert 0.04 < duration < 0.15

    def test_track_latency_none_attributes(self):
        """Tests that track_latency works with None attributes."""
        mock_histogram = MagicMock()

        with track_latency(mock_histogram, None):
            pass

        call_args = mock_histogram.record.call_args
        passed_attrs = call_args[0][1]
        assert passed_attrs == {}

    def test_track_latency_multiple_calls(self):
        """Tests that track_latency can be called multiple times."""
        mock_histogram = MagicMock()

        for _ in range(3):
            with track_latency(mock_histogram, {}):
                pass

        assert mock_histogram.record.call_count == 3
