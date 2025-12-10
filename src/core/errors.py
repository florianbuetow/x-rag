"""Custom exceptions for the RAG platform."""


class XRagError(Exception):
    """Base exception for all X-RAG errors."""

    pass


class ConfigurationError(XRagError):
    """Raised when configuration is invalid or missing."""

    pass


class ServiceUnavailableError(XRagError):
    """Raised when a required service is unavailable."""

    def __init__(self, service_name: str, details: str) -> None:
        self.service_name = service_name
        self.details = details
        message = f"Service '{service_name}' is unavailable"
        if details:
            message += f": {details}"
        super().__init__(message)


class DocumentNotFoundError(XRagError):
    """Raised when a document is not found."""

    def __init__(self, doc_id: str, namespace: str) -> None:
        self.doc_id = doc_id
        self.namespace = namespace
        super().__init__(f"Document '{doc_id}' not found in namespace '{namespace}'")


class EmbeddingError(XRagError):
    """Raised when embedding generation fails."""

    pass


class SearchError(XRagError):
    """Raised when search operation fails."""

    pass


class IngestionError(XRagError):
    """Raised when document ingestion fails."""

    pass
