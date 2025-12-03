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
def search_service_config():
    """Search service configuration fixture."""
    from src.search_service.config import SearchServiceConfig

    return SearchServiceConfig(
        openai_api_key="sk-test-key-12345",
        default_top_k=10,
        default_mode="hybrid",
        hybrid_alpha=0.5,
        openai_max_tokens=500,
        openai_temperature=0.7,
    )


@pytest.fixture
def search_service_config_dev_mode():
    """Search service configuration with placeholder key (dev mode)."""
    from src.search_service.config import SearchServiceConfig

    return SearchServiceConfig(
        openai_api_key="sk-your-key-here",
        default_top_k=10,
        default_mode="hybrid",
        hybrid_alpha=0.5,
    )


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
            "namespace": "default",
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
