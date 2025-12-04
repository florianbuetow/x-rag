"""Unit tests for src/llm/factory.py.

Tests cover:
- create_llm_client with OpenAI configuration
- create_llm_client with local configuration
"""

from unittest.mock import patch

from src.llm.config import LLMConfig
from src.llm.factory import create_llm_client


class TestCreateLLMClient:
    """Tests for create_llm_client function."""

    @patch("src.llm.factory.OpenAIClient")
    def test_create_llm_client_openai(self, mock_openai_client):
        """Tests create_llm_client creates OpenAIClient for OpenAI config."""
        mock_instance = mock_openai_client.return_value
        config = LLMConfig.for_openai(
            api_key="sk-test123",
            model="gpt-4",
            max_retries=5,
            timeout=120,
        )

        result = create_llm_client(config)

        mock_openai_client.assert_called_once_with(
            api_key="sk-test123",
            model="gpt-4",
            max_retries=5,
            timeout=120,
            base_url=None,
        )
        assert result == mock_instance

    @patch("src.llm.factory.OpenAIClient")
    def test_create_llm_client_local(self, mock_openai_client):
        """Tests create_llm_client creates OpenAIClient for local config."""
        mock_instance = mock_openai_client.return_value
        config = LLMConfig.for_local(
            base_url="http://localhost:1234/v1",
            model="qwen2.5-7b",
        )

        result = create_llm_client(config)

        mock_openai_client.assert_called_once_with(
            api_key="local",
            model="qwen2.5-7b",
            max_retries=3,
            timeout=60,
            base_url="http://localhost:1234/v1",
        )
        assert result == mock_instance

    @patch("src.llm.factory.OpenAIClient")
    def test_create_llm_client_with_custom_api_key(self, mock_openai_client):
        """Tests create_llm_client passes custom API key to client."""
        config = LLMConfig.for_local(
            base_url="http://localhost:1234/v1",
            model="model",
            api_key="custom-key",
        )

        create_llm_client(config)

        call_kwargs = mock_openai_client.call_args[1]
        assert call_kwargs["api_key"] == "custom-key"
