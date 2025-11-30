"""Core document model for the RAG platform.

Framework-agnostic document representation that can be converted
to/from Haystack documents and other formats.
"""

from dataclasses import dataclass, field
from typing import Any


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
        return self.metadata.get("namespace", "default")

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
            metadata=data.get("metadata", {}),
            score=data.get("score"),
        )
