"""Unit tests for src/core/errors.py.

Tests cover:
- XRagError base exception
- ConfigurationError
- ServiceUnavailableError with attributes
- DocumentNotFoundError with attributes
- EmbeddingError
- SearchError
- IngestionError
- Error inheritance hierarchy
- String representations
"""

import pytest

from src.core.errors import (
    ConfigurationError,
    DocumentNotFoundError,
    EmbeddingError,
    IngestionError,
    SearchError,
    ServiceUnavailableError,
    XRagError,
)


class TestXRagError:
    """Tests for XRagError base exception."""

    def test_xrag_error_is_exception(self):
        """Tests that XRagError inherits from Exception."""
        assert issubclass(XRagError, Exception)

    def test_xrag_error_can_be_raised(self):
        """Tests that XRagError can be raised and caught."""
        with pytest.raises(XRagError):
            raise XRagError("Test error")

    def test_xrag_error_message(self):
        """Tests that XRagError preserves message."""
        error = XRagError("Custom message")
        assert str(error) == "Custom message"

    def test_xrag_error_empty_message(self):
        """Tests that XRagError works with empty message."""
        error = XRagError()
        assert str(error) == ""


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_configuration_error_inherits_from_xrag_error(self):
        """Tests that ConfigurationError inherits from XRagError."""
        assert issubclass(ConfigurationError, XRagError)

    def test_configuration_error_can_be_caught_as_xrag_error(self):
        """Tests that ConfigurationError can be caught as XRagError."""
        with pytest.raises(XRagError):
            raise ConfigurationError("Missing config")

    def test_configuration_error_message(self):
        """Tests that ConfigurationError preserves message."""
        error = ConfigurationError("OPENAI_API_KEY is required")
        assert str(error) == "OPENAI_API_KEY is required"


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError."""

    def test_service_unavailable_error_inherits_from_xrag_error(self):
        """Tests that ServiceUnavailableError inherits from XRagError."""
        assert issubclass(ServiceUnavailableError, XRagError)

    def test_service_unavailable_error_with_service_name_only(self):
        """Tests ServiceUnavailableError with service name and empty details."""
        error = ServiceUnavailableError("Weaviate", details="")

        assert error.service_name == "Weaviate"
        assert error.details == ""
        assert str(error) == "Service 'Weaviate' is unavailable"

    def test_service_unavailable_error_with_details(self):
        """Tests ServiceUnavailableError with service name and details."""
        error = ServiceUnavailableError("Redis", details="Connection refused")

        assert error.service_name == "Redis"
        assert error.details == "Connection refused"
        assert str(error) == "Service 'Redis' is unavailable: Connection refused"

    def test_service_unavailable_error_attributes_accessible(self):
        """Tests that service_name and details are accessible as attributes."""
        error = ServiceUnavailableError("Kafka", details="Broker timeout")

        assert hasattr(error, "service_name")
        assert hasattr(error, "details")
        assert error.service_name == "Kafka"
        assert error.details == "Broker timeout"

    def test_service_unavailable_error_can_be_caught_as_xrag_error(self):
        """Tests that ServiceUnavailableError can be caught as XRagError."""
        with pytest.raises(XRagError) as exc_info:
            raise ServiceUnavailableError("TestService", details="")

        assert exc_info.value.service_name == "TestService"


class TestDocumentNotFoundError:
    """Tests for DocumentNotFoundError."""

    def test_document_not_found_error_inherits_from_xrag_error(self):
        """Tests that DocumentNotFoundError inherits from XRagError."""
        assert issubclass(DocumentNotFoundError, XRagError)

    def test_document_not_found_error_with_default_namespace(self):
        """Tests DocumentNotFoundError with default namespace."""
        error = DocumentNotFoundError("doc-123", namespace="default")

        assert error.doc_id == "doc-123"
        assert error.namespace == "default"
        assert str(error) == "Document 'doc-123' not found in namespace 'default'"

    def test_document_not_found_error_with_custom_namespace(self):
        """Tests DocumentNotFoundError with custom namespace."""
        error = DocumentNotFoundError("doc-456", namespace="tenant-789")

        assert error.doc_id == "doc-456"
        assert error.namespace == "tenant-789"
        assert str(error) == "Document 'doc-456' not found in namespace 'tenant-789'"

    def test_document_not_found_error_attributes_accessible(self):
        """Tests that doc_id and namespace are accessible as attributes."""
        error = DocumentNotFoundError("test-doc", namespace="test-ns")

        assert hasattr(error, "doc_id")
        assert hasattr(error, "namespace")

    def test_document_not_found_error_can_be_caught_as_xrag_error(self):
        """Tests that DocumentNotFoundError can be caught as XRagError."""
        with pytest.raises(XRagError) as exc_info:
            raise DocumentNotFoundError("doc-id", namespace="default")

        assert exc_info.value.doc_id == "doc-id"


class TestEmbeddingError:
    """Tests for EmbeddingError."""

    def test_embedding_error_inherits_from_xrag_error(self):
        """Tests that EmbeddingError inherits from XRagError."""
        assert issubclass(EmbeddingError, XRagError)

    def test_embedding_error_can_be_raised(self):
        """Tests that EmbeddingError can be raised."""
        with pytest.raises(EmbeddingError):
            raise EmbeddingError("Failed to generate embedding")

    def test_embedding_error_message(self):
        """Tests that EmbeddingError preserves message."""
        error = EmbeddingError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"

    def test_embedding_error_can_be_caught_as_xrag_error(self):
        """Tests that EmbeddingError can be caught as XRagError."""
        with pytest.raises(XRagError):
            raise EmbeddingError("Test")


class TestSearchError:
    """Tests for SearchError."""

    def test_search_error_inherits_from_xrag_error(self):
        """Tests that SearchError inherits from XRagError."""
        assert issubclass(SearchError, XRagError)

    def test_search_error_can_be_raised(self):
        """Tests that SearchError can be raised."""
        with pytest.raises(SearchError):
            raise SearchError("Search timeout")

    def test_search_error_message(self):
        """Tests that SearchError preserves message."""
        error = SearchError("Invalid query syntax")
        assert str(error) == "Invalid query syntax"

    def test_search_error_can_be_caught_as_xrag_error(self):
        """Tests that SearchError can be caught as XRagError."""
        with pytest.raises(XRagError):
            raise SearchError("Test")


class TestIngestionError:
    """Tests for IngestionError."""

    def test_ingestion_error_inherits_from_xrag_error(self):
        """Tests that IngestionError inherits from XRagError."""
        assert issubclass(IngestionError, XRagError)

    def test_ingestion_error_can_be_raised(self):
        """Tests that IngestionError can be raised."""
        with pytest.raises(IngestionError):
            raise IngestionError("Failed to ingest document")

    def test_ingestion_error_message(self):
        """Tests that IngestionError preserves message."""
        error = IngestionError("Invalid document format")
        assert str(error) == "Invalid document format"

    def test_ingestion_error_can_be_caught_as_xrag_error(self):
        """Tests that IngestionError can be caught as XRagError."""
        with pytest.raises(XRagError):
            raise IngestionError("Test")


class TestErrorHierarchy:
    """Tests for error inheritance hierarchy."""

    def test_all_errors_inherit_from_xrag_error(self):
        """Tests that all custom errors inherit from XRagError."""
        error_classes = [
            ConfigurationError,
            ServiceUnavailableError,
            DocumentNotFoundError,
            EmbeddingError,
            SearchError,
            IngestionError,
        ]

        for error_class in error_classes:
            assert issubclass(error_class, XRagError), f"{error_class.__name__} should inherit from XRagError"

    def test_all_errors_inherit_from_exception(self):
        """Tests that all custom errors inherit from Exception."""
        error_classes = [
            XRagError,
            ConfigurationError,
            ServiceUnavailableError,
            DocumentNotFoundError,
            EmbeddingError,
            SearchError,
            IngestionError,
        ]

        for error_class in error_classes:
            assert issubclass(error_class, Exception), f"{error_class.__name__} should inherit from Exception"

    def test_catch_all_xrag_errors(self):
        """Tests that all errors can be caught with single except XRagError."""
        errors = [
            ConfigurationError("config"),
            ServiceUnavailableError("service", details=""),
            DocumentNotFoundError("doc", namespace="default"),
            EmbeddingError("embed"),
            SearchError("search"),
            IngestionError("ingest"),
        ]

        for error in errors:
            try:
                raise error
            except XRagError:
                pass  # Should be caught
            else:
                pytest.fail(f"{type(error).__name__} was not caught by XRagError")
