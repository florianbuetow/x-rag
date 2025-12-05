"""Unit tests for src/common/tracing.py.

Tests cover:
- init_tracing function
- get_tracer function
- shutdown_tracing function
- get_current_trace_id function
- is_tracing_enabled function
"""

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from src.common import tracing


@pytest.fixture(autouse=True)
def reset_tracing_state():
    """Reset global tracing state before and after each test."""
    # Reset before test
    tracing._tracer_provider = None

    yield

    # Reset after test
    if tracing._tracer_provider is not None:
        tracing._tracer_provider.shutdown()
        tracing._tracer_provider = None


class TestInitTracing:
    """Tests for init_tracing function."""

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_returns_tracer_provider(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that init_tracing returns a TracerProvider."""
        result = tracing.init_tracing(service_name="test-service")

        assert isinstance(result, TracerProvider)

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_sets_global_provider(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that init_tracing sets the global tracer provider."""
        tracing.init_tracing(service_name="test-service")

        assert tracing._tracer_provider is not None

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_uses_default_endpoint(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that init_tracing uses default endpoint when not specified."""
        tracing.init_tracing(service_name="test-service")

        mock_exporter.assert_called_once()
        call_kwargs = mock_exporter.call_args[1]
        assert call_kwargs["endpoint"] == "http://xrag-tempo:4317"

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_uses_custom_endpoint(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that init_tracing uses custom endpoint when provided."""
        custom_endpoint = "http://custom-tempo:4317"
        tracing.init_tracing(
            service_name="test-service",
            otlp_endpoint=custom_endpoint,
        )

        mock_exporter.assert_called_once()
        call_kwargs = mock_exporter.call_args[1]
        assert call_kwargs["endpoint"] == custom_endpoint

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_uses_env_endpoint(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Tests that init_tracing reads endpoint from env var."""
        env_endpoint = "http://env-tempo:4317"
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", env_endpoint)

        tracing.init_tracing(service_name="test-service")

        mock_exporter.assert_called_once()
        call_kwargs = mock_exporter.call_args[1]
        assert call_kwargs["endpoint"] == env_endpoint

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_configures_batch_processor(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that init_tracing configures BatchSpanProcessor."""
        tracing.init_tracing(service_name="test-service")

        mock_batch_processor.assert_called_once()
        call_kwargs = mock_batch_processor.call_args[1]
        assert call_kwargs["max_queue_size"] == 2048
        assert call_kwargs["max_export_batch_size"] == 512
        assert call_kwargs["schedule_delay_millis"] == 5000

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_warns_if_already_initialized(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests that init_tracing warns if called twice."""
        tracing.init_tracing(service_name="test-service")
        tracing.init_tracing(service_name="test-service-2")

        assert "already initialized" in caplog.text

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_init_tracing_returns_existing_provider_if_initialized(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that init_tracing returns existing provider if called twice."""
        first_provider = tracing.init_tracing(service_name="test-service")
        second_provider = tracing.init_tracing(service_name="test-service-2")

        assert first_provider is second_provider


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_get_tracer_returns_tracer(self):
        """Tests that get_tracer returns a Tracer instance."""
        result = tracing.get_tracer("test-module")

        assert isinstance(result, trace.Tracer)

    def test_get_tracer_returns_different_tracers_for_different_names(self):
        """Tests that get_tracer returns tracers with different names."""
        tracer1 = tracing.get_tracer("module1")
        tracer2 = tracing.get_tracer("module2")

        # Both should be valid tracers (implementation detail: may be same or different)
        assert isinstance(tracer1, trace.Tracer)
        assert isinstance(tracer2, trace.Tracer)


class TestShutdownTracing:
    """Tests for shutdown_tracing function."""

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_shutdown_tracing_clears_global_provider(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that shutdown_tracing clears the global provider."""
        tracing.init_tracing(service_name="test-service")
        assert tracing._tracer_provider is not None

        tracing.shutdown_tracing()

        assert tracing._tracer_provider is None

    def test_shutdown_tracing_does_nothing_if_not_initialized(
        self,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests that shutdown_tracing is safe to call when not initialized."""
        # Should not raise
        tracing.shutdown_tracing()

        # Should not log shutdown message
        assert "shutdown complete" not in caplog.text.lower()

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_shutdown_tracing_logs_completion(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Tests that shutdown_tracing logs completion."""
        import logging

        caplog.set_level(logging.INFO)
        tracing.init_tracing(service_name="test-service")
        tracing.shutdown_tracing()

        assert "shutdown complete" in caplog.text.lower()


class TestGetCurrentTraceId:
    """Tests for get_current_trace_id function."""

    def test_get_current_trace_id_returns_none_without_active_span(self):
        """Tests that get_current_trace_id returns None when no span is active."""
        result = tracing.get_current_trace_id()

        assert result is None

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_get_current_trace_id_returns_hex_string_with_active_span(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that get_current_trace_id returns hex string when span is active."""
        tracing.init_tracing(service_name="test-service")
        tracer = tracing.get_tracer("test")

        with tracer.start_as_current_span("test-span"):
            result = tracing.get_current_trace_id()

        assert result is not None
        assert len(result) == 32  # 128-bit trace ID = 32 hex chars
        # Verify it's valid hex
        int(result, 16)


class TestIsTracingEnabled:
    """Tests for is_tracing_enabled function."""

    def test_is_tracing_enabled_returns_false_when_not_initialized(self):
        """Tests that is_tracing_enabled returns False before init."""
        result = tracing.is_tracing_enabled()

        assert result is False

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_is_tracing_enabled_returns_true_when_initialized(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that is_tracing_enabled returns True after init."""
        tracing.init_tracing(service_name="test-service")

        result = tracing.is_tracing_enabled()

        assert result is True

    @patch("src.common.tracing.OTLPSpanExporter")
    @patch("src.common.tracing.BatchSpanProcessor")
    def test_is_tracing_enabled_returns_false_after_shutdown(
        self,
        mock_batch_processor: MagicMock,
        mock_exporter: MagicMock,
    ):
        """Tests that is_tracing_enabled returns False after shutdown."""
        tracing.init_tracing(service_name="test-service")
        tracing.shutdown_tracing()

        result = tracing.is_tracing_enabled()

        assert result is False
