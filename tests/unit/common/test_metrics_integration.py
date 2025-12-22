"""Integration tests for OTel service metrics.

These tests verify that metric modules can be imported and metrics
are properly created with the OTel SDK.
"""

from src.common.metrics import OperationType, get_buckets


class TestBucketConfig:
    """Tests for histogram bucket configuration."""

    def test_fast_buckets_defined(self):
        """Tests that FAST buckets are defined."""
        buckets = get_buckets(OperationType.FAST)
        assert buckets is not None
        assert isinstance(buckets, tuple)
        assert len(buckets) > 0

    def test_medium_buckets_defined(self):
        """Tests that MEDIUM buckets are defined."""
        buckets = get_buckets(OperationType.MEDIUM)
        assert buckets is not None
        assert isinstance(buckets, tuple)
        assert len(buckets) > 0

    def test_slow_buckets_defined(self):
        """Tests that SLOW buckets are defined."""
        buckets = get_buckets(OperationType.SLOW)
        assert buckets is not None
        assert isinstance(buckets, tuple)
        assert len(buckets) > 0

    def test_batch_buckets_defined(self):
        """Tests that BATCH buckets are defined."""
        buckets = get_buckets(OperationType.BATCH)
        assert buckets is not None
        assert isinstance(buckets, tuple)
        assert len(buckets) > 0

    def test_fast_buckets_cover_expected_range(self):
        """Tests FAST buckets cover millisecond-scale operations."""
        buckets = get_buckets(OperationType.FAST)
        assert min(buckets) <= 0.01  # Covers 10ms or faster
        assert max(buckets) <= 1.0  # Max 1 second

    def test_medium_buckets_cover_expected_range(self):
        """Tests MEDIUM buckets cover sub-second operations."""
        buckets = get_buckets(OperationType.MEDIUM)
        assert min(buckets) <= 0.1  # Covers 100ms
        assert max(buckets) >= 1.0  # At least 1 second

    def test_slow_buckets_cover_expected_range(self):
        """Tests SLOW buckets cover multi-second operations."""
        buckets = get_buckets(OperationType.SLOW)
        assert max(buckets) >= 10.0  # At least 10 seconds

    def test_batch_buckets_cover_expected_range(self):
        """Tests BATCH buckets cover batch processing operations."""
        buckets = get_buckets(OperationType.BATCH)
        assert max(buckets) >= 5.0  # At least 5 seconds


class TestServiceMetricsImport:
    """Tests that service metrics modules can be imported."""

    def test_search_service_metrics_importable(self):
        """Tests search_service metrics can be imported."""
        from src.search_service.metrics import (
            get_request_duration,
            inc_requests_total,
        )

        assert callable(get_request_duration)
        assert callable(inc_requests_total)

    def test_embedding_service_metrics_importable(self):
        """Tests embedding_service metrics can be imported."""
        from src.embedding_service.metrics import (
            get_request_duration,
            inc_requests_total,
        )

        assert callable(get_request_duration)
        assert callable(inc_requests_total)

    def test_indexer_metrics_importable(self):
        """Tests indexer metrics can be imported."""
        from src.indexer.metrics import (
            get_processing_duration,
            inc_documents_processed_total,
        )

        assert callable(get_processing_duration)
        assert callable(inc_documents_processed_total)

    def test_ingestion_api_metrics_importable(self):
        """Tests ingestion_api metrics can be imported."""
        from src.ingestion_api.metrics import (
            get_request_duration,
            inc_requests_total,
        )

        assert callable(get_request_duration)
        assert callable(inc_requests_total)

    def test_search_ui_metrics_importable(self):
        """Tests search_ui metrics can be imported."""
        from src.search_ui.metrics import (
            get_request_duration,
            inc_requests_total,
        )

        assert callable(get_request_duration)
        assert callable(inc_requests_total)


class TestOTelMetricsModule:
    """Tests for the OTel metrics module."""

    def test_init_otel_metrics_importable(self):
        """Tests init_otel_metrics can be imported."""
        from src.common.otel_metrics import init_otel_metrics

        assert callable(init_otel_metrics)

    def test_get_meter_importable(self):
        """Tests get_meter can be imported."""
        from src.common.otel_metrics import get_meter

        assert callable(get_meter)

    def test_track_latency_importable(self):
        """Tests track_latency can be imported."""
        from src.common.otel_metrics import track_latency

        assert callable(track_latency)

    def test_operation_type_enum(self):
        """Tests OperationType enum values."""
        from src.common.otel_metrics import OperationType

        assert OperationType.FAST.value == "fast"
        assert OperationType.MEDIUM.value == "medium"
        assert OperationType.SLOW.value == "slow"
        assert OperationType.BATCH.value == "batch"
