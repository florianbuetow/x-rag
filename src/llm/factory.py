"""Factory for creating LLM clients from configuration."""

import logging

from src.llm.config import LLMConfig
from src.llm.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


def create_llm_client(config: LLMConfig) -> OpenAIClient:
    """Create an LLM client from configuration.

    Currently uses OpenAIClient for all providers since OpenAI-compatible
    APIs (LM Studio, Ollama, vLLM) use the same protocol.

    Args:
        config: LLM configuration

    Returns:
        Configured LLM client
    """
    logger.info(f"Creating LLM client (provider={config.provider.value}, model={config.model}, base_url={config.base_url})")

    return OpenAIClient(
        api_key=config.api_key,
        model=config.model,
        max_retries=config.max_retries,
        timeout=config.timeout,
        base_url=config.base_url,
    )
