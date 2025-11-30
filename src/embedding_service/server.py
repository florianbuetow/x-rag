"""gRPC server implementation for Embedding Service."""

import asyncio
import logging
from typing import Any

import grpc

from src.proto_gen import embedding_pb2, embedding_pb2_grpc, common_pb2
from src.common.health import HealthChecker
from src.core.errors import ServiceUnavailableError
from src.embedding_service.backends.base import EmbeddingBackend

logger = logging.getLogger(__name__)


class EmbeddingServicer(embedding_pb2_grpc.EmbeddingServiceServicer):
    """gRPC servicer for Embedding Service.

    Implements the EmbeddingService gRPC interface defined in embedding.proto.
    """

    def __init__(self, backend: EmbeddingBackend, default_model: str = "text-embedding-3-small"):
        """Initialize servicer.

        Args:
            backend: Embedding backend implementation
            default_model: Default model to use if not specified in request
        """
        self.backend = backend
        self.default_model = default_model
        self.health_checker = HealthChecker()
        logger.info(f"EmbeddingServicer initialized with default model: {default_model}")

    async def Embed(
        self,
        request: embedding_pb2.EmbedRequest,
        context: grpc.aio.ServicerContext,
    ) -> embedding_pb2.EmbedResponse:
        """Generate embedding for a single text.

        Args:
            request: EmbedRequest with text and model
            context: gRPC context

        Returns:
            EmbedResponse with embedding vector
        """
        try:
            # Validate request
            if not request.text:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Text cannot be empty")

            # Use default model if not specified
            model = request.model or self.default_model

            # Convert options map to dict
            options = dict(request.options) if request.options else {}

            # Generate embedding
            logger.debug(f"Generating embedding for text (model={model})")
            embedding = await self.backend.embed(request.text, model, **options)

            # Get dimension
            dimension = self.backend.get_dimension(model)

            return embedding_pb2.EmbedResponse(
                embedding=embedding,
                dimension=dimension,
                model=model,
            )

        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable: {e}")
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(e))

        except ValueError as e:
            logger.error(f"Invalid request: {e}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        except Exception as e:
            logger.error(f"Unexpected error in Embed: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

    async def EmbedBatch(
        self,
        request: embedding_pb2.EmbedBatchRequest,
        context: grpc.aio.ServicerContext,
    ) -> embedding_pb2.EmbedBatchResponse:
        """Generate embeddings for multiple texts (batched for efficiency).

        Args:
            request: EmbedBatchRequest with list of texts and model
            context: gRPC context

        Returns:
            EmbedBatchResponse with list of embeddings
        """
        try:
            # Validate request
            if not request.texts:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Texts list cannot be empty")

            # Use default model if not specified
            model = request.model or self.default_model

            # Convert options map to dict
            options = dict(request.options) if request.options else {}

            # Generate embeddings
            logger.debug(f"Generating {len(request.texts)} embeddings in batch (model={model})")
            embeddings = await self.backend.embed_batch(list(request.texts), model, **options)

            # Get dimension
            dimension = self.backend.get_dimension(model)

            # Build response with individual EmbedResponse messages
            embed_responses = [
                embedding_pb2.EmbedResponse(
                    embedding=emb,
                    dimension=dimension,
                    model=model,
                )
                for emb in embeddings
            ]

            return embedding_pb2.EmbedBatchResponse(embeddings=embed_responses)

        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable: {e}")
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(e))

        except ValueError as e:
            logger.error(f"Invalid request: {e}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        except Exception as e:
            logger.error(f"Unexpected error in EmbedBatch: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {e}")

    async def HealthCheck(
        self,
        request: common_pb2.HealthCheckRequest,
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.HealthCheckResponse:
        """Health check endpoint.

        Args:
            request: HealthCheckRequest (empty)
            context: gRPC context

        Returns:
            HealthCheckResponse with service status
        """
        try:
            # For embedding service, we mainly check if the backend is accessible
            # We can do a simple check by verifying we can get model dimensions
            try:
                self.backend.get_dimension(self.default_model)
                backend_healthy = True
            except Exception as e:
                logger.warning(f"Backend health check failed: {e}")
                backend_healthy = False

            if backend_healthy:
                return common_pb2.HealthCheckResponse(
                    status=common_pb2.HealthCheckResponse.HEALTHY,
                    dependencies={"backend": "HEALTHY"},
                    message="Embedding service is healthy",
                )
            else:
                return common_pb2.HealthCheckResponse(
                    status=common_pb2.HealthCheckResponse.UNHEALTHY,
                    dependencies={"backend": "UNHEALTHY"},
                    message="Backend is not available",
                )

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return common_pb2.HealthCheckResponse(
                status=common_pb2.HealthCheckResponse.UNHEALTHY,
                dependencies={},
                message=f"Health check failed: {e}",
            )
