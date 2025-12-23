"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock, Mock

import grpc
import pytest

from src.core.document import CoreDocument

# ============================================
# Document Fixtures
# ============================================


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        CoreDocument(
            id="doc1",
            content="Machine learning is a subset of artificial intelligence.",
            metadata={"namespace": "wiki", "title": "Machine Learning", "source": "wikipedia"},
        ),
        CoreDocument(
            id="doc2",
            content="Deep learning is a type of machine learning based on neural networks.",
            metadata={"namespace": "wiki", "title": "Deep Learning", "source": "wikipedia"},
        ),
        CoreDocument(
            id="doc3",
            content="Natural language processing deals with text and language understanding.",
            metadata={"namespace": "wiki", "title": "NLP", "source": "wikipedia"},
        ),
    ]


@pytest.fixture
def test_query():
    """Sample query for testing."""
    return "What is machine learning?"


@pytest.fixture
def sample_document():
    """Single sample document for testing."""
    return CoreDocument(
        id="test-doc",
        content="This is a test document.",
        metadata={"namespace": "test", "source": "pytest"},
        score=0.95,
    )


# ============================================
# gRPC Context Fixtures
# ============================================


class GrpcAbortException(grpc.RpcError):
    """Exception raised when gRPC context.abort() is called.

    Inherits from grpc.RpcError so that server code that catches
    RpcError will properly re-raise this exception.
    """

    def __init__(self, code, message):
        self._code = code
        self._message = message
        super().__init__(f"{code}: {message}")

    def code(self):
        """Return the gRPC status code."""
        return self._code

    def details(self):
        """Return the error details/message."""
        return self._message


@pytest.fixture
def mock_grpc_context():
    """Mock gRPC servicer context for sync tests."""
    context = Mock()

    def abort_side_effect(code, message):
        raise GrpcAbortException(code, message)

    context.abort = Mock(side_effect=abort_side_effect)
    return context


@pytest.fixture
def mock_async_grpc_context():
    """Mock async gRPC servicer context."""
    context = AsyncMock()

    async def async_abort_side_effect(code, message):
        raise GrpcAbortException(code, message)

    context.abort = AsyncMock(side_effect=async_abort_side_effect)
    return context


# ============================================
# Search Service Fixtures
# ============================================


@pytest.fixture
def mock_search_pipeline():
    """Mock SearchPipeline for Search Service tests."""
    pipeline = AsyncMock()
    pipeline.search = AsyncMock()

    # Mock retriever
    pipeline.retriever = Mock()
    pipeline.retriever.health_check = Mock(return_value=True)

    # Mock embedding client
    pipeline.embedding_client = AsyncMock()
    pipeline.embedding_client.health_check = AsyncMock(return_value=True)

    # Mock LLM client
    pipeline.llm_client = AsyncMock()
    pipeline.llm_client.health_check = AsyncMock(return_value=True)

    return pipeline


@pytest.fixture
def mock_embedding_service_client():
    """Mock EmbeddingServiceClient for Search Service tests."""
    client = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.embed = AsyncMock(return_value=[0.1] * 384)  # Mock embedding vector
    return client


