"""Unit tests for src/core/document.py.

Tests cover:
- CoreDocument creation with valid data
- CoreDocument creation with optional fields
- Property accessors (namespace, source, title)
- with_score method for immutable updates
- Serialization (to_dict)
- Deserialization (from_dict)
"""

import pytest

from src.core.document import CoreDocument


class TestCoreDocumentCreation:
    """Tests for CoreDocument creation and basic functionality."""

    def test_create_document_with_required_fields(self):
        """Tests that document can be created with only required fields."""
        doc = CoreDocument(id="doc-1", content="Test content")

        assert doc.id == "doc-1"
        assert doc.content == "Test content"
        assert doc.metadata == {}
        assert doc.score is None

    def test_create_document_with_all_fields(self):
        """Tests that document can be created with all fields."""
        metadata = {"source": "test.pdf", "page": 1}
        doc = CoreDocument(id="doc-2", content="Full content", metadata=metadata, score=0.95)

        assert doc.id == "doc-2"
        assert doc.content == "Full content"
        assert doc.metadata == metadata
        assert doc.score == 0.95

    def test_create_document_with_empty_content(self):
        """Tests that document can be created with empty content."""
        doc = CoreDocument(id="doc-3", content="")

        assert doc.id == "doc-3"
        assert doc.content == ""

    def test_create_document_with_unicode_content(self):
        """Tests that document handles unicode content correctly."""
        unicode_content = "Hello 世界! Привет мир! 🚀"
        doc = CoreDocument(id="doc-unicode", content=unicode_content)

        assert doc.content == unicode_content

    def test_create_document_with_long_content(self):
        """Tests that document handles long content correctly."""
        long_content = "x" * 100000
        doc = CoreDocument(id="doc-long", content=long_content)

        assert len(doc.content) == 100000


class TestCoreDocumentProperties:
    """Tests for CoreDocument property accessors."""

    def test_namespace_raises_error_when_not_set(self):
        """Tests that namespace raises ValueError when not in metadata."""
        doc = CoreDocument(id="doc-1", content="content")

        with pytest.raises(ValueError, match="Document missing required 'namespace' in metadata"):
            _ = doc.namespace

    def test_namespace_returns_value_when_set(self):
        """Tests that namespace returns correct value when in metadata."""
        doc = CoreDocument(id="doc-1", content="content", metadata={"namespace": "tenant-123"})

        assert doc.namespace == "tenant-123"

    def test_source_returns_none_when_not_set(self):
        """Tests that source returns None when not in metadata."""
        doc = CoreDocument(id="doc-1", content="content")

        assert doc.source is None

    def test_source_returns_value_when_set(self):
        """Tests that source returns correct value when in metadata."""
        doc = CoreDocument(id="doc-1", content="content", metadata={"source": "document.pdf"})

        assert doc.source == "document.pdf"

    def test_title_returns_none_when_not_set(self):
        """Tests that title returns None when not in metadata."""
        doc = CoreDocument(id="doc-1", content="content")

        assert doc.title is None

    def test_title_returns_value_when_set(self):
        """Tests that title returns correct value when in metadata."""
        doc = CoreDocument(id="doc-1", content="content", metadata={"title": "My Document"})

        assert doc.title == "My Document"


class TestCoreDocumentWithScore:
    """Tests for CoreDocument.with_score method."""

    def test_with_score_creates_new_document(self):
        """Tests that with_score creates a new document instance."""
        original = CoreDocument(id="doc-1", content="content")
        updated = original.with_score(0.85)

        assert updated is not original
        assert original.score is None
        assert updated.score == 0.85

    def test_with_score_preserves_other_fields(self):
        """Tests that with_score preserves all other fields."""
        metadata = {"key": "value"}
        original = CoreDocument(id="doc-1", content="content", metadata=metadata)
        updated = original.with_score(0.75)

        assert updated.id == original.id
        assert updated.content == original.content
        assert updated.metadata == original.metadata

    def test_with_score_creates_metadata_copy(self):
        """Tests that with_score creates a copy of metadata (immutability)."""
        metadata = {"key": "value"}
        original = CoreDocument(id="doc-1", content="content", metadata=metadata)
        updated = original.with_score(0.75)

        # Modify original metadata
        original.metadata["key"] = "modified"

        # Updated document should not be affected
        assert updated.metadata["key"] == "value"

    def test_with_score_replaces_existing_score(self):
        """Tests that with_score replaces existing score."""
        original = CoreDocument(id="doc-1", content="content", score=0.5)
        updated = original.with_score(0.9)

        assert original.score == 0.5
        assert updated.score == 0.9


