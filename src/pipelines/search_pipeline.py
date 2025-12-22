"""Search pipeline for RAG queries.

Orchestrates the complete RAG pipeline:
1. Embed query using Embedding Service
2. Retrieve relevant documents from Weaviate
3. Generate answer using OpenAI LLM
"""

import logging
from typing import Any, Literal

from src.common.metrics import track_latency
from src.common.tracing_utils import trace_vector_search
from src.llm.openai_client import OpenAIClient
from src.pipelines.prompt_templates import build_no_results_response, build_rag_prompt
from src.retrievers.weaviate_retriever import SearchResult, WeaviateRetriever
from src.search_service.grpc_clients import EmbeddingServiceClient
from src.search_service.metrics import (
    get_embedding_duration,
    get_llm_generation_duration,
    get_retrieval_duration,
)

logger = logging.getLogger(__name__)


class SearchPipeline:
    """RAG search pipeline.

    Coordinates embedding generation, document retrieval, and answer generation
    to answer user queries with retrieved context.
    """

    def __init__(
        self,
        retriever: WeaviateRetriever,
        embedding_client: EmbeddingServiceClient,
        llm_client: OpenAIClient,
        max_context_length: int,
    ) -> None:
        """Initialize search pipeline.

        Args:
            retriever: Weaviate retriever for document search
            embedding_client: Client for generating query embeddings
            llm_client: OpenAI client for answer generation
            max_context_length: Maximum context length in characters
        """
        self.retriever = retriever
        self.embedding_client = embedding_client
        self.llm_client = llm_client
        self.max_context_length = max_context_length

    async def search(
        self,
        query: str,
        top_k: int,
        mode: Literal["vector", "bm25", "hybrid"],
        alpha: float,
        namespace: str | None,
        openai_max_tokens: int,
        openai_temperature: float,
    ) -> dict[str, Any]:
        """Execute RAG search pipeline.

        Args:
            query: User query
            top_k: Number of documents to retrieve
            mode: Search mode (vector, bm25, hybrid)
            alpha: Hybrid search alpha (0=BM25, 1=vector)
            namespace: Namespace filter
            openai_max_tokens: Max tokens in LLM response
            openai_temperature: LLM temperature

        Returns:
            Dictionary with answer, sources, and metadata
        """
        # Step 1: Generate query embedding (for vector/hybrid modes)
        query_embedding: list[float] | None = None
        if mode in ("vector", "hybrid"):
            logger.debug(f"Generating embedding for query: {query[:50]}...")
            with track_latency(get_embedding_duration(), {}):
                if not namespace:
                    raise ValueError("namespace is required for search")
                query_embedding = await self.embedding_client.embed(
                    text=query,
                    model="text-embedding-3-small",
                    namespace=namespace,
                )
            logger.debug(f"Generated embedding (dim={len(query_embedding)})")

        # Step 2: Retrieve relevant documents
        logger.info(f"Retrieving documents (mode={mode}, top_k={top_k})")
        query_dim = len(query_embedding) if query_embedding else None
        with (
            track_latency(get_retrieval_duration(), {"mode": mode}),  # nosemgrep: xrag.no-dict-get-with-default
            trace_vector_search(
                index_name="DocumentChunk",
                top_k=top_k,
                query_vector_dim=query_dim,
                search_mode=mode,
            ) as search_span,
        ):
            results: list[SearchResult] = self.retriever.search(
                query=query,
                query_embedding=query_embedding,
                top_k=top_k,
                mode=mode,
                alpha=alpha,
                namespace=namespace,
            )
            search_span.set_attribute("vector_search.result_count", len(results))

        # Step 3: Build context from results
        response: dict[str, Any]
        if not results:
            logger.info("No results found")
            if not namespace:
                raise ValueError("namespace is required for search")
            response = {
                "answer": build_no_results_response(query),
                "sources": [],
                "metadata": {
                    "mode": mode,
                    "top_k": top_k,
                    "namespace": namespace,
                    "num_sources": 0,
                },
            }
        else:
            # Build context from top results
            context = self._build_context(results)
            logger.debug(f"Built context ({len(context)} chars)")

            # Step 4: Generate answer using LLM
            logger.info("Generating answer with OpenAI")
            prompt = build_rag_prompt(query=query, context=context)
            with track_latency(get_llm_generation_duration(), {}):
                answer = await self.llm_client.generate(
                    prompt=prompt,
                    max_tokens=openai_max_tokens,
                    temperature=openai_temperature,
                    system_message=None,
                )

            # Build response
            sources_list: list[dict[str, Any]] = [r.to_dict() for r in results]
            if not namespace:
                raise ValueError("namespace is required for search")
            response = {
                "answer": answer,
                "sources": sources_list,
                "metadata": {
                    "mode": mode,
                    "top_k": top_k,
                    "namespace": namespace,
                    "num_sources": len(results),
                },
            }

        return response

    def _build_context(self, results: list[SearchResult]) -> str:
        """Build context string from search results.

        Args:
            results: Search results

        Returns:
            Formatted context string
        """
        context_parts = []
        current_length = 0

        for i, result in enumerate(results, 1):
            # Format: "Source 1: <content>"
            part = f"Source {i}: {result.content}"

            # Check if adding this would exceed max length
            if current_length + len(part) > self.max_context_length:
                logger.warning(f"Context truncated: using {i - 1}/{len(results)} sources (max_length={self.max_context_length})")
                break

            context_parts.append(part)
            current_length += len(part)

        return "\n\n".join(context_parts)

    async def close(self) -> None:
        """Close all connections."""
        pass
