"""Search pipeline for RAG queries.

Orchestrates the complete RAG pipeline:
1. Embed query using Embedding Service
2. Retrieve relevant documents from Weaviate
3. Generate answer using OpenAI LLM
4. Cache results in Redis
"""

import json
import logging
from typing import Any, Dict, List, Literal, Optional, cast

import redis.asyncio as aioredis

from src.llm.openai_client import OpenAIClient
from src.pipelines.prompt_templates import build_no_results_response, build_rag_prompt
from src.retrievers.weaviate_retriever import SearchResult, WeaviateRetriever
from src.search_service.grpc_clients import EmbeddingServiceClient

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
        redis_url: str,
        cache_ttl: int = 3600,
        enable_cache: bool = True,
        max_context_length: int = 4000,
    ) -> None:
        """Initialize search pipeline.

        Args:
            retriever: Weaviate retriever for document search
            embedding_client: Client for generating query embeddings
            llm_client: OpenAI client for answer generation
            redis_url: Redis URL for caching
            cache_ttl: Cache TTL in seconds
            enable_cache: Whether to enable caching
            max_context_length: Maximum context length in characters
        """
        self.retriever = retriever
        self.embedding_client = embedding_client
        self.llm_client = llm_client
        self.cache_ttl = cache_ttl
        self.enable_cache = enable_cache
        self.max_context_length = max_context_length

        # Initialize Redis client for caching
        self.redis_client: Optional[aioredis.Redis] = None
        if enable_cache:
            self.redis_client = aioredis.from_url(  # type: ignore[no-untyped-call]
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info(f"✓ Cache enabled (TTL={cache_ttl}s)")
        else:
            logger.info("Cache disabled")

    async def search(
        self,
        query: str,
        top_k: int = 10,
        mode: Literal["vector", "bm25", "hybrid"] = "hybrid",
        alpha: float = 0.5,
        namespace: Optional[str] = None,
        use_cache: bool = True,
        openai_max_tokens: int = 500,
        openai_temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Execute RAG search pipeline.

        Args:
            query: User query
            top_k: Number of documents to retrieve
            mode: Search mode (vector, bm25, hybrid)
            alpha: Hybrid search alpha (0=BM25, 1=vector)
            namespace: Namespace filter
            use_cache: Whether to check cache
            openai_max_tokens: Max tokens in LLM response
            openai_temperature: LLM temperature

        Returns:
            Dictionary with answer, sources, and metadata
        """
        # Check cache first
        if use_cache and self.enable_cache and self.redis_client:
            cache_key = self._make_cache_key(query, top_k, mode, alpha, namespace)
            cached = await self._get_from_cache(cache_key)
            if cached:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return cached

        # Step 1: Generate query embedding (for vector/hybrid modes)
        query_embedding: Optional[List[float]] = None
        if mode in ("vector", "hybrid"):
            logger.debug(f"Generating embedding for query: {query[:50]}...")
            query_embedding = await self.embedding_client.embed(
                text=query,
                model="text-embedding-3-small",
            )
            logger.debug(f"Generated embedding (dim={len(query_embedding)})")

        # Step 2: Retrieve relevant documents
        logger.info(f"Retrieving documents (mode={mode}, top_k={top_k})")
        results: List[SearchResult] = self.retriever.search(
            query=query,
            query_embedding=query_embedding,
            top_k=top_k,
            mode=mode,
            alpha=alpha,
            namespace=namespace,
        )

        # Step 3: Build context from results
        response: Dict[str, Any]
        if not results:
            logger.info("No results found")
            response = {
                "answer": build_no_results_response(query),
                "sources": [],
                "metadata": {
                    "mode": mode,
                    "top_k": top_k,
                    "namespace": namespace or "default",
                    "cache_hit": False,
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
            answer = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=openai_max_tokens,
                temperature=openai_temperature,
            )

            # Build response
            sources_list: List[Dict[str, Any]] = [r.to_dict() for r in results]
            response = {
                "answer": answer,
                "sources": sources_list,
                "metadata": {
                    "mode": mode,
                    "top_k": top_k,
                    "namespace": namespace or "default",
                    "cache_hit": False,
                    "num_sources": len(results),
                },
            }

        # Cache the result
        if use_cache and self.enable_cache and self.redis_client:
            cache_key = self._make_cache_key(query, top_k, mode, alpha, namespace)
            await self._save_to_cache(cache_key, response)

        return response

    def _build_context(self, results: List[SearchResult]) -> str:
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

    def _make_cache_key(
        self,
        query: str,
        top_k: int,
        mode: str,
        alpha: float,
        namespace: Optional[str],
    ) -> str:
        """Generate cache key for a query.

        Args:
            query: User query
            top_k: Number of results
            mode: Search mode
            alpha: Hybrid alpha
            namespace: Namespace filter

        Returns:
            Cache key string
        """
        ns = namespace or "default"
        return f"search:{mode}:{ns}:{top_k}:{alpha}:{query}"

    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get result from cache.

        Args:
            key: Cache key

        Returns:
            Cached result or None
        """
        if not self.redis_client:
            return None

        try:
            cached = await self.redis_client.get(key)
            if cached:
                result = cast(Dict[str, Any], json.loads(cached))
                result["metadata"]["cache_hit"] = True
                return result
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

        return None

    async def _save_to_cache(self, key: str, value: Dict[str, Any]) -> None:
        """Save result to cache.

        Args:
            key: Cache key
            value: Result to cache
        """
        if not self.redis_client:
            return

        try:
            await self.redis_client.set(
                key,
                json.dumps(value),
                ex=self.cache_ttl,
            )
            logger.debug(f"Cached result (key={key[:50]}...)")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def close(self) -> None:
        """Close all connections."""
        if self.redis_client:
            await self.redis_client.close()
