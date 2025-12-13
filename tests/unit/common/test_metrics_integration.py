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
        with track_latency(histogram, labels=None):
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

    def test_different_durations_land_in_correct_buckets(self, fresh_registry):
        """Verify different duration values land in the correct histogram buckets."""
        histogram = Histogram(
            "test_buckets_seconds",
            "Test bucket distribution",
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
            registry=fresh_registry,
        )

        # Record a very fast operation (~5ms)
        with track_latency(histogram, labels=None):
            time.sleep(0.005)

        # Record a medium operation (~50ms)
        with track_latency(histogram, labels=None):
            time.sleep(0.05)

        # Record a slower operation (~200ms)
        with track_latency(histogram, labels=None):
            time.sleep(0.2)

        # Verify total count
        count = fresh_registry.get_sample_value("test_buckets_seconds_count")
        assert count == 3

        # Verify bucket distribution (cumulative)
        bucket_10ms = fresh_registry.get_sample_value("test_buckets_seconds_bucket", {"le": "0.01"})
        bucket_100ms = fresh_registry.get_sample_value("test_buckets_seconds_bucket", {"le": "0.1"})
        bucket_500ms = fresh_registry.get_sample_value("test_buckets_seconds_bucket", {"le": "0.5"})

        # First operation (5ms) should be in 10ms bucket
        assert bucket_10ms >= 1
        # First two operations should be in 100ms bucket (5ms + 50ms)
        assert bucket_100ms >= 2
        # All three should be in 500ms bucket
        assert bucket_500ms >= 3

    def test_sum_accumulates_correctly(self, fresh_registry):
        """Verify histogram sum accumulates total duration correctly."""
        histogram = Histogram(
            "test_sum_seconds",
            "Test sum accumulation",
            buckets=BucketConfig.FAST,
            registry=fresh_registry,
        )

        # Record multiple operations with known durations
        durations = [0.01, 0.02, 0.03]  # 10ms, 20ms, 30ms
        for d in durations:
            with track_latency(histogram, labels=None):
                time.sleep(d)

        # Verify count
        count = fresh_registry.get_sample_value("test_sum_seconds_count")
        assert count == 3

        # Verify sum is approximately the total (with tolerance for timing)
        total = fresh_registry.get_sample_value("test_sum_seconds_sum")
        expected_min = sum(durations) * 0.8  # Allow 20% under
        expected_max = sum(durations) * 1.5  # Allow 50% over (timing variance)
        assert expected_min < total < expected_max

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

        with track_latency(histogram, labels=None):
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

        with track_latency(histogram, labels=None):
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

        with pytest.raises(ValueError), track_latency(histogram, labels=None):
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

        with track_latency(histogram, labels=None):
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
        with track_latency(histogram, labels=None):
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


class TestSearchServiceMetrics:
    """Comprehensive tests for Search Service metrics."""

    def test_all_latency_metrics_exist(self):
        """Verify all latency histograms are defined."""
        from src.search_service.metrics import (
            embedding_duration,
            llm_generation_duration,
            request_duration,
            retrieval_duration,
        )

        # All should be Histograms with observe method
        for metric in [request_duration, embedding_duration, retrieval_duration, llm_generation_duration]:
            assert hasattr(metric, "observe") or hasattr(metric, "labels")

    def test_all_counter_metrics_exist(self):
        """Verify all counters are defined."""
        from src.search_service.metrics import errors_total, requests_total

        for metric in [requests_total, errors_total]:
            assert hasattr(metric, "inc") or hasattr(metric, "labels")

    def test_all_gauge_metrics_exist(self):
        """Verify all gauges are defined."""
        from src.search_service.metrics import active_requests

        assert hasattr(active_requests, "inc") or hasattr(active_requests, "labels")

    def test_request_duration_has_method_label(self):
        """Verify request_duration uses method label."""
        from src.search_service.metrics import request_duration

        # Should be usable with method label
        labeled = request_duration.labels(method="Search")
        assert hasattr(labeled, "observe")


