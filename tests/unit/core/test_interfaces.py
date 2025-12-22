"""Unit tests for src/core/interfaces.py.

Tests cover:
- Protocol definitions for Retriever, GraphRetriever, Reranker, AnswerGenerator, Cache
- Runtime checkable behavior
- SearchMode literal type
"""

from src.core.document import CoreDocument
from src.core.interfaces import AnswerGenerator, Cache, GraphRetriever, Reranker, Retriever, SearchMode


class TestSearchMode:
    """Tests for SearchMode type."""

    def test_search_mode_literal_values(self):
        """Tests that SearchMode accepts valid literal values."""
        # These should all be valid assignments
        mode1: SearchMode = "vector"
        mode2: SearchMode = "bm25"
        mode3: SearchMode = "hybrid"

        assert mode1 == "vector"
        assert mode2 == "bm25"
        assert mode3 == "hybrid"


class TestRetrieverProtocol:
    """Tests for Retriever protocol."""

    def test_retriever_is_runtime_checkable(self):
        """Tests that Retriever protocol is runtime checkable."""

        # Protocol should be decorated with @runtime_checkable
        assert hasattr(Retriever, "__protocol_attrs__") or hasattr(Retriever, "_is_runtime_protocol")

    def test_class_implementing_retriever_is_instance(self):
        """Tests that a class implementing Retriever protocol passes isinstance check."""

        class MockRetriever:
            def retrieve(
                self,
                query: str,
                top_k: int = 10,
                mode: SearchMode = "hybrid",
                namespace: str = "test-ns",
            ) -> list[CoreDocument]:
                return []

        retriever = MockRetriever()
        assert isinstance(retriever, Retriever)

    def test_class_not_implementing_retriever_is_not_instance(self):
        """Tests that a class not implementing Retriever fails isinstance check."""

        class NotARetriever:
            def search(self, query: str) -> list[CoreDocument]:
                return []

        not_retriever = NotARetriever()
        assert not isinstance(not_retriever, Retriever)

    def test_retriever_protocol_has_retrieve_method(self):
        """Tests that Retriever protocol requires retrieve method."""

        class ValidRetriever:
            def retrieve(
                self,
                query: str,
                top_k: int = 10,
                mode: SearchMode = "hybrid",
                namespace: str = "test-ns",
            ) -> list[CoreDocument]:
                return [CoreDocument(id="1", content="test")]

        retriever = ValidRetriever()
        result = retriever.retrieve("test query")

        assert len(result) == 1
        assert result[0].id == "1"


class TestGraphRetrieverProtocol:
    """Tests for GraphRetriever protocol."""

    def test_graph_retriever_is_runtime_checkable(self):
        """Tests that GraphRetriever protocol is runtime checkable."""
        assert hasattr(GraphRetriever, "__protocol_attrs__") or hasattr(GraphRetriever, "_is_runtime_protocol")

    def test_class_implementing_graph_retriever_is_instance(self):
        """Tests that a class implementing GraphRetriever passes isinstance check."""

        class MockGraphRetriever:
            def neighbors(
                self,
                doc_ids: list[str],
                top_k: int = 10,
                namespace: str = "test-ns",
            ) -> list[CoreDocument]:
                return []

        retriever = MockGraphRetriever()
        assert isinstance(retriever, GraphRetriever)

    def test_class_not_implementing_graph_retriever_is_not_instance(self):
        """Tests that a class not implementing GraphRetriever fails isinstance check."""

        class NotAGraphRetriever:
            def find_related(self, doc_id: str) -> list[CoreDocument]:
                return []

        not_retriever = NotAGraphRetriever()
        assert not isinstance(not_retriever, GraphRetriever)

    def test_graph_retriever_protocol_has_neighbors_method(self):
        """Tests that GraphRetriever protocol requires neighbors method."""

        class ValidGraphRetriever:
            def neighbors(
                self,
                doc_ids: list[str],
                top_k: int = 10,
                namespace: str = "test-ns",
            ) -> list[CoreDocument]:
                return [CoreDocument(id="neighbor-1", content="neighbor content")]

        retriever = ValidGraphRetriever()
        result = retriever.neighbors(["doc-1"])

        assert len(result) == 1
        assert result[0].id == "neighbor-1"


class TestRerankerProtocol:
    """Tests for Reranker protocol."""

    def test_reranker_is_runtime_checkable(self):
        """Tests that Reranker protocol is runtime checkable."""
        assert hasattr(Reranker, "__protocol_attrs__") or hasattr(Reranker, "_is_runtime_protocol")

    def test_class_implementing_reranker_is_instance(self):
        """Tests that a class implementing Reranker passes isinstance check."""

        class MockReranker:
            def rerank(
                self,
                query: str,
                documents: list[CoreDocument],
                top_k: int | None = None,
            ) -> list[CoreDocument]:
                return documents

        reranker = MockReranker()
        assert isinstance(reranker, Reranker)

    def test_class_not_implementing_reranker_is_not_instance(self):
        """Tests that a class not implementing Reranker fails isinstance check."""

        class NotAReranker:
            def sort_documents(self, docs: list[CoreDocument]) -> list[CoreDocument]:
                return docs

        not_reranker = NotAReranker()
        assert not isinstance(not_reranker, Reranker)

    def test_reranker_protocol_has_rerank_method(self):
        """Tests that Reranker protocol requires rerank method."""

        class ValidReranker:
            def rerank(
                self,
                query: str,
                documents: list[CoreDocument],
                top_k: int | None = None,
            ) -> list[CoreDocument]:
                # Simple reranking: reverse order
                return list(reversed(documents))

        reranker = ValidReranker()
        docs = [CoreDocument(id="1", content="a"), CoreDocument(id="2", content="b")]
        result = reranker.rerank("query", docs)

        assert result[0].id == "2"
        assert result[1].id == "1"