class TestCoreDocumentSerialization:
    """Tests for CoreDocument serialization methods."""

    def test_to_dict_with_minimal_document(self):
        """Tests that to_dict works with minimal document."""
        doc = CoreDocument(id="doc-1", content="content")
        result = doc.to_dict()

        assert result == {"id": "doc-1", "content": "content", "metadata": {}, "score": None}

    def test_to_dict_with_full_document(self):
        """Tests that to_dict works with fully populated document."""
        metadata = {"source": "test.pdf", "page": 5}
        doc = CoreDocument(id="doc-1", content="content", metadata=metadata, score=0.88)
        result = doc.to_dict()

        assert result == {"id": "doc-1", "content": "content", "metadata": metadata, "score": 0.88}

    def test_from_dict_with_minimal_data(self):
        """Tests that from_dict works with minimal data."""
        data = {"id": "doc-1", "content": "content"}
        doc = CoreDocument.from_dict(data)

        assert doc.id == "doc-1"
        assert doc.content == "content"
        assert doc.metadata == {}
        assert doc.score is None

    def test_from_dict_with_full_data(self):
        """Tests that from_dict works with full data."""
        data = {"id": "doc-1", "content": "content", "metadata": {"key": "value"}, "score": 0.77}
        doc = CoreDocument.from_dict(data)

        assert doc.id == "doc-1"
        assert doc.content == "content"
        assert doc.metadata == {"key": "value"}
        assert doc.score == 0.77

    def test_from_dict_missing_id_raises_key_error(self):
        """Tests that from_dict raises KeyError when id is missing."""
        data = {"content": "content"}

        with pytest.raises(KeyError):
            CoreDocument.from_dict(data)

    def test_from_dict_missing_content_raises_key_error(self):
        """Tests that from_dict raises KeyError when content is missing."""
        data = {"id": "doc-1"}

        with pytest.raises(KeyError):
            CoreDocument.from_dict(data)

    def test_roundtrip_serialization(self):
        """Tests that to_dict and from_dict are inverses."""
        original = CoreDocument(id="doc-roundtrip", content="test content", metadata={"namespace": "test", "tags": ["a", "b"]}, score=0.95)

        serialized = original.to_dict()
        restored = CoreDocument.from_dict(serialized)

        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.metadata == original.metadata
        assert restored.score == original.score


class TestCoreDocumentEquality:
    """Tests for CoreDocument equality and hashing."""

    def test_documents_with_same_data_are_equal(self):
        """Tests that two documents with same data are equal."""
        doc1 = CoreDocument(id="doc-1", content="content", metadata={"key": "value"}, score=0.5)
        doc2 = CoreDocument(id="doc-1", content="content", metadata={"key": "value"}, score=0.5)

        assert doc1 == doc2

    def test_documents_with_different_id_are_not_equal(self):
        """Tests that documents with different ids are not equal."""
        doc1 = CoreDocument(id="doc-1", content="content")
        doc2 = CoreDocument(id="doc-2", content="content")

        assert doc1 != doc2

    def test_documents_with_different_content_are_not_equal(self):
        """Tests that documents with different content are not equal."""
        doc1 = CoreDocument(id="doc-1", content="content-a")
        doc2 = CoreDocument(id="doc-1", content="content-b")

        assert doc1 != doc2

    def test_documents_with_different_metadata_are_not_equal(self):
        """Tests that documents with different metadata are not equal."""
        doc1 = CoreDocument(id="doc-1", content="content", metadata={"a": 1})
        doc2 = CoreDocument(id="doc-1", content="content", metadata={"b": 2})

        assert doc1 != doc2

    def test_documents_with_different_score_are_not_equal(self):
        """Tests that documents with different scores are not equal."""
        doc1 = CoreDocument(id="doc-1", content="content", score=0.5)
        doc2 = CoreDocument(id="doc-1", content="content", score=0.9)

        assert doc1 != doc2
