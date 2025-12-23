"""gRPC server implementation for Embedding Service."""

import logging

import grpc

from src.common.dataset_config import DatasetsConfigLoader
from src.common.health import HealthChecker
from src.common.metrics import track_latency
from src.core.errors import ConfigurationError, ServiceUnavailableError
from src.embedding_service.generators.embedding_generator import EmbeddingGenerator
from src.embedding_service.generators.factory import EmbeddingGeneratorFactory
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
    Namespace-aware: uses dataset-specific embedding models based on namespace parameter.
    """

    def __init__(self, datasets_config_path: str) -> None:
        """Initialize servicer with dataset config loader.

        Args:
            datasets_config_path: Path to datasets_config.yaml file.
        """
        self.datasets_loader = DatasetsConfigLoader(datasets_config_path)
        self._generator_cache: dict[str, EmbeddingGenerator] = {}
        self.health_checker = HealthChecker()

        namespaces = self.datasets_loader.list_namespaces()
        logger.info(f"EmbeddingServicer initialized with {len(namespaces)} datasets: {namespaces}")

    def _get_generator(self, namespace: str) -> EmbeddingGenerator:
        """Get or create embedding generator for namespace.

        Args:
            namespace: Dataset namespace.

        Returns:
            Embedding generator for the namespace.

        Raises:
            ConfigurationError: If namespace is unknown.
        """
        # Check cache first
        if namespace in self._generator_cache:
            return self._generator_cache[namespace]

        # Load dataset config and create generator
        logger.info(f"Creating embedding generator for namespace: {namespace}")
        dataset_config = self.datasets_loader.get_dataset_config(namespace)
        embedding_config = dataset_config.embedding.to_embedding_config()

        generator = EmbeddingGeneratorFactory.create_from_config(embedding_config)

        # Cache for future requests
        self._generator_cache[namespace] = generator
        logger.info(f"Cached generator for '{namespace}': provider={embedding_config.provider.value}, model={embedding_config.model}")

        return generator

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

                # Extract namespace from options
                options = dict(request.options) if request.options else {}
                if "namespace" not in options:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "namespace is required in options")
                namespace = options["namespace"]

                # Get namespace-specific generator
                try:
                    generator = self._get_generator(namespace)
                except ConfigurationError as e:
                    logger.error(f"Unknown namespace: {namespace}")
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

                # Model is required - no defaults
                model = request.model
                if not model:
                    logger.error("Model is required")
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "model field is required")

                # Generate embedding
                logger.debug(f"Generating embedding for namespace={namespace}, model={model}")
                with track_latency(get_backend_duration(), {"namespace": namespace}):
                    embedding = await generator.embed(request.text, model)
                    dimension = generator.get_dimension(model)

                # Record embedding generated
                inc_embeddings_total(model, 1)

            inc_requests_total("Embed", "success")
            return embedding_pb2.EmbedResponse(
                embedding=embedding,
                dimension=dimension,
                model=model or namespace,
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

                # Extract namespace from options
                options = dict(request.options) if request.options else {}
                if "namespace" not in options:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "namespace is required in options")
                namespace = options["namespace"]

                # Get namespace-specific generator
                try:
                    generator = self._get_generator(namespace)
                except ConfigurationError as e:
                    logger.error(f"Unknown namespace: {namespace}")
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

                # Model is required - no defaults
                model = request.model
                if not model:
                    logger.error("Model is required")
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "model field is required")

                # Record batch size
                num_texts = len(request.texts)
                record_batch_size(num_texts)

                # Generate embeddings
                logger.debug(f"Generating {num_texts} embeddings in batch (namespace={namespace}, model={model})")
                with track_latency(get_backend_duration(), {"namespace": namespace}):
                    embeddings = await generator.embed_batch(list(request.texts), model)
                    dimension = generator.get_dimension(model)

                # Record embeddings generated
                inc_embeddings_total(model, num_texts)

                # Build response with individual EmbedResponse messages
                embed_responses = [
                    embedding_pb2.EmbedResponse(
                        embedding=emb,
                        dimension=dimension,
                        model=model or "",
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
            # Check if datasets config loader has at least one namespace configured
            try:
                namespaces = self.datasets_loader.list_namespaces()
                config_healthy = len(namespaces) > 0
            except Exception as e:
                logger.warning(f"Config health check failed: {e}")
                config_healthy = False

            if config_healthy:
                return common_pb2.HealthCheckResponse(
                    status=common_pb2.HealthCheckResponse.HEALTHY,
                    dependencies={"datasets_config": "HEALTHY"},
                    message="Embedding service is healthy",
                )
            else:
                return common_pb2.HealthCheckResponse(
                    status=common_pb2.HealthCheckResponse.UNHEALTHY,
                    dependencies={"datasets_config": "UNHEALTHY"},
                    message="No datasets configured",
                )

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return common_pb2.HealthCheckResponse(
                status=common_pb2.HealthCheckResponse.UNHEALTHY,
                dependencies={},
                message=f"Health check failed: {e}",
            )
