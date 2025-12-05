"""gRPC server implementation for Search Service."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

import grpc

from src.common.metrics import track_latency
from src.pipelines.search_pipeline import SearchPipeline
from src.proto_gen import common_pb2, search_pb2, search_pb2_grpc
from src.search_service.config import SearchServiceConfig
from src.search_service.metrics import (
    active_requests,
    errors_total,
    request_duration,
    requests_total,
)

logger = logging.getLogger(__name__)


class SearchServicer(search_pb2_grpc.SearchServiceServicer):
    """gRPC servicer for Search Service.

    Implements the SearchService gRPC interface defined in search.proto.
    """

    def __init__(self, pipeline: SearchPipeline, config: SearchServiceConfig) -> None:
        """Initialize servicer.

        Args:
            pipeline: Search pipeline instance
            config: Service configuration
        """
        self.pipeline = pipeline
        self.config = config
        logger.info("SearchServicer initialized")

    async def _validate_search_params(
        self,
        request: search_pb2.SearchRequest,
        context: grpc.aio.ServicerContext[search_pb2.SearchRequest, search_pb2.SearchResponse],
    ) -> tuple[str, str, int, str, float]:
        """Validate and extract search parameters from request.

        Args:
            request: The search request
            context: gRPC context for error reporting

        Returns:
            Tuple of (query, namespace, top_k, mode, alpha)
        """
        if not request.query:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Query cannot be empty")

        query = request.query
        namespace = request.namespace or "default"
        top_k = request.top_k or self.config.default_top_k
        mode = request.mode or self.config.default_mode

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

        alpha = await self._parse_alpha(request, context)

        return query, namespace, top_k, mode, alpha

    async def _parse_alpha(
        self,
        request: search_pb2.SearchRequest,
        context: grpc.aio.ServicerContext[search_pb2.SearchRequest, search_pb2.SearchResponse],
    ) -> float:
        """Parse alpha value from request options.

        Args:
            request: The search request
            context: gRPC context for error reporting

        Returns:
            Alpha value for hybrid search
        """
        alpha = self.config.hybrid_alpha
        if "alpha" in request.options:
            try:
                alpha = float(request.options["alpha"])
                if not 0.0 <= alpha <= 1.0:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"alpha must be between 0.0 and 1.0, got {alpha}")
            except ValueError:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid alpha value: {request.options['alpha']}")
        return alpha

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
                metadata={str(k): str(v) for k, v in source_dict.get("metadata", {}).items()},
            )
            for source_dict in result["sources"]
        ]

        metadata = {
            "mode": result["metadata"]["mode"],
            "top_k": str(result["metadata"]["top_k"]),
            "namespace": result["metadata"]["namespace"],
            "cache_hit": str(result["metadata"].get("cache_hit", False)),
            "num_sources": str(result["metadata"]["num_sources"]),
        }

        return search_pb2.SearchResponse(answer=result["answer"], sources=sources, metadata=metadata)

    async def _check_dependency(
        self,
        name: str,
        check_fn: Callable[[], bool] | Callable[[], Awaitable[bool]],
        is_async: bool = False,
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

    def _determine_health_status(
        self, all_critical_healthy: bool, openai_is_critical: bool, openai_ok: bool
    ) -> tuple[common_pb2.HealthCheckResponse.Status.ValueType, str]:
        """Determine overall health status and message.

        Args:
            all_critical_healthy: Whether all critical dependencies are healthy
            openai_is_critical: Whether OpenAI is considered critical
            openai_ok: Whether OpenAI health check passed

        Returns:
            Tuple of (status_code, message)
        """
        if not all_critical_healthy:
            return (
                common_pb2.HealthCheckResponse.UNHEALTHY,
                "Search service is unhealthy (critical dependencies down)",
            )

        if not openai_is_critical and not openai_ok:
            return (
                common_pb2.HealthCheckResponse.HEALTHY,
                "Search service is healthy (dev mode: OpenAI disabled)",
            )

        return (common_pb2.HealthCheckResponse.HEALTHY, "Search service is healthy")

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
        active_requests.labels(method="Search").inc()
        try:
            with track_latency(request_duration, {"method": "Search"}):
                # Validate and extract parameters
                query, namespace, top_k, mode, alpha = await self._validate_search_params(request, context)

                logger.info(f"Search request: query='{query[:50]}...', mode={mode}, top_k={top_k}, namespace={namespace}")

                # Execute search pipeline
                # Cast mode to literal type after validation
                search_mode = cast(Literal["vector", "bm25", "hybrid"], mode)
                result = await self.pipeline.search(
                    query=query,
                    top_k=top_k,
                    mode=search_mode,
                    alpha=alpha,
                    namespace=namespace,
                    openai_max_tokens=self.config.openai_max_tokens,
                    openai_temperature=self.config.openai_temperature,
                )

                # Build and return response
                response = self._build_search_response(result)
                logger.info(f"Search completed: {len(response.sources)} sources, cache_hit={result['metadata'].get('cache_hit', False)}")

            requests_total.labels(method="Search", status="success").inc()
            return response

        except grpc.RpcError:
            # Re-raise gRPC errors (already aborted)
            requests_total.labels(method="Search", status="error").inc()
            raise

        except Exception as e:
            logger.error(f"Unexpected error in Search: {e}", exc_info=True)
            requests_total.labels(method="Search", status="error").inc()
            errors_total.labels(method="Search", error_type=type(e).__name__).inc()
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

        finally:
            active_requests.labels(method="Search").dec()

    async def HealthCheck(
        self,
        request: common_pb2.HealthCheckRequest,
        context: grpc.aio.ServicerContext[common_pb2.HealthCheckRequest, common_pb2.HealthCheckResponse],
    ) -> common_pb2.HealthCheckResponse:
        """Health check endpoint.

        Checks all critical dependencies:
        - Weaviate (critical)
        - Embedding Service (critical)
        - OpenAI API (critical)

        Args:
            request: HealthCheckRequest (empty)
            context: gRPC context

        Returns:
            HealthCheckResponse with aggregate status
        """
        try:
            # Check all dependencies
            weaviate_status, weaviate_ok = await self._check_dependency("Weaviate", self.pipeline.retriever.health_check, is_async=False)
            embedding_status, embedding_ok = await self._check_dependency(
                "Embedding Service", self.pipeline.embedding_client.health_check, is_async=True
            )
            openai_status, openai_ok = await self._check_dependency("OpenAI", self.pipeline.llm_client.health_check, is_async=True)

            dependencies = {
                "weaviate": weaviate_status,
                "embedding_service": embedding_status,
                "openai": openai_status,
            }

            # OpenAI is only critical if not using placeholder key
            openai_is_critical = self.config.openai_api_key != "sk-your-key-here"
            all_critical_healthy = weaviate_ok and embedding_ok and (openai_ok or not openai_is_critical)

            # Determine status and message
            status, message = self._determine_health_status(all_critical_healthy, openai_is_critical, openai_ok)

            return common_pb2.HealthCheckResponse(status=status, dependencies=dependencies, message=message)

        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            return common_pb2.HealthCheckResponse(
                status=common_pb2.HealthCheckResponse.UNHEALTHY,
                dependencies={},
                message=f"Health check failed: {e}",
            )
