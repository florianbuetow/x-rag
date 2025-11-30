"""Pytest configuration and fixtures."""

import pytest
from src.core.document import CoreDocument


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
