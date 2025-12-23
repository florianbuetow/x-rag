"""gRPC server implementation for Search Service."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

import grpc

from src.common.dataset_config import DatasetsConfigLoader
from src.common.metrics import track_latency
from src.core.errors import ConfigurationError
from src.llm.factory import create_llm_client
from src.llm.openai_client import OpenAIClient
from src.pipelines.search_pipeline import SearchPipeline
from src.proto_gen import common_pb2, search_pb2, search_pb2_grpc
from src.retrievers.weaviate_retriever import WeaviateRetriever
from src.retrievers.weaviate_retriever_factory import WeaviateRetrieverFactory
from src.search_service.config import SearchServiceConfig
from src.search_service.grpc_clients import EmbeddingServiceClient
from src.search_service.metrics import (
    dec_active_requests,
    get_request_duration,
    inc_active_requests,
    inc_errors_total,
    inc_requests_total,
)

logger = logging.getLogger(__name__)


class SearchServicer(search_pb2_grpc.SearchServiceServicer):
    """gRPC servicer for Search Service.

    Implements the SearchService gRPC interface defined in search.proto.
    Namespace-aware: creates separate pipelines for each dataset namespace.
    """

    def __init__(
        self,
        embedding_client: EmbeddingServiceClient,
        config: SearchServiceConfig,
        datasets_config_path: str,
    ) -> None:
        """Initialize servicer.

        Args:
            embedding_client: Shared embedding service client (namespace-aware)
            config: Service configuration
            datasets_config_path: Path to datasets configuration file (required)
        """
        self.embedding_client = embedding_client
        self.config = config
        self.datasets_loader = DatasetsConfigLoader(datasets_config_path)
        self.retriever_factory = WeaviateRetrieverFactory(
            datasets_config_path=datasets_config_path,
            weaviate_url=config.weaviate_url,
        )
        self._pipeline_cache: dict[str, SearchPipeline] = {}
        self._retriever_cache: dict[str, WeaviateRetriever] = {}
        self._llm_cache: dict[str, OpenAIClient] = {}

        namespaces = self.datasets_loader.list_namespaces()
        logger.info(f"SearchServicer initialized with {len(namespaces)} datasets: {namespaces}")

    def _get_pipeline(self, namespace: str) -> SearchPipeline:
        """Get or create search pipeline for namespace.

        Args:
            namespace: Dataset namespace

        Returns:
            SearchPipeline for the namespace

        Raises:
            ConfigurationError: If namespace is unknown
        """
        # Check cache first
        if namespace in self._pipeline_cache:
            return self._pipeline_cache[namespace]

        # Load dataset config
        logger.info(f"Creating search pipeline for namespace: {namespace}")
        dataset_config = self.datasets_loader.get_dataset_config(namespace)

        # Create or get retriever for this namespace
        if namespace not in self._retriever_cache:
            retriever = self.retriever_factory.create_retriever(namespace)
            retriever.connect()
            self._retriever_cache[namespace] = retriever
            logger.info(f"Created retriever for '{namespace}': collection={dataset_config.weaviate.collection}")

        # Create or get LLM client for this namespace
        if namespace not in self._llm_cache:
            llm_config = dataset_config.llm.to_llm_config()
            llm_client = create_llm_client(llm_config)
            self._llm_cache[namespace] = llm_client
            logger.info(f"Created LLM client for '{namespace}': provider={llm_config.provider.value}, model={llm_config.model}")

        # Create pipeline with namespace-specific components
        pipeline = SearchPipeline(
            retriever=self._retriever_cache[namespace],
            embedding_client=self.embedding_client,  # Shared, routes by namespace internally
            llm_client=self._llm_cache[namespace],
            max_context_length=dataset_config.search.max_context_length,
        )

        # Cache for future requests
        self._pipeline_cache[namespace] = pipeline
        logger.info(f"Cached pipeline for '{namespace}': max_context_length={dataset_config.search.max_context_length}")

        return pipeline

    async def _validate_and_get_search_params(
        self,
        request: search_pb2.SearchRequest,
        namespace: str,
        context: grpc.aio.ServicerContext[search_pb2.SearchRequest, search_pb2.SearchResponse],
    ) -> tuple[str, int, str, float]:
        """Validate and extract search parameters from request using dataset defaults.

        Args:
            request: The search request
            namespace: Dataset namespace
            context: gRPC context for error reporting

        Returns:
            Tuple of (query, top_k, mode, alpha)
        """
        if not request.query:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Query cannot be empty")

        # Load dataset-specific defaults
        try:
            dataset_config = self.datasets_loader.get_dataset_config(namespace)
        except ConfigurationError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        query = request.query

        # Validate top_k if explicitly provided (negative values are invalid)
        if request.top_k < 0:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"top_k must be positive, got {request.top_k}")

        # Use provided values if valid, otherwise use dataset defaults
        top_k = request.top_k if request.top_k > 0 else dataset_config.search.top_k
        mode = request.mode if request.mode else dataset_config.search.mode

        if top_k <= 0:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"top_k must be positive, got {top_k}")
        if top_k > 100:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"top_k too large (max 100), got {top_k}")

        valid_modes = ["vector", "bm25", "hybrid"]
        if mode not in valid_modes:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}",
            )

        # Parse alpha from request options or use dataset default
        alpha = dataset_config.search.hybrid_alpha
        if "alpha" in request.options:
            try:
                alpha = float(request.options["alpha"])
                if not 0.0 <= alpha <= 1.0:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"alpha must be between 0.0 and 1.0, got {alpha}")
            except ValueError:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid alpha value: {request.options['alpha']}")

        return query, top_k, mode, alpha

    def _build_search_response(self, result: dict[str, Any]) -> search_pb2.SearchResponse:
        """Build protobuf response from search result.

        Args:
            result: Search pipeline result dict

        Returns:
            SearchResponse protobuf message
        """
        sources = [
            search_pb2.Source(
                id=source_dict["id"],
                content=source_dict["content"],
                score=source_dict["score"],
                metadata={str(k): str(v) for k, v in source_dict["metadata"].items()} if "metadata" in source_dict else {},
            )
            for source_dict in result["sources"]
        ]

        metadata = {
            "mode": result["metadata"]["mode"],
            "top_k": str(result["metadata"]["top_k"]),
            "namespace": result["metadata"]["namespace"],
            "cache_hit": str(result["metadata"]["cache_hit"]) if "cache_hit" in result["metadata"] else "False",
            "num_sources": str(result["metadata"]["num_sources"]),
        }

        return search_pb2.SearchResponse(answer=result["answer"], sources=sources, metadata=metadata)

    async def _check_dependency(
        self,
        name: str,
        check_fn: Callable[[], bool] | Callable[[], Awaitable[bool]],
        is_async: bool,
    ) -> tuple[str, bool]:
        """Check a single dependency's health.

        Args:
            name: Name of the dependency
            check_fn: Health check function to call
            is_async: Whether check_fn is async

        Returns:
            Tuple of (status_string, is_healthy)
        """
        try:
            if is_async:
                healthy = await cast(Callable[[], Awaitable[bool]], check_fn)()
            else:
                healthy = cast(Callable[[], bool], check_fn)()
            return ("HEALTHY" if healthy else "UNHEALTHY", healthy)
        except Exception as e:
            logger.warning(f"{name} health check failed: {e}")
            return ("UNHEALTHY", False)

    async def Search(
        self,
        request: search_pb2.SearchRequest,
        context: grpc.aio.ServicerContext[search_pb2.SearchRequest, search_pb2.SearchResponse],
    ) -> search_pb2.SearchResponse:
        """Perform RAG search and generate answer.

        Args:
            request: SearchRequest with query and parameters
            context: gRPC context

        Returns:
            SearchResponse with answer and sources
        """
        inc_active_requests("Search")
        try:
            with track_latency(get_request_duration(), {"method": "Search"}):
                # Extract namespace first
                if not request.namespace:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "namespace is required")
                namespace = request.namespace

                # Get namespace-specific pipeline (validates namespace exists)
                try:
                    pipeline = self._get_pipeline(namespace)
                    dataset_config = self.datasets_loader.get_dataset_config(namespace)
                except ConfigurationError as e:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

                # Validate and extract parameters with dataset-specific defaults
                query, top_k, mode, alpha = await self._validate_and_get_search_params(request, namespace, context)

                logger.info(f"Search request: query='{query[:50]}...', mode={mode}, top_k={top_k}, namespace={namespace}")

                # Execute search pipeline with dataset-specific settings
                search_mode = cast(Literal["vector", "bm25", "hybrid"], mode)
                result = await pipeline.search(
                    query=query,
                    top_k=top_k,
                    mode=search_mode,
                    alpha=alpha,
                    namespace=namespace,
                    openai_max_tokens=dataset_config.llm.max_tokens,
                    openai_temperature=dataset_config.llm.temperature,
                )

                # Build and return response
                response = self._build_search_response(result)
                cache_hit = result["metadata"]["cache_hit"]
                logger.info(f"Search completed: {len(response.sources)} sources, cache_hit={cache_hit}")

            inc_requests_total("Search", "success")
            return response

        except grpc.RpcError:
            # Re-raise gRPC errors (already aborted)
            inc_requests_total("Search", "error")
            raise

        except Exception as e:
            logger.error(f"Unexpected error in Search: {e}", exc_info=True)
            inc_requests_total("Search", "error")
            inc_errors_total("Search", type(e).__name__)
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

        finally:
            dec_active_requests("Search")

    async def HealthCheck(
        self,
        request: common_pb2.HealthCheckRequest,
        context: grpc.aio.ServicerContext[common_pb2.HealthCheckRequest, common_pb2.HealthCheckResponse],
    ) -> common_pb2.HealthCheckResponse:
        """Health check endpoint.

        Checks critical dependencies:
        - Embedding Service (critical, shared)
        - Weaviate (checked via first cached retriever, if any)
        - LLM (checked via first cached LLM client, if any)

        Args:
            request: HealthCheckRequest (empty)
            context: gRPC context

        Returns:
            HealthCheckResponse with aggregate status
        """
        try:
            dependencies: dict[str, str] = {}

            # Check shared embedding service (critical)
            embedding_status, embedding_ok = await self._check_dependency(
                "Embedding Service", self.embedding_client.health_check, is_async=True
            )
            dependencies["embedding_service"] = embedding_status

            # Check Weaviate via first cached retriever (if any)
            weaviate_ok = True
            if self._retriever_cache:
                first_retriever = next(iter(self._retriever_cache.values()))
                weaviate_status, weaviate_ok = await self._check_dependency("Weaviate", first_retriever.health_check, is_async=False)
                dependencies["weaviate"] = weaviate_status
            else:
                dependencies["weaviate"] = "NOT_CHECKED"

            # Check LLM via first cached LLM client (if any)
            llm_ok = True
            if self._llm_cache:
                first_llm = next(iter(self._llm_cache.values()))
                llm_status, llm_ok = await self._check_dependency("LLM", first_llm.health_check, is_async=True)
                dependencies["llm"] = llm_status
            else:
                dependencies["llm"] = "NOT_CHECKED"

            # Service is healthy if embedding service is healthy (critical)
            # Weaviate and LLM are checked opportunistically if pipelines exist
            all_critical_healthy = embedding_ok and (not self._retriever_cache or weaviate_ok) and (not self._llm_cache or llm_ok)

            # Determine status
            if all_critical_healthy:
                status = common_pb2.HealthCheckResponse.HEALTHY
                message = "Search service is healthy"
            else:
                status = common_pb2.HealthCheckResponse.UNHEALTHY
                message = "Search service is unhealthy (critical dependencies down)"

            return common_pb2.HealthCheckResponse(status=status, dependencies=dependencies, message=message)

        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            return common_pb2.HealthCheckResponse(
                status=common_pb2.HealthCheckResponse.UNHEALTHY,
                dependencies={},
                message=f"Health check failed: {e}",
            )
