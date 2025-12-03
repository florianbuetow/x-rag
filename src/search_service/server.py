"""gRPC server implementation for Search Service."""

import logging
from typing import Literal, cast

import grpc

from src.pipelines.search_pipeline import SearchPipeline
from src.proto_gen import common_pb2, search_pb2, search_pb2_grpc
from src.search_service.config import SearchServiceConfig

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
        try:
            # Validate request
            if not request.query:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Query cannot be empty")

            # Extract parameters with defaults
            query = request.query
            namespace = request.namespace or "default"
            top_k = request.top_k or self.config.default_top_k
            mode = request.mode or self.config.default_mode

            # Validate top_k
            if top_k <= 0:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"top_k must be positive, got {top_k}")
            if top_k > 100:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"top_k too large (max 100), got {top_k}")

            # Validate mode
            valid_modes = ["vector", "bm25", "hybrid"]
            if mode not in valid_modes:
                await context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}",
                )

            # Extract alpha from options (for hybrid mode)
            alpha = self.config.hybrid_alpha
            if "alpha" in request.options:
                try:
                    alpha = float(request.options["alpha"])
                    if not 0.0 <= alpha <= 1.0:
                        await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"alpha must be between 0.0 and 1.0, got {alpha}")
                except ValueError:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid alpha value: {request.options['alpha']}")

            # Log search request
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

            # Build protobuf response
            sources = []
            for source_dict in result["sources"]:
                sources.append(
                    search_pb2.Source(
                        id=source_dict["id"],
                        content=source_dict["content"],
                        score=source_dict["score"],
                        metadata=source_dict["metadata"],
                    )
                )

            # Add metadata
            metadata = {
                "mode": result["metadata"]["mode"],
                "top_k": str(result["metadata"]["top_k"]),
                "namespace": result["metadata"]["namespace"],
                "cache_hit": str(result["metadata"]["cache_hit"]),
                "num_sources": str(result["metadata"]["num_sources"]),
            }

            response = search_pb2.SearchResponse(
                answer=result["answer"],
                sources=sources,
                metadata=metadata,
            )

            logger.info(f"Search completed: {len(sources)} sources, cache_hit={result['metadata']['cache_hit']}")
            return response

        except grpc.RpcError:
            # Re-raise gRPC errors (already aborted)
            raise

        except Exception as e:
            logger.error(f"Unexpected error in Search: {e}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

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
            dependencies: dict[str, str] = {}
            all_critical_healthy = True

            # Check Weaviate (critical)
            try:
                weaviate_healthy = self.pipeline.retriever.health_check()
                dependencies["weaviate"] = "HEALTHY" if weaviate_healthy else "UNHEALTHY"
                if not weaviate_healthy:
                    all_critical_healthy = False
            except Exception as e:
                logger.warning(f"Weaviate health check failed: {e}")
                dependencies["weaviate"] = "UNHEALTHY"
                all_critical_healthy = False

            # Check Embedding Service (critical)
            try:
                embedding_healthy = await self.pipeline.embedding_client.health_check()
                dependencies["embedding_service"] = "HEALTHY" if embedding_healthy else "UNHEALTHY"
                if not embedding_healthy:
                    all_critical_healthy = False
            except Exception as e:
                logger.warning(f"Embedding Service health check failed: {e}")
                dependencies["embedding_service"] = "UNHEALTHY"
                all_critical_healthy = False

            # Check OpenAI (critical only if not using placeholder key)
            openai_is_critical = self.config.openai_api_key != "sk-your-key-here"
            try:
                openai_healthy = await self.pipeline.llm_client.health_check()
                dependencies["openai"] = "HEALTHY" if openai_healthy else "UNHEALTHY"
                if not openai_healthy and openai_is_critical:
                    all_critical_healthy = False
            except Exception as e:
                logger.warning(f"OpenAI health check failed: {e}")
                dependencies["openai"] = "UNHEALTHY"
                if openai_is_critical:
                    all_critical_healthy = False

            # Determine overall status
            if all_critical_healthy:
                # If using placeholder key and OpenAI is down, treat as healthy (dev mode)
                if not openai_is_critical and dependencies.get("openai") == "UNHEALTHY":
                    status = common_pb2.HealthCheckResponse.HEALTHY
                    message = "Search service is healthy (dev mode: OpenAI disabled)"
                else:
                    status = common_pb2.HealthCheckResponse.HEALTHY
                    message = "Search service is healthy"
            else:
                status = common_pb2.HealthCheckResponse.UNHEALTHY
                message = "Search service is unhealthy (critical dependencies down)"

            return common_pb2.HealthCheckResponse(
                status=status,
                dependencies=dependencies,
                message=message,
            )

        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            return common_pb2.HealthCheckResponse(
                status=common_pb2.HealthCheckResponse.UNHEALTHY,
                dependencies={},
                message=f"Health check failed: {e}",
            )