class TestEmbeddingServiceMetrics:
    """Comprehensive tests for Embedding Service metrics."""

    def test_all_latency_metrics_exist(self):
        """Verify all latency histograms are defined."""
        from src.embedding_service.metrics import (
            backend_duration,
            batch_size,
            request_duration,
        )

        for metric in [request_duration, backend_duration, batch_size]:
            assert hasattr(metric, "observe") or hasattr(metric, "labels")

    def test_all_counter_metrics_exist(self):
        """Verify all counters are defined."""
        from src.embedding_service.metrics import (
            embeddings_total,
            errors_total,
            requests_total,
        )

        for metric in [requests_total, embeddings_total, errors_total]:
            assert hasattr(metric, "inc") or hasattr(metric, "labels")

    def test_all_gauge_metrics_exist(self):
        """Verify all gauges are defined."""
        from src.embedding_service.metrics import active_requests

        assert hasattr(active_requests, "inc") or hasattr(active_requests, "labels")


class TestIndexerMetrics:
    """Comprehensive tests for Indexer metrics."""

    def test_all_latency_metrics_exist(self):
        """Verify all pipeline stage histograms are defined."""
        from src.indexer.metrics import (
            duplicate_check_duration,
            embedding_duration,
            kafka_poll_duration,
            minio_load_duration,
            processing_duration,
            text_cleaning_duration,
            text_splitting_duration,
            weaviate_insert_duration,
        )

        metrics = [
            processing_duration,
            kafka_poll_duration,
            minio_load_duration,
            text_cleaning_duration,
            text_splitting_duration,
            embedding_duration,
            weaviate_insert_duration,
            duplicate_check_duration,
        ]
        for metric in metrics:
            assert hasattr(metric, "observe") or hasattr(metric, "labels")

    def test_all_counter_metrics_exist(self):
        """Verify all counters are defined."""
        from src.indexer.metrics import (
            chunks_created_total,
            documents_processed_total,
            errors_total,
            kafka_messages_total,
        )

        for metric in [documents_processed_total, chunks_created_total, kafka_messages_total, errors_total]:
            assert hasattr(metric, "inc") or hasattr(metric, "labels")

    def test_all_gauge_metrics_exist(self):
        """Verify all gauges are defined."""
        from src.indexer.metrics import active_documents, kafka_lag

        for metric in [active_documents, kafka_lag]:
            assert hasattr(metric, "inc") or hasattr(metric, "labels") or hasattr(metric, "set")


class TestIngestionAPIMetrics:
    """Comprehensive tests for Ingestion API metrics."""

    def test_all_latency_metrics_exist(self):
        """Verify all latency histograms are defined."""
        from src.ingestion_api.metrics import (
            document_size_bytes,
            kafka_publish_duration,
            minio_upload_duration,
            request_duration,
        )

        for metric in [request_duration, minio_upload_duration, kafka_publish_duration, document_size_bytes]:
            assert hasattr(metric, "observe") or hasattr(metric, "labels")

    def test_all_counter_metrics_exist(self):
        """Verify all counters are defined."""
        from src.ingestion_api.metrics import errors_total, requests_total

        for metric in [requests_total, errors_total]:
            assert hasattr(metric, "inc") or hasattr(metric, "labels")

    def test_all_gauge_metrics_exist(self):
        """Verify all gauges are defined."""
        from src.ingestion_api.metrics import active_requests

        assert hasattr(active_requests, "inc") or hasattr(active_requests, "labels")


class TestSearchUIMetrics:
    """Comprehensive tests for Search UI metrics."""

    def test_all_latency_metrics_exist(self):
        """Verify all latency histograms are defined."""
        from src.search_ui.metrics import (
            grpc_call_duration,
            request_duration,
            sources_returned,
        )

        for metric in [request_duration, grpc_call_duration, sources_returned]:
            assert hasattr(metric, "observe") or hasattr(metric, "labels")

    def test_all_counter_metrics_exist(self):
        """Verify all counters are defined."""
        from src.search_ui.metrics import errors_total, requests_total

        for metric in [requests_total, errors_total]:
            assert hasattr(metric, "inc") or hasattr(metric, "labels")

    def test_all_gauge_metrics_exist(self):
        """Verify all gauges are defined."""
        from src.search_ui.metrics import active_requests

        assert hasattr(active_requests, "inc") or hasattr(active_requests, "labels")