@pytest.fixture
def search_service_config(monkeypatch):
    """Search service configuration fixture.

    Uses environment variables to create a properly configured instance.
    """
    from src.search_service.config import SearchServiceConfig

    # Set required environment variables for SearchServiceConfig
    test_env = {
        "SERVICE_NAME": "search-service-test",
        "PORT": "50052",
        "ENABLE_REFLECTION": "true",
        "WEAVIATE_URL": "http://localhost:8081",
        "EMBEDDING_SERVICE_ADDR": "localhost:50051",
        "EMBEDDING_SERVICE_TIMEOUT": "30",
        "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    return SearchServiceConfig()


@pytest.fixture
def search_service_config_dev_mode(monkeypatch):
    """Search service configuration with placeholder key (dev mode).

    Uses environment variables to create a properly configured instance.
    """
    from src.search_service.config import SearchServiceConfig

    # Set required environment variables for SearchServiceConfig
    test_env = {
        "SERVICE_NAME": "search-service-test",
        "PORT": "50052",
        "ENABLE_REFLECTION": "true",
        "WEAVIATE_URL": "http://localhost:8081",
        "EMBEDDING_SERVICE_ADDR": "localhost:50051",
        "EMBEDDING_SERVICE_TIMEOUT": "30",
        "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    return SearchServiceConfig()


@pytest.fixture
def sample_search_result():
    """Sample search result from pipeline."""
    return {
        "answer": "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
        "sources": [
            {
                "id": "doc1",
                "content": "Machine learning is a subset of artificial intelligence.",
                "score": 0.95,
                "metadata": {"title": "Machine Learning", "namespace": "wiki"},
            },
            {
                "id": "doc2",
                "content": "Deep learning is a type of machine learning based on neural networks.",
                "score": 0.85,
                "metadata": {"title": "Deep Learning", "namespace": "wiki"},
            },
        ],
        "metadata": {
            "mode": "hybrid",
            "top_k": 10,
            "namespace": "test-ns",
            "cache_hit": False,
            "num_sources": 2,
        },
    }


# ============================================
# Embedding Service Fixtures
# ============================================


@pytest.fixture
def mock_embedding_generator():
    """Mock EmbeddingGenerator for Embedding Service tests."""
    generator = AsyncMock()
    generator.embed = AsyncMock(return_value=[0.1, 0.2, 0.3] * 512)  # 1536 dims
    generator.embed_batch = AsyncMock(
        return_value=[
            [0.1, 0.2, 0.3] * 512,
            [0.4, 0.5, 0.6] * 512,
        ]
    )
    generator.get_dimension = Mock(return_value=1536)
    return generator


@pytest.fixture
def mock_dataset_config():
    """Mock DatasetConfig for testing."""
    config = Mock()

    # Embedding config
    config.embedding = Mock()
    config.embedding.provider = "hash_based"
    config.embedding.model = "text-embedding-3-small"
    config.embedding.dimension = 1536
    config.embedding.to_embedding_config.return_value = Mock(
        provider=Mock(value="hash_based"),
        model="text-embedding-3-small",
        dimension=1536,
    )

    # LLM config
    config.llm = Mock()
    config.llm.max_tokens = 500
    config.llm.temperature = 0.7

    # Search config
    config.search = Mock()
    config.search.top_k = 10
    config.search.mode = "hybrid"
    config.search.hybrid_alpha = 0.5

    return config


@pytest.fixture
def mock_datasets_loader(mock_dataset_config):
    """Mock DatasetsConfigLoader for testing."""
    loader = Mock()
    loader.list_namespaces.return_value = ["test"]
    loader.get_dataset_config.return_value = mock_dataset_config
    loader.has_dataset.return_value = True
    return loader


@pytest.fixture
def embedding_service_config(monkeypatch):
    """Embedding service configuration fixture.

    Uses environment variables to create a properly configured instance.
    """
    from src.embedding_service.config import EmbeddingServiceConfig

    # Set required environment variables for EmbeddingServiceConfig
    test_env = {
        "SERVICE_NAME": "embedding-service-test",
        "PORT": "50051",
        "ENABLE_REFLECTION": "true",
        "DATASETS_CONFIG_PATH": "config/test/datasets_config.yaml",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    return EmbeddingServiceConfig()


# ============================================
# Indexer Fixtures
# ============================================


@pytest.fixture
def mock_kafka_consumer():
    """Mock AIOKafkaConsumer."""
    consumer = AsyncMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    consumer._client = Mock()
    consumer._client.fetch_all_metadata = AsyncMock()
    return consumer


@pytest.fixture
def mock_kafka_message():
    """Mock Kafka message."""
    message = Mock()
    message.value = b'{"doc_id": "test-123", "event_type": "created"}'
    message.topic = "document-changes"
    message.partition = 0
    message.offset = 42
    return message


# ============================================
# Weaviate Fixtures
# ============================================


@pytest.fixture
def mock_weaviate_client():
    """Mock Weaviate client."""
    client = Mock()
    collection = Mock()
    client.collections.get = Mock(return_value=collection)
    client.close = Mock()
    return client


# ============================================
# Ingestion API Fixtures
# ============================================


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client."""
    client = Mock()
    client.store_document = Mock(return_value="bucket/key/path")
    client.health_check = Mock(return_value=True)
    return client


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer client."""
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.publish = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    return client
