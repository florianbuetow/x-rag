"""Tracing utilities for RAG-specific operations.

Provides decorators and context managers for instrumenting common RAG operations:
LLM calls, embedding generation, and vector search.

This module provides:
- trace_llm_call: Decorator for tracing LLM operations
- trace_embedding_generation: Context manager for embedding operations
- trace_vector_search: Context manager for vector database queries
- add_rag_attributes: Helper to add RAG-specific attributes to spans

Usage:
    from src.common.tracing_utils import (
        trace_llm_call,
        trace_embedding_generation,
        trace_vector_search,
    )

    # Decorator for LLM calls
    @trace_llm_call(model="gpt-4", operation="completion")
    async def generate_answer(prompt: str) -> str:
        return await llm.complete(prompt)

    # Context manager for embeddings
    with trace_embedding_generation("text-embedding-3-small", chunk_count=10) as span:
        embeddings = await client.embed(texts)
        span.set_attribute("embedding.dimensions", len(embeddings[0]))

    # Context manager for vector search
    with trace_vector_search("documents", top_k=10) as span:
        results = await db.search(query_vector)
        span.set_attribute("vector_search.result_count", len(results))
"""

import asyncio
import functools
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any, ParamSpec, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

P = ParamSpec("P")
T = TypeVar("T")


def _get_tracer() -> trace.Tracer:
    """Get the global tracer for this module."""
    return trace.get_tracer(__name__)


def trace_llm_call(
    model: str,
    operation: str = "completion",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for tracing LLM API calls.

    Records timing, model info, and token counts (if available) for LLM operations.

    Args:
        model: LLM model name (e.g., "gpt-4", "gpt-3.5-turbo")
        operation: Operation type (e.g., "completion", "chat", "rerank")

    Returns:
        Decorated function

    Example:
        @trace_llm_call(model="gpt-4", operation="completion")
        async def generate_answer(prompt: str) -> str:
            return await llm.complete(prompt)
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = _get_tracer()
            with tracer.start_as_current_span(
                f"llm.{operation}",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("llm.model", model)
                span.set_attribute("llm.operation", operation)

                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)  # type: ignore[misc]

                    # Record token counts if available (OpenAI response format)
                    if hasattr(result, "usage") and result.usage is not None:
                        span.set_attribute("llm.prompt_tokens", result.usage.prompt_tokens)
                        span.set_attribute("llm.completion_tokens", result.usage.completion_tokens)
                        span.set_attribute("llm.total_tokens", result.usage.total_tokens)

                    span.set_status(Status(StatusCode.OK))
                    return result  # type: ignore[no-any-return]

                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("llm.duration_ms", duration_ms)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = _get_tracer()
            with tracer.start_as_current_span(
                f"llm.{operation}",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("llm.model", model)
                span.set_attribute("llm.operation", operation)

                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("llm.duration_ms", duration_ms)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator


@contextmanager
def trace_embedding_generation(
    model: str,
    chunk_count: int,
    total_tokens: int | None = None,
) -> Generator[Span, None, None]:
    """Context manager for tracing embedding generation.

    Args:
        model: Embedding model name (e.g., "text-embedding-3-small")
        chunk_count: Number of text chunks being embedded
        total_tokens: Optional total token count

    Yields:
        Active span for adding additional attributes

    Example:
        with trace_embedding_generation("text-embedding-3-small", len(chunks)) as span:
            embeddings = await client.embed(chunks)
            span.set_attribute("embedding.dimensions", len(embeddings[0]))
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(
        "embedding.generate",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("embedding.model", model)
        span.set_attribute("embedding.chunk_count", chunk_count)
        if total_tokens is not None:
            span.set_attribute("embedding.total_tokens", total_tokens)

        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("embedding.duration_ms", duration_ms)


@contextmanager
def trace_vector_search(
    index_name: str,
    top_k: int,
    query_vector_dim: int | None = None,
    search_mode: str | None = None,
) -> Generator[Span, None, None]:
    """Context manager for tracing vector database searches.

    Args:
        index_name: Name of the vector index/collection
        top_k: Number of results requested
        query_vector_dim: Optional dimension of query vector
        search_mode: Optional search mode (e.g., "vector", "hybrid", "bm25")

    Yields:
        Active span for adding additional attributes

    Example:
        with trace_vector_search("documents", top_k=10) as span:
            results = await vector_db.search(query_embedding, top_k=10)
            span.set_attribute("vector_search.result_count", len(results))
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(
        "vector_search.query",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("vector_search.index", index_name)
        span.set_attribute("vector_search.top_k", top_k)
        if query_vector_dim is not None:
            span.set_attribute("vector_search.query_dimensions", query_vector_dim)
        if search_mode is not None:
            span.set_attribute("vector_search.mode", search_mode)

        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("vector_search.duration_ms", duration_ms)


@contextmanager
def trace_llm_generation(
    model: str,
    operation: str = "completion",
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> Generator[Span, None, None]:
    """Context manager for tracing LLM generation calls.

    Args:
        model: LLM model name (e.g., "gpt-4", "gpt-3.5-turbo")
        operation: Operation type (e.g., "completion", "chat")
        max_tokens: Optional max tokens parameter
        temperature: Optional temperature parameter

    Yields:
        Active span for adding additional attributes

    Example:
        with trace_llm_generation("gpt-4", max_tokens=500) as span:
            answer = await llm.generate(prompt)
            span.set_attribute("llm.response_length", len(answer))
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(
        f"llm.{operation}",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.operation", operation)
        if max_tokens is not None:
            span.set_attribute("llm.max_tokens", max_tokens)
        if temperature is not None:
            span.set_attribute("llm.temperature", temperature)

        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("llm.duration_ms", duration_ms)


@contextmanager
def trace_document_processing(
    document_id: str,
    stage: str,
) -> Generator[Span, None, None]:
    """Context manager for tracing document processing stages.

    Args:
        document_id: Unique identifier for the document
        stage: Processing stage (e.g., "load", "clean", "split", "embed", "store")

    Yields:
        Active span for adding additional attributes

    Example:
        with trace_document_processing(doc_id, "split") as span:
            chunks = splitter.split(document)
            span.set_attribute("document.chunk_count", len(chunks))
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(
        f"document.{stage}",
        kind=SpanKind.INTERNAL,
    ) as span:
        span.set_attribute("document.id", document_id)
        span.set_attribute("document.stage", stage)

        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("document.duration_ms", duration_ms)


def add_rag_attributes(
    span: Span,
    query: str,
    retrieved_count: int,
    reranked: bool = False,
    final_context_tokens: int | None = None,
) -> None:
    """Add RAG-specific attributes to a span.

    Helper function to add common RAG attributes to an existing span.

    Args:
        span: OpenTelemetry Span to add attributes to
        query: Search query text
        retrieved_count: Number of documents retrieved
        reranked: Whether results were reranked
        final_context_tokens: Optional token count in final context
    """
    span.set_attribute("rag.query_length", len(query))
    span.set_attribute("rag.retrieved_count", retrieved_count)
    span.set_attribute("rag.reranked", reranked)
    if final_context_tokens is not None:
        span.set_attribute("rag.context_tokens", final_context_tokens)


def create_span_from_context(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Span:
    """Create a new span as child of the current context.

    Utility for creating manual spans with common setup.

    Args:
        name: Span name
        attributes: Optional dict of initial attributes
        kind: Span kind (default: INTERNAL)

    Returns:
        Started span (must be used as context manager or ended manually)
    """
    tracer = _get_tracer()
    span = tracer.start_span(name, kind=kind)
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    return span
