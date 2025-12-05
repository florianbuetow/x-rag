"""Integration tests for service metrics recording.

These tests verify that metrics are actually recorded when operations occur,
not just that the metrics API exists.
"""

import time

import pytest
from prometheus_client import CollectorRegistry, Histogram

from src.common.metrics import BucketConfig, OperationType, track_latency


class TestMetricsRecording:
    """Tests that verify metrics are actually recorded."""

    @pytest.fixture
    def fresh_registry(self):
        """Create a fresh registry for each test to avoid metric conflicts."""
        return CollectorRegistry()

    def test_track_latency_records_correct_bucket(self, fresh_registry):
        """Verify track_latency records duration in correct histogram bucket."""
        histogram = Histogram(
            "test_operation_seconds",
            "Test operation duration",
            buckets=BucketConfig.FAST,
            registry=fresh_registry,
        )

        # Sleep for 50ms (0.05s) - should fall in bucket 0.05 or 0.1
        with track_latency(histogram):
            time.sleep(0.05)

        # Verify observation was recorded
        count = fresh_registry.get_sample_value("test_operation_seconds_count")
        assert count == 1

        # Verify duration is in expected range (0.05s with some tolerance)
        total = fresh_registry.get_sample_value("test_operation_seconds_sum")
        assert total is not None
        assert 0.04 < total < 0.15  # Allow for timing variance

        # Verify bucket distribution - should be in bucket ≤0.1
        bucket_0_1 = fresh_registry.get_sample_value("test_operation_seconds_bucket", {"le": "0.1"})
        # Due to timing variance, should definitely be in 0.1 bucket
        assert bucket_0_1 >= 1

    def test_labeled_histogram_records_per_label(self, fresh_registry):
        """Verify labeled histograms record separately per label value."""
        histogram = Histogram(
            "test_labeled_seconds",
            "Test labeled duration",
            ["method"],
            buckets=BucketConfig.FAST,
            registry=fresh_registry,
        )

        # Record for "search" method
        with track_latency(histogram, {"method": "search"}):
            time.sleep(0.01)

        # Record twice for "embed" method
        with track_latency(histogram, {"method": "embed"}):
            time.sleep(0.01)
        with track_latency(histogram, {"method": "embed"}):
            time.sleep(0.01)

        # Verify counts per label
        search_count = fresh_registry.get_sample_value("test_labeled_seconds_count", {"method": "search"})
        embed_count = fresh_registry.get_sample_value("test_labeled_seconds_count", {"method": "embed"})

        assert search_count == 1
        assert embed_count == 2

    def test_histogram_buckets_match_config(self, fresh_registry):
        """Verify histogram uses configured buckets."""
        histogram = Histogram(
            "test_slow_seconds",
            "Test slow operation",
            buckets=BucketConfig.SLOW,
            registry=fresh_registry,
        )

        with track_latency(histogram):
            pass  # Minimal work

        # Verify SLOW bucket boundaries exist
        for bucket_le in ["0.1", "0.25", "0.5", "1.0", "5.0", "30.0"]:
            value = fresh_registry.get_sample_value("test_slow_seconds_bucket", {"le": bucket_le})
            assert value is not None, f"Missing bucket le={bucket_le}"

    def test_fast_operations_use_millisecond_precision(self, fresh_registry):
        """Verify FAST buckets capture sub-millisecond operations."""
        histogram = Histogram(
            "test_fast_seconds",
            "Test fast operation",
            buckets=BucketConfig.FAST,
            registry=fresh_registry,
        )

        with track_latency(histogram):
            pass  # Should be < 5ms

        # Verify recorded in smallest bucket (0.005s = 5ms)
        bucket_5ms = fresh_registry.get_sample_value("test_fast_seconds_bucket", {"le": "0.005"})
        assert bucket_5ms is not None
        assert bucket_5ms >= 1  # Should be captured in 5ms bucket

    def test_track_latency_records_on_exception(self, fresh_registry):
        """Verify latency is recorded even when operation raises exception."""
        histogram = Histogram(
            "test_error_seconds",
            "Test error operation",
            buckets=BucketConfig.FAST,
            registry=fresh_registry,
        )

        with pytest.raises(ValueError), track_latency(histogram):
            time.sleep(0.02)
            raise ValueError("Test error")

        # Should still have recorded the duration
        count = fresh_registry.get_sample_value("test_error_seconds_count")
        assert count == 1

        total = fresh_registry.get_sample_value("test_error_seconds_sum")
        assert total is not None
        assert total >= 0.02


