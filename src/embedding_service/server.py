"""gRPC server implementation for Embedding Service."""

import logging

import grpc

from src.common.health import HealthChecker
from src.common.metrics import track_latency
from src.common.tracing_utils import trace_embedding_generation
from src.core.errors import ServiceUnavailableError
from src.embedding_service.generators.embedding_generator import EmbeddingGenerator
from src.embedding_service.metrics import (
    active_requests,
    backend_duration,
    batch_size,
    embeddings_total,
    errors_total,
    request_duration,
    requests_total,
)
from src.proto_gen import common_pb2, embedding_pb2, embedding_pb2_grpc

logger = logging.getLogger(__name__)


class EmbeddingServicer(embedding_pb2_grpc.EmbeddingServiceServicer):
    """gRPC servicer for Embedding Service.

    Implements the EmbeddingService gRPC interface defined in embedding.proto.
    """

    def __init__(self, generator: EmbeddingGenerator, default_model: str) -> None:
        """Initialize servicer.

        Args:
            generator: Embedding generator implementation
            default_model: Default model to use if not specified in request
        """
        self.generator = generator
        self.default_model = default_model
        self.health_checker = HealthChecker()
        logger.info(f"EmbeddingServicer initialized with default model: {default_model}")

    async def Embed(
        self,
        request: embedding_pb2.EmbedRequest,
        context: grpc.aio.ServicerContext[embedding_pb2.EmbedRequest, embedding_pb2.EmbedResponse],
    ) -> embedding_pb2.EmbedResponse:
        """Generate embedding for a single text.

        Args:
            request: EmbedRequest with text and model
            context: gRPC context

        Returns:
            EmbedResponse with embedding vector
        """
        active_requests.labels(method="Embed").inc()
        try:
            with track_latency(request_duration, {"method": "Embed"}):
                # Validate request
                if not request.text:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Text cannot be empty")

                # Use default model if not specified
                model = request.model or self.default_model

                # Convert options map to dict
                options = dict(request.options) if request.options else {}

                # Generate embedding
                logger.debug(f"Generating embedding for text (model={model})")
                with (
                    track_latency(backend_duration, {"model": model}),
                    trace_embedding_generation(model=model, chunk_count=1, total_tokens=None) as embed_span,
                ):
                    embedding = await self.generator.embed(request.text, model, **options)
                    dimension = self.generator.get_dimension(model)
                    embed_span.set_attribute("embedding.dimensions", dimension)
                    embed_span.set_attribute("embedding.text_length", len(request.text))

                # Record embedding generated
                embeddings_total.labels(model=model).inc()

            requests_total.labels(method="Embed", status="success").inc()
            return embedding_pb2.EmbedResponse(
                embedding=embedding,
                dimension=dimension,
                model=model,
            )

        except grpc.RpcError:
            # Re-raise gRPC errors (already aborted)
            requests_total.labels(method="Embed", status="error").inc()
            raise

        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable: {e}")
            requests_total.labels(method="Embed", status="error").inc()
            errors_total.labels(method="Embed", error_type="ServiceUnavailableError").inc()
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(e))

        except ValueError as e:
            logger.error(f"Invalid request: {e}")
            requests_total.labels(method="Embed", status="error").inc()
            errors_total.labels(method="Embed", error_type="ValueError").inc()
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        except Exception as e:
            logger.error(f"Unexpected error in Embed: {e}")
            requests_total.labels(method="Embed", status="error").inc()
            errors_total.labels(method="Embed", error_type=type(e).__name__).inc()
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

        finally:
            active_requests.labels(method="Embed").dec()

    async def EmbedBatch(
        self,
        request: embedding_pb2.EmbedBatchRequest,
        context: grpc.aio.ServicerContext[embedding_pb2.EmbedBatchRequest, embedding_pb2.EmbedBatchResponse],
    ) -> embedding_pb2.EmbedBatchResponse:
        """Generate embeddings for multiple texts (batched for efficiency).

        Args:
            request: EmbedBatchRequest with list of texts and model
            context: gRPC context

        Returns:
            EmbedBatchResponse with list of embeddings
        """
        active_requests.labels(method="EmbedBatch").inc()
        try:
            with track_latency(request_duration, {"method": "EmbedBatch"}):
                # Validate request
                if not request.texts:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Texts list cannot be empty")

                # Use default model if not specified
                model = request.model or self.default_model

                # Convert options map to dict
                options = dict(request.options) if request.options else {}

                # Record batch size
                num_texts = len(request.texts)
                batch_size.observe(num_texts)

                # Generate embeddings
                logger.debug(f"Generating {num_texts} embeddings in batch (model={model})")
                with (
                    track_latency(backend_duration, {"model": model}),
                    trace_embedding_generation(model=model, chunk_count=num_texts, total_tokens=None) as embed_span,
                ):
                    embeddings = await self.generator.embed_batch(list(request.texts), model, **options)
                    dimension = self.generator.get_dimension(model)
                    embed_span.set_attribute("embedding.dimensions", dimension)
                    total_text_length = sum(len(t) for t in request.texts)
                    embed_span.set_attribute("embedding.total_text_length", total_text_length)

                # Record embeddings generated
                embeddings_total.labels(model=model).inc(num_texts)

                # Build response with individual EmbedResponse messages
                embed_responses = [
                    embedding_pb2.EmbedResponse(
                        embedding=emb,
                        dimension=dimension,
                        model=model,
                    )
                    for emb in embeddings
                ]

            requests_total.labels(method="EmbedBatch", status="success").inc()
            return embedding_pb2.EmbedBatchResponse(embeddings=embed_responses)

        except grpc.RpcError:
            # Re-raise gRPC errors (already aborted)
            requests_total.labels(method="EmbedBatch", status="error").inc()
            raise

        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable: {e}")
            requests_total.labels(method="EmbedBatch", status="error").inc()
            errors_total.labels(method="EmbedBatch", error_type="ServiceUnavailableError").inc()
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(e))

        except ValueError as e:
            logger.error(f"Invalid request: {e}")
            requests_total.labels(method="EmbedBatch", status="error").inc()
            errors_total.labels(method="EmbedBatch", error_type="ValueError").inc()
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        except Exception as e:
            logger.error(f"Unexpected error in EmbedBatch: {e}")
            requests_total.labels(method="EmbedBatch", status="error").inc()
            errors_total.labels(method="EmbedBatch", error_type=type(e).__name__).inc()
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

        finally:
            active_requests.labels(method="EmbedBatch").dec()

    async def HealthCheck(
        self,
        request: common_pb2.HealthCheckRequest,
        context: grpc.aio.ServicerContext[common_pb2.HealthCheckRequest, common_pb2.HealthCheckResponse],
    ) -> common_pb2.HealthCheckResponse:
        """Health check endpoint.

        Args:
            request: HealthCheckRequest (empty)
            context: gRPC context

        Returns:
            HealthCheckResponse with service status
        """
        try:
            # For embedding service, we mainly check if the generator is accessible
            # We can do a simple check by verifying we can get model dimensions
            try:
                self.generator.get_dimension(self.default_model)
                generator_healthy = True
            except Exception as e:
                logger.warning(f"Backend health check failed: {e}")
                generator_healthy = False

            if generator_healthy:
                return common_pb2.HealthCheckResponse(
                    status=common_pb2.HealthCheckResponse.HEALTHY,
                    dependencies={"generator": "HEALTHY"},
                    message="Embedding service is healthy",
                )
            else:
                return common_pb2.HealthCheckResponse(
                    status=common_pb2.HealthCheckResponse.UNHEALTHY,
                    dependencies={"generator": "UNHEALTHY"},
                    message="Backend is not available",
                )

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return common_pb2.HealthCheckResponse(
                status=common_pb2.HealthCheckResponse.UNHEALTHY,
                dependencies={},
                message=f"Health check failed: {e}",
            )
