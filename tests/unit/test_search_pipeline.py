"""Tests for SearchPipeline."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.pipelines.search_pipeline import SearchPipeline
from src.retrievers.weaviate_retriever import SearchResult


class TestSearchPipelineInit:
    """Tests for SearchPipeline initialization."""

    def test_initialization_with_dependencies(self):
        """Pipeline initializes with retriever, embedding client, LLM."""
        mock_retriever = Mock()
        mock_embedding_client = AsyncMock()
        mock_llm_client = AsyncMock()

        pipeline = SearchPipeline(
            retriever=mock_retriever,
            embedding_client=mock_embedding_client,
            llm_client=mock_llm_client,
            max_context_length=4000,
        )

        assert pipeline.retriever is mock_retriever
        assert pipeline.embedding_client is mock_embedding_client
        assert pipeline.llm_client is mock_llm_client

    def test_initialization_stores_config(self):
        """Pipeline stores max_context_length."""
        mock_retriever = Mock()
        mock_embedding_client = AsyncMock()
        mock_llm_client = AsyncMock()

        pipeline = SearchPipeline(
            retriever=mock_retriever,
            embedding_client=mock_embedding_client,
            llm_client=mock_llm_client,
            max_context_length=8000,
        )

        assert pipeline.max_context_length == 8000

    def test_initialization_requires_max_context_length(self):
        """Pipeline requires max_context_length parameter."""
        mock_retriever = Mock()
        mock_embedding_client = AsyncMock()
        mock_llm_client = AsyncMock()

        with pytest.raises(TypeError, match="max_context_length"):
            SearchPipeline(
                retriever=mock_retriever,
                embedding_client=mock_embedding_client,
                llm_client=mock_llm_client,
            )


class TestSearchPipelineSearch:
    """Tests for search method."""

    @pytest.fixture
    def mock_retriever(self):
        """Mock WeaviateRetriever."""
        retriever = Mock()
        retriever.search = Mock(return_value=[])
        return retriever

    @pytest.fixture
    def mock_embedding_client(self):
        """Mock EmbeddingServiceClient."""
        client = AsyncMock()
        client.embed = AsyncMock(return_value=[0.1, 0.2, 0.3] * 512)
        return client

    @pytest.fixture
    def mock_llm_client(self):
        """Mock OpenAIClient."""
        client = AsyncMock()
        client.generate = AsyncMock(return_value="This is the generated answer.")
        return client

    @pytest.fixture
    def pipeline(self, mock_retriever, mock_embedding_client, mock_llm_client):
        """Create a SearchPipeline for testing."""
        return SearchPipeline(
            retriever=mock_retriever,
            embedding_client=mock_embedding_client,
            llm_client=mock_llm_client,
            max_context_length=4000,
        )

    @pytest.fixture
    def sample_search_results(self):
        """Sample search results from retriever."""
        return [
            SearchResult(
                id="chunk-1",
                content="Machine learning is a subset of AI.",
                score=0.95,
                metadata={"doc_id": "doc-1", "title": "ML Basics"},
            ),
            SearchResult(
                id="chunk-2",
                content="Deep learning uses neural networks.",
                score=0.88,
                metadata={"doc_id": "doc-2", "title": "DL Intro"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_search_vector_mode_generates_embedding(self, pipeline, mock_embedding_client, sample_search_results):
        """Vector mode calls embedding client."""
        pipeline.retriever.search.return_value = sample_search_results

        await pipeline.search(
            query="test query",
            top_k=10,
            mode="vector",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        mock_embedding_client.embed.assert_called_once()
        call_kwargs = mock_embedding_client.embed.call_args[1]
        assert call_kwargs["text"] == "test query"

    @pytest.mark.asyncio
    async def test_search_hybrid_mode_generates_embedding(self, pipeline, mock_embedding_client, sample_search_results):
        """Hybrid mode calls embedding client."""
        pipeline.retriever.search.return_value = sample_search_results

        await pipeline.search(
            query="test query",
            top_k=10,
            mode="hybrid",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        mock_embedding_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_bm25_mode_no_embedding(self, pipeline, mock_embedding_client, sample_search_results):
        """BM25 mode skips embedding generation."""
        pipeline.retriever.search.return_value = sample_search_results

        await pipeline.search(
            query="test query",
            top_k=10,
            mode="bm25",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        mock_embedding_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_retrieves_documents(self, pipeline, mock_retriever, sample_search_results):
        """Search calls retriever with correct parameters."""
        mock_retriever.search.return_value = sample_search_results

        await pipeline.search(
            query="test query",
            top_k=5,
            mode="hybrid",
            alpha=0.7,
            namespace="test-ns",
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        mock_retriever.search.assert_called_once()
        call_kwargs = mock_retriever.search.call_args[1]
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["top_k"] == 5
        assert call_kwargs["mode"] == "hybrid"
        assert call_kwargs["alpha"] == 0.7
        assert call_kwargs["namespace"] == "test-ns"

    @pytest.mark.asyncio
    async def test_search_no_results_returns_appropriate_response(self, pipeline):
        """No retrieved documents returns appropriate response."""
        pipeline.retriever.search.return_value = []

        result = await pipeline.search(
            query="test query",
            top_k=10,
            mode="hybrid",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        assert "sources" in result
        assert result["sources"] == []
        assert result["metadata"]["num_sources"] == 0
        # LLM should not be called when no results
        pipeline.llm_client.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_generates_answer_with_llm(self, pipeline, mock_llm_client, sample_search_results):
        """LLM called with query and context."""
        pipeline.retriever.search.return_value = sample_search_results

        result = await pipeline.search(
            query="test query",
            top_k=10,
            mode="hybrid",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        mock_llm_client.generate.assert_called_once()
        assert result["answer"] == "This is the generated answer."

    @pytest.mark.asyncio
    async def test_search_passes_openai_params(self, pipeline, mock_llm_client, sample_search_results):
        """Search passes OpenAI parameters correctly."""
        pipeline.retriever.search.return_value = sample_search_results

        await pipeline.search(
            query="test query",
            top_k=10,
            mode="hybrid",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=200,
            openai_temperature=0.3,
        )

        call_kwargs = mock_llm_client.generate.call_args[1]
        assert call_kwargs["max_tokens"] == 200
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_search_returns_complete_result(self, pipeline, sample_search_results):
        """SearchResult has answer, sources, metadata."""
        pipeline.retriever.search.return_value = sample_search_results

        result = await pipeline.search(
            query="test query",
            top_k=10,
            mode="hybrid",
            alpha=0.5,
            namespace="my-namespace",
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        assert "answer" in result
        assert "sources" in result
        assert "metadata" in result
        assert result["metadata"]["mode"] == "hybrid"
        assert result["metadata"]["top_k"] == 10
        assert result["metadata"]["namespace"] == "my-namespace"
        assert result["metadata"]["num_sources"] == 2

    @pytest.mark.asyncio
    async def test_search_sources_are_serialized(self, pipeline, sample_search_results):
        """Sources are converted to dictionaries."""
        pipeline.retriever.search.return_value = sample_search_results

        result = await pipeline.search(
            query="test query",
            top_k=10,
            mode="hybrid",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        assert len(result["sources"]) == 2
        source = result["sources"][0]
        assert source["id"] == "chunk-1"
        assert source["content"] == "Machine learning is a subset of AI."
        assert source["score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_default_namespace(self, pipeline, sample_search_results):
        """Default namespace is 'default' when not specified."""
        pipeline.retriever.search.return_value = sample_search_results

        result = await pipeline.search(
            query="test query",
            top_k=10,
            mode="hybrid",
            alpha=0.5,
            namespace=None,
            openai_max_tokens=500,
            openai_temperature=0.7,
        )

        assert result["metadata"]["namespace"] == "default"


class TestSearchPipelineContext:
    """Tests for context building."""

    @pytest.fixture
    def pipeline(self):
        """Create a SearchPipeline for testing."""
        return SearchPipeline(
            retriever=Mock(),
            embedding_client=AsyncMock(),
            llm_client=AsyncMock(),
            max_context_length=100,  # Small for testing truncation
        )

    def test_build_context_concatenates_documents(self, pipeline):
        """Context includes all document contents."""
        results = [
            SearchResult(id="1", content="First content", score=0.9, metadata={}),
            SearchResult(id="2", content="Second content", score=0.8, metadata={}),
        ]

        context = pipeline._build_context(results)

        assert "Source 1: First content" in context
        assert "Source 2: Second content" in context

    def test_build_context_truncates_when_too_long(self, pipeline):
        """Context truncated to max_context_length."""
        # Each result is ~50 chars with formatting
        results = [
            SearchResult(id="1", content="A" * 40, score=0.9, metadata={}),
            SearchResult(id="2", content="B" * 40, score=0.8, metadata={}),
            SearchResult(id="3", content="C" * 40, score=0.7, metadata={}),
        ]

        context = pipeline._build_context(results)

        # Should only include first ~2 results due to max_context_length=100
        assert "Source 1" in context
        # Source 3 should be truncated
        assert "Source 3" not in context

    def test_build_context_empty_results(self, pipeline):
        """Empty results returns empty context."""
        context = pipeline._build_context([])

        assert context == ""

    def test_build_context_separator(self, pipeline):
        """Context uses double newline separator."""
        results = [
            SearchResult(id="1", content="First", score=0.9, metadata={}),
            SearchResult(id="2", content="Second", score=0.8, metadata={}),
        ]

        # Temporarily increase max length to avoid truncation
        pipeline.max_context_length = 1000
        context = pipeline._build_context(results)

        assert "\n\n" in context


class TestSearchPipelineCleanup:
    """Tests for cleanup."""

    @pytest.mark.asyncio
    async def test_close_is_callable(self):
        """close() can be called without error."""
        pipeline = SearchPipeline(
            retriever=Mock(),
            embedding_client=AsyncMock(),
            llm_client=AsyncMock(),
            max_context_length=4000,
        )

        # Should not raise
        await pipeline.close()