class TestBucketConfigCorrectness:
    """Tests that bucket configurations are correct for their use cases."""

    def test_fast_buckets_cover_expected_range(self):
        """FAST buckets should cover 5ms to 5s range."""
        buckets = BucketConfig.FAST
        assert min(buckets) == 0.005  # 5ms
        assert max(buckets) == 5.0  # 5s
        assert 0.1 in buckets  # 100ms (target p99)

    def test_medium_buckets_cover_expected_range(self):
        """MEDIUM buckets should cover 10ms to 10s range."""
        buckets = BucketConfig.MEDIUM
        assert min(buckets) == 0.01  # 10ms
        assert max(buckets) == 10.0  # 10s
        assert 0.5 in buckets  # 500ms (target p99)

    def test_slow_buckets_cover_expected_range(self):
        """SLOW buckets should cover 100ms to 60s range."""
        buckets = BucketConfig.SLOW
        assert min(buckets) == 0.1  # 100ms
        assert max(buckets) == 60.0  # 60s
        assert 30.0 in buckets  # 30s (target p99)

    def test_batch_buckets_cover_expected_range(self):
        """BATCH buckets should cover 50ms to 60s range."""
        buckets = BucketConfig.BATCH
        assert min(buckets) == 0.05  # 50ms
        assert max(buckets) == 60.0  # 60s
        assert 5.0 in buckets  # 5s (target p99)

    def test_operation_type_mapping(self):
        """Verify OperationType maps correctly to buckets."""
        assert BucketConfig.get(OperationType.FAST) == BucketConfig.FAST
        assert BucketConfig.get(OperationType.MEDIUM) == BucketConfig.MEDIUM
        assert BucketConfig.get(OperationType.SLOW) == BucketConfig.SLOW
        assert BucketConfig.get(OperationType.BATCH) == BucketConfig.BATCH


class TestPrometheusExposition:
    """Tests for Prometheus metrics exposition format."""

    @pytest.fixture
    def fresh_registry(self):
        """Create a fresh registry for each test."""
        return CollectorRegistry()

    def test_histogram_exposition_format(self, fresh_registry):
        """Verify histogram exposes _bucket, _count, _sum metrics."""
        histogram = Histogram(
            "test_exposition_seconds",
            "Test exposition",
            buckets=BucketConfig.FAST,
            registry=fresh_registry,
        )

        with track_latency(histogram):
            pass

        # Verify all required metric components exist
        assert fresh_registry.get_sample_value("test_exposition_seconds_count") is not None
        assert fresh_registry.get_sample_value("test_exposition_seconds_sum") is not None
        assert fresh_registry.get_sample_value("test_exposition_seconds_bucket", {"le": "+Inf"}) is not None

    def test_histogram_bucket_cumulative(self, fresh_registry):
        """Verify histogram buckets are cumulative (as required by Prometheus)."""
        histogram = Histogram(
            "test_cumulative_seconds",
            "Test cumulative",
            buckets=(0.1, 0.5, 1.0),
            registry=fresh_registry,
        )

        # Record a value that should be in middle bucket
        with track_latency(histogram):
            time.sleep(0.2)  # ~200ms

        bucket_0_1 = fresh_registry.get_sample_value("test_cumulative_seconds_bucket", {"le": "0.1"})
        bucket_0_5 = fresh_registry.get_sample_value("test_cumulative_seconds_bucket", {"le": "0.5"})
        bucket_1_0 = fresh_registry.get_sample_value("test_cumulative_seconds_bucket", {"le": "1.0"})
        bucket_inf = fresh_registry.get_sample_value("test_cumulative_seconds_bucket", {"le": "+Inf"})

        # Buckets should be cumulative
        assert bucket_0_1 <= bucket_0_5 <= bucket_1_0 <= bucket_inf
        # Value 0.2s should be in 0.5 bucket but not 0.1
        assert bucket_0_1 == 0  # Not in 100ms bucket
        assert bucket_0_5 >= 1  # Should be in 500ms bucket


class TestServiceMetricsImport:
    """Tests that service metrics modules can be imported and used."""

    def test_search_service_metrics_importable(self):
        """Verify search service metrics can be imported."""
        from src.search_service.metrics import (
            active_requests,
            errors_total,
            request_duration,
            requests_total,
        )

        # Verify they're the right types
        assert hasattr(request_duration, "observe") or hasattr(request_duration, "labels")
        assert hasattr(requests_total, "labels")
        assert hasattr(errors_total, "labels")
        assert hasattr(active_requests, "labels")

    def test_embedding_service_metrics_importable(self):
        """Verify embedding service metrics can be imported."""
        from src.embedding_service.metrics import (
            request_duration,
            requests_total,
        )

        assert hasattr(request_duration, "labels")
        assert hasattr(requests_total, "labels")

    def test_indexer_metrics_importable(self):
        """Verify indexer metrics can be imported."""
        from src.indexer.metrics import (
            documents_processed_total,
            processing_duration,
        )

        assert hasattr(processing_duration, "labels")
        assert hasattr(documents_processed_total, "labels")

    def test_ingestion_api_metrics_importable(self):
        """Verify ingestion API metrics can be imported."""
        from src.ingestion_api.metrics import (
            request_duration,
            requests_total,
        )

        assert hasattr(request_duration, "labels")
        assert hasattr(requests_total, "labels")

    def test_search_ui_metrics_importable(self):
        """Verify search UI metrics can be imported."""
        from src.search_ui.metrics import (
            request_duration,
            requests_total,
        )

        assert hasattr(request_duration, "labels")
        assert hasattr(requests_total, "labels")
