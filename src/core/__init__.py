"""Core domain models and interfaces."""

from src.core.document import CoreDocument
from src.core.interfaces import (
    AnswerGenerator,
    Cache,
    Chunker,
    DocumentLoader,
    EmbeddingClient,
    GraphRetriever,
    IndexClient,
    Reranker,
    Retriever,
    SearchMode,
    TextCleaner,
    TextSplitter,
)
from src.core.types import Chunk, IndexedChunk, RetrievalResult, RetrievedChunk

__all__ = [
    # Document
    "CoreDocument",
    # Types
    "Chunk",
    "IndexedChunk",
    "RetrievedChunk",
    "RetrievalResult",
    # Interfaces
    "AnswerGenerator",
    "Cache",
    "Chunker",
    "DocumentLoader",
    "EmbeddingClient",
    "GraphRetriever",
    "IndexClient",
    "Reranker",
    "Retriever",
    "SearchMode",
    "TextCleaner",
    "TextSplitter",
]
