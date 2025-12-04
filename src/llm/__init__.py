"""LLM integration module for X-RAG platform.

Provides LLM client abstraction supporting both OpenAI API and
OpenAI-compatible local servers (LM Studio, Ollama, vLLM, etc.).
"""

from src.llm.config import EmbeddingConfig, EmbeddingProvider, LLMConfig, LLMProvider
from src.llm.factory import create_llm_client
from src.llm.openai_client import OpenAIClient

__all__ = [
    "LLMConfig",
    "LLMProvider",
    "EmbeddingConfig",
    "EmbeddingProvider",
    "OpenAIClient",
    "create_llm_client",
]
