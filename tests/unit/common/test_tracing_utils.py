"""Unit tests for src/common/tracing_utils.py.

Tests cover:
- trace_llm_call decorator
- trace_embedding_generation context manager
- trace_vector_search context manager
- trace_document_processing context manager
- add_rag_attributes helper
"""

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.trace import SpanKind

from src.common.tracing_utils import (
    add_rag_attributes,
    trace_document_processing,
    trace_embedding_generation,
    trace_llm_call,
    trace_vector_search,
)


@pytest.fixture
def mock_tracer():
    """Create a mock tracer with span tracking."""
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=None)

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_span

    return mock_tracer, mock_span


class TestTraceLlmCall:
    """Tests for trace_llm_call decorator."""

    def test_decorator_returns_callable(self):
        """Tests that decorator returns a callable."""

        @trace_llm_call(model="gpt-4", operation="completion")
        def sample_func():
            return "result"

        assert callable(sample_func)

    @patch("src.common.tracing_utils._get_tracer")
    def test_sync_function_is_traced(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that sync functions are properly traced."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        @trace_llm_call(model="gpt-4", operation="completion")
        def sync_func():
            return "result"

        result = sync_func()

        assert result == "result"
        tracer.start_as_current_span.assert_called_once()
        span.set_attribute.assert_any_call("llm.model", "gpt-4")
        span.set_attribute.assert_any_call("llm.operation", "completion")

    @patch("src.common.tracing_utils._get_tracer")
    @pytest.mark.asyncio
    async def test_async_function_is_traced(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that async functions are properly traced."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        @trace_llm_call(model="gpt-4", operation="chat")
        async def async_func():
            return "async_result"

        result = await async_func()

        assert result == "async_result"
        tracer.start_as_current_span.assert_called_once()
        span.set_attribute.assert_any_call("llm.model", "gpt-4")

    @patch("src.common.tracing_utils._get_tracer")
    def test_span_kind_is_client(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that span kind is CLIENT for LLM calls."""
        tracer, _ = mock_tracer
        mock_get_tracer.return_value = tracer

        @trace_llm_call(model="gpt-4", operation="completion")
        def sync_func():
            return "result"

        sync_func()

        tracer.start_as_current_span.assert_called_once()
        call_kwargs = tracer.start_as_current_span.call_args[1]
        assert call_kwargs["kind"] == SpanKind.CLIENT

    @patch("src.common.tracing_utils._get_tracer")
    def test_exception_is_recorded(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that exceptions are recorded on the span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        @trace_llm_call(model="gpt-4", operation="completion")
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

        span.record_exception.assert_called_once()

    @patch("src.common.tracing_utils._get_tracer")
    def test_duration_is_recorded(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that duration is recorded on the span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        @trace_llm_call(model="gpt-4", operation="completion")
        def sync_func():
            return "result"

        sync_func()

        # Check that duration_ms attribute was set
        duration_calls = [call for call in span.set_attribute.call_args_list if call[0][0] == "llm.duration_ms"]
        assert len(duration_calls) == 1
        assert duration_calls[0][0][1] >= 0  # Duration should be non-negative


class TestTraceEmbeddingGeneration:
    """Tests for trace_embedding_generation context manager."""

    @patch("src.common.tracing_utils._get_tracer")
    def test_context_manager_yields_span(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that context manager yields the span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_embedding_generation("text-embedding-3-small", chunk_count=10, total_tokens=None) as yielded:
            assert yielded is span

    @patch("src.common.tracing_utils._get_tracer")
    def test_attributes_are_set(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that embedding attributes are set on span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_embedding_generation("text-embedding-3-small", chunk_count=10, total_tokens=None):
            pass

        span.set_attribute.assert_any_call("embedding.model", "text-embedding-3-small")
        span.set_attribute.assert_any_call("embedding.chunk_count", 10)

    @patch("src.common.tracing_utils._get_tracer")
    def test_optional_total_tokens(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that total_tokens is set when provided."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_embedding_generation("model", chunk_count=5, total_tokens=1000):
            pass

        span.set_attribute.assert_any_call("embedding.total_tokens", 1000)

    @patch("src.common.tracing_utils._get_tracer")
    def test_exception_sets_error_status(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that exceptions set error status on span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with pytest.raises(ValueError), trace_embedding_generation("model", chunk_count=5, total_tokens=None):
            raise ValueError("Test error")

        span.set_status.assert_called()
        span.record_exception.assert_called_once()


class TestTraceVectorSearch:
    """Tests for trace_vector_search context manager."""

    @patch("src.common.tracing_utils._get_tracer")
    def test_context_manager_yields_span(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that context manager yields the span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_vector_search("documents", top_k=10, query_vector_dim=None, search_mode=None) as yielded:
            assert yielded is span

    @patch("src.common.tracing_utils._get_tracer")
    def test_attributes_are_set(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that vector search attributes are set on span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_vector_search("documents", top_k=10, query_vector_dim=None, search_mode=None):
            pass

        span.set_attribute.assert_any_call("vector_search.index", "documents")
        span.set_attribute.assert_any_call("vector_search.top_k", 10)

    @patch("src.common.tracing_utils._get_tracer")
    def test_optional_query_vector_dim(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that query_vector_dim is set when provided."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_vector_search("documents", top_k=10, query_vector_dim=1536, search_mode=None):
            pass

        span.set_attribute.assert_any_call("vector_search.query_dimensions", 1536)

    @patch("src.common.tracing_utils._get_tracer")
    def test_optional_search_mode(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that search_mode is set when provided."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_vector_search("documents", top_k=10, query_vector_dim=None, search_mode="hybrid"):
            pass

        span.set_attribute.assert_any_call("vector_search.mode", "hybrid")


class TestTraceDocumentProcessing:
    """Tests for trace_document_processing context manager."""

    @patch("src.common.tracing_utils._get_tracer")
    def test_context_manager_yields_span(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that context manager yields the span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_document_processing("doc-123", "split") as yielded:
            assert yielded is span

    @patch("src.common.tracing_utils._get_tracer")
    def test_attributes_are_set(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that document processing attributes are set on span."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_document_processing("doc-123", "embed"):
            pass

        span.set_attribute.assert_any_call("document.id", "doc-123")
        span.set_attribute.assert_any_call("document.stage", "embed")

    @patch("src.common.tracing_utils._get_tracer")
    def test_span_name_includes_stage(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that span name includes the stage."""
        tracer, span = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_document_processing("doc-123", "store"):
            pass

        tracer.start_as_current_span.assert_called_once()
        call_args = tracer.start_as_current_span.call_args[0]
        assert call_args[0] == "document.store"

    @patch("src.common.tracing_utils._get_tracer")
    def test_span_kind_is_internal(self, mock_get_tracer: MagicMock, mock_tracer):
        """Tests that span kind is INTERNAL for document processing."""
        tracer, _ = mock_tracer
        mock_get_tracer.return_value = tracer

        with trace_document_processing("doc-123", "split"):
            pass

        call_kwargs = tracer.start_as_current_span.call_args[1]
        assert call_kwargs["kind"] == SpanKind.INTERNAL


class TestAddRagAttributes:
    """Tests for add_rag_attributes helper."""

    def test_adds_required_attributes(self):
        """Tests that required attributes are added to span."""
        mock_span = MagicMock()

        add_rag_attributes(
            mock_span,
            query="What is machine learning?",
            retrieved_count=5,
            reranked=False,
            final_context_tokens=None,
        )

        mock_span.set_attribute.assert_any_call("rag.query_length", 25)
        mock_span.set_attribute.assert_any_call("rag.retrieved_count", 5)
        mock_span.set_attribute.assert_any_call("rag.reranked", False)

    def test_adds_optional_reranked(self):
        """Tests that reranked attribute is set when provided."""
        mock_span = MagicMock()

        add_rag_attributes(
            mock_span,
            query="test",
            retrieved_count=5,
            reranked=True,
            final_context_tokens=None,
        )

        mock_span.set_attribute.assert_any_call("rag.reranked", True)

    def test_adds_optional_context_tokens(self):
        """Tests that context_tokens is set when provided."""
        mock_span = MagicMock()

        add_rag_attributes(
            mock_span,
            query="test",
            retrieved_count=5,
            reranked=False,
            final_context_tokens=2500,
        )

        mock_span.set_attribute.assert_any_call("rag.context_tokens", 2500)

    def test_does_not_add_context_tokens_when_none(self):
        """Tests that context_tokens is not set when None."""
        mock_span = MagicMock()

        add_rag_attributes(
            mock_span,
            query="test",
            retrieved_count=5,
            reranked=False,
            final_context_tokens=None,
        )

        # Check that context_tokens was NOT set
        context_token_calls = [call for call in mock_span.set_attribute.call_args_list if call[0][0] == "rag.context_tokens"]
        assert len(context_token_calls) == 0