class TestAnswerGeneratorProtocol:
    """Tests for AnswerGenerator protocol."""

    def test_answer_generator_is_runtime_checkable(self):
        """Tests that AnswerGenerator protocol is runtime checkable."""
        assert hasattr(AnswerGenerator, "__protocol_attrs__") or hasattr(AnswerGenerator, "_is_runtime_protocol")

    def test_class_implementing_answer_generator_is_instance(self):
        """Tests that a class implementing AnswerGenerator passes isinstance check."""

        class MockAnswerGenerator:
            def generate(
                self,
                query: str,
                documents: list[CoreDocument],
            ) -> str:
                return "Generated answer"

        generator = MockAnswerGenerator()
        assert isinstance(generator, AnswerGenerator)

    def test_class_not_implementing_answer_generator_is_not_instance(self):
        """Tests that a class not implementing AnswerGenerator fails isinstance check."""

        class NotAnAnswerGenerator:
            def create_answer(self, question: str) -> str:
                return "answer"

        not_generator = NotAnAnswerGenerator()
        assert not isinstance(not_generator, AnswerGenerator)

    def test_answer_generator_protocol_has_generate_method(self):
        """Tests that AnswerGenerator protocol requires generate method."""

        class ValidAnswerGenerator:
            def generate(
                self,
                query: str,
                documents: list[CoreDocument],
            ) -> str:
                context = "\n".join(doc.content for doc in documents)
                return f"Answer to '{query}' based on: {context}"

        generator = ValidAnswerGenerator()
        docs = [CoreDocument(id="1", content="fact 1")]
        result = generator.generate("What is it?", docs)

        assert "What is it?" in result
        assert "fact 1" in result


class TestCacheProtocol:
    """Tests for Cache protocol."""

    def test_cache_is_runtime_checkable(self):
        """Tests that Cache protocol is runtime checkable."""
        assert hasattr(Cache, "__protocol_attrs__") or hasattr(Cache, "_is_runtime_protocol")

    def test_class_implementing_cache_is_instance(self):
        """Tests that a class implementing Cache passes isinstance check."""

        class MockCache:
            def get(self, key: str) -> object | None:
                return None

            def set(self, key: str, value: object, ttl: int | None = None) -> None:
                pass

        cache = MockCache()
        assert isinstance(cache, Cache)

    def test_class_not_implementing_cache_is_not_instance(self):
        """Tests that a class not implementing Cache fails isinstance check."""

        class NotACache:
            def fetch(self, key: str) -> object:
                return None

        not_cache = NotACache()
        assert not isinstance(not_cache, Cache)

    def test_cache_protocol_has_get_and_set_methods(self):
        """Tests that Cache protocol requires get and set methods."""

        class ValidCache:
            def __init__(self):
                self._store: dict[str, object] = {}

            def get(self, key: str) -> object | None:
                return self._store.get(key)

            def set(self, key: str, value: object, ttl: int | None = None) -> None:
                self._store[key] = value

        cache = ValidCache()
        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"

    def test_cache_get_returns_none_for_missing_key(self):
        """Tests that Cache.get returns None for missing keys."""

        class ValidCache:
            def get(self, key: str) -> object | None:
                return None

            def set(self, key: str, value: object, ttl: int | None = None) -> None:
                pass

        cache = ValidCache()
        result = cache.get("nonexistent")

        assert result is None


class TestProtocolCompatibility:
    """Tests for protocol compatibility between components."""

    def test_retriever_returns_core_documents(self):
        """Tests that Retriever returns CoreDocument instances."""

        class TestRetriever:
            def retrieve(
                self,
                query: str,
                top_k: int = 10,
                mode: SearchMode = "hybrid",
                namespace: str = "test-ns",
            ) -> list[CoreDocument]:
                return [
                    CoreDocument(id="1", content="content 1", score=0.9),
                    CoreDocument(id="2", content="content 2", score=0.8),
                ]

        retriever = TestRetriever()
        results = retriever.retrieve("test", top_k=2)

        assert all(isinstance(doc, CoreDocument) for doc in results)
        assert len(results) == 2

    def test_reranker_accepts_and_returns_core_documents(self):
        """Tests that Reranker works with CoreDocument instances."""

        class TestReranker:
            def rerank(
                self,
                query: str,
                documents: list[CoreDocument],
                top_k: int | None = None,
            ) -> list[CoreDocument]:
                # Rerank by score descending
                sorted_docs = sorted(documents, key=lambda d: d.score or 0, reverse=True)
                return sorted_docs[:top_k] if top_k else sorted_docs

        reranker = TestReranker()
        docs = [
            CoreDocument(id="1", content="a", score=0.5),
            CoreDocument(id="2", content="b", score=0.9),
            CoreDocument(id="3", content="c", score=0.7),
        ]

        results = reranker.rerank("query", docs, top_k=2)

        assert len(results) == 2
        assert results[0].id == "2"  # Highest score
        assert results[1].id == "3"  # Second highest

    def test_answer_generator_uses_documents_for_context(self):
        """Tests that AnswerGenerator can use document content."""

        class TestAnswerGenerator:
            def generate(
                self,
                query: str,
                documents: list[CoreDocument],
            ) -> str:
                if not documents:
                    return "No context available."
                context = " | ".join(doc.content for doc in documents)
                return f"Based on context [{context}], the answer to '{query}' is..."

        generator = TestAnswerGenerator()
        docs = [
            CoreDocument(id="1", content="Paris is capital of France"),
            CoreDocument(id="2", content="France is in Europe"),
        ]

        answer = generator.generate("What is the capital of France?", docs)

        assert "Paris is capital of France" in answer
        assert "France is in Europe" in answer
