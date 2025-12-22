"""gRPC server implementation for Embedding Service."""

import logging

import grpc

from src.common.health import HealthChecker
from src.common.metrics import track_latency
from src.core.errors import ServiceUnavailableError
from src.embedding_service.generators.embedding_generator import EmbeddingGenerator
from src.embedding_service.metrics import (
    dec_active_requests,
    get_backend_duration,
    get_request_duration,
    inc_active_requests,
    inc_embeddings_total,
    inc_errors_total,
    inc_requests_total,
    record_batch_size,
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
        inc_active_requests("Embed")
        try:
            with track_latency(get_request_duration(), {"method": "Embed"}):
                # Validate request
                if not request.text:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Text cannot be empty")

                # Use default model if not specified
                model = request.model or self.default_model

                # Convert options map to dict
                options = dict(request.options) if request.options else {}

                # Generate embedding
                logger.debug(f"Generating embedding for text (model={model})")
                with track_latency(get_backend_duration(), {"model": model}):
                    embedding = await self.generator.embed(request.text, model, **options)
                    dimension = self.generator.get_dimension(model)

                # Record embedding generated
                inc_embeddings_total(model, 1)

            inc_requests_total("Embed", "success")
            return embedding_pb2.EmbedResponse(
                embedding=embedding,
                dimension=dimension,
                model=model,
            )

        except grpc.RpcError:
            # Re-raise gRPC errors (already aborted)
            inc_requests_total("Embed", "error")
            raise

        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable: {e}")
            inc_requests_total("Embed", "error")
            inc_errors_total("Embed", "ServiceUnavailableError")
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(e))

        except ValueError as e:
            logger.error(f"Invalid request: {e}")
            inc_requests_total("Embed", "error")
            inc_errors_total("Embed", "ValueError")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        except Exception as e:
            logger.error(f"Unexpected error in Embed: {e}")
            inc_requests_total("Embed", "error")
            inc_errors_total("Embed", type(e).__name__)
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

        finally:
            dec_active_requests("Embed")

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
        inc_active_requests("EmbedBatch")
        try:
            with track_latency(get_request_duration(), {"method": "EmbedBatch"}):
                # Validate request
                if not request.texts:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Texts list cannot be empty")

                # Use default model if not specified
                model = request.model or self.default_model

                # Convert options map to dict
                options = dict(request.options) if request.options else {}

                # Record batch size
                num_texts = len(request.texts)
                record_batch_size(num_texts)

                # Generate embeddings
                logger.debug(f"Generating {num_texts} embeddings in batch (model={model})")
                with track_latency(get_backend_duration(), {"model": model}):
                    embeddings = await self.generator.embed_batch(list(request.texts), model, **options)
                    dimension = self.generator.get_dimension(model)

                # Record embeddings generated
                inc_embeddings_total(model, num_texts)

                # Build response with individual EmbedResponse messages
                embed_responses = [
                    embedding_pb2.EmbedResponse(
                        embedding=emb,
                        dimension=dimension,
                        model=model,
                    )
                    for emb in embeddings
                ]

            inc_requests_total("EmbedBatch", "success")
            return embedding_pb2.EmbedBatchResponse(embeddings=embed_responses)

        except grpc.RpcError:
            # Re-raise gRPC errors (already aborted)
            inc_requests_total("EmbedBatch", "error")
            raise

        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable: {e}")
            inc_requests_total("EmbedBatch", "error")
            inc_errors_total("EmbedBatch", "ServiceUnavailableError")
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(e))

        except ValueError as e:
            logger.error(f"Invalid request: {e}")
            inc_requests_total("EmbedBatch", "error")
            inc_errors_total("EmbedBatch", "ValueError")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        except Exception as e:
            logger.error(f"Unexpected error in EmbedBatch: {e}")
            inc_requests_total("EmbedBatch", "error")
            inc_errors_total("EmbedBatch", type(e).__name__)
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

        finally:
            dec_active_requests("EmbedBatch")

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
