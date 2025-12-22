"""Core document model for the RAG platform.

Framework-agnostic document representation that can be converted
to/from Haystack documents and other formats.
"""

from dataclasses import dataclass, field
from typing import Any, cast

from pydantic import BaseModel, Field


@dataclass
class CoreDocument:
    """Framework-agnostic document representation.

    This is the canonical document model used throughout the system.
    It can be converted to/from Haystack Document objects.
    """

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None

    @property
    def namespace(self) -> str:
        """Get document namespace for multi-tenancy.

        Returns:
            Namespace string (default: "default")
        """
        if "namespace" in self.metadata:
            return cast(str, self.metadata["namespace"])
        return "default"

    @property
    def source(self) -> str | None:
        """Get document source.

        Returns:
            Source string or None
        """
        return self.metadata.get("source")

    @property
    def title(self) -> str | None:
        """Get document title.

        Returns:
            Title string or None
        """
        return self.metadata.get("title")

    def with_score(self, score: float) -> "CoreDocument":
        """Create a new document with updated score.

        Args:
            score: New relevance score

        Returns:
            New CoreDocument instance with updated score
        """
        return CoreDocument(
            id=self.id,
            content=self.content,
            metadata=self.metadata.copy(),
            score=score,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with document data
        """
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoreDocument":
        """Create document from dictionary.

        Args:
            data: Dictionary with document data

        Returns:
            CoreDocument instance
        """
        return cls(
            id=data["id"],
            content=data["content"],
            metadata=data["metadata"] if "metadata" in data else {},
            score=data["score"] if "score" in data else None,
        )


class MinimumDocument(BaseModel):
    """Minimum required fields for document ingestion.

    This validates documents before indexing. Only these fields are required;
    metadata can contain any additional fields which will be stored in Weaviate.

    All ingested documents must have:
    - text: The document content to be indexed
    - namespace: Dataset identifier (e.g., "nutritionfacts")
    - doc_id: Unique document identifier

    Optional metadata can include title, author, date, source, etc. These
    fields will be dynamically added to the Weaviate collection schema.
    """

    text: str = Field(..., min_length=1, description="Document content")
    namespace: str = Field(..., pattern="^[a-z0-9-]+$", description="Dataset namespace")
    doc_id: str = Field(..., min_length=1, description="Unique document identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata (title, author, date, etc.)")


class MinimumDocumentChunk(BaseModel):
    """Minimum required fields for chunks stored in Weaviate.

    Chunks are created by splitting MinimumDocument.text during indexing.
    All chunks from the same document share doc_id but have unique chunk_ids.

    Required fields:
    - content: Chunk text content (subset of original document text)
    - namespace: Dataset namespace (inherited from document)
    - doc_id: Source document ID (inherited from document)
    - chunk_id: Unique chunk identifier (format: {doc_id}:chunk:{index})
    - chunk_index: Position of chunk in document (0-indexed)

    Metadata from the original document is inherited by all chunks.
    """

    content: str = Field(..., min_length=1, description="Chunk text content")
    namespace: str = Field(..., pattern="^[a-z0-9-]+$", description="Dataset namespace")
    doc_id: str = Field(..., min_length=1, description="Source document ID")
    chunk_id: str = Field(..., min_length=1, description="Unique chunk identifier (doc_id + chunk_index)")
    chunk_index: int = Field(..., ge=0, description="Position of chunk in document (0-indexed)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata inherited from document")

    @property
    def collection_name(self) -> str:
        """Get Weaviate collection name for this chunk's namespace.

        Returns:
            Collection name in format: DocumentChunk_{namespace}
        """
        return f"DocumentChunk_{self.namespace}"
