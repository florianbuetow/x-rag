"""Unit tests for src/llm/openai_client.py.

Tests cover:
- OpenAIClient initialization
- generate method (success, error handling, token usage)
- generate_with_context method (RAG pattern)
- health_check method
- close method
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import OpenAIError

from src.llm.openai_client import OpenAIClient


class TestOpenAIClientInit:
    """Tests for OpenAIClient initialization."""

    @patch("src.llm.openai_client.AsyncOpenAI")
    def test_init_creates_client(self, mock_async_openai):
        """Tests that __init__ creates client with all parameters."""
        client = OpenAIClient(
            api_key="test-key",
            model="gpt-4o-mini",
            max_retries=3,
            timeout=60,
            base_url=None,
        )

        mock_async_openai.assert_called_once_with(
            api_key="test-key",
            max_retries=3,
            timeout=60,
            base_url=None,
        )
        assert client.model == "gpt-4o-mini"

    @patch("src.llm.openai_client.AsyncOpenAI")
    def test_init_creates_client_with_custom_model(self, mock_async_openai):
        """Tests that __init__ respects custom model parameter."""
        client = OpenAIClient(
            api_key="test-key",
            model="gpt-4",
            max_retries=3,
            timeout=60,
            base_url=None,
        )

        assert client.model == "gpt-4"

    @patch("src.llm.openai_client.AsyncOpenAI")
    def test_init_creates_client_with_custom_retries(self, mock_async_openai):
        """Tests that __init__ respects custom max_retries parameter."""
        OpenAIClient(
            api_key="test-key",
            model="gpt-4o-mini",
            max_retries=5,
            timeout=60,
            base_url=None,
        )

        mock_async_openai.assert_called_once_with(
            api_key="test-key",
            max_retries=5,
            timeout=60,
            base_url=None,
        )

    @patch("src.llm.openai_client.AsyncOpenAI")
    def test_init_creates_client_with_custom_timeout(self, mock_async_openai):
        """Tests that __init__ respects custom timeout parameter."""
        OpenAIClient(
            api_key="test-key",
            model="gpt-4o-mini",
            max_retries=3,
            timeout=120,
            base_url=None,
        )

        mock_async_openai.assert_called_once_with(
            api_key="test-key",
            max_retries=3,
            timeout=120,
            base_url=None,
        )


class TestOpenAIClientGenerate:
    """Tests for OpenAIClient.generate method."""

    @pytest.fixture
    def mock_client(self):
        """Create OpenAIClient with mocked AsyncOpenAI."""
        with patch("src.llm.openai_client.AsyncOpenAI") as mock_async_openai:
            mock_openai_instance = MagicMock()
            mock_async_openai.return_value = mock_openai_instance
            client = OpenAIClient(
                api_key="test-key",
                model="gpt-4o-mini",
                max_retries=3,
                timeout=60,
                base_url=None,
            )
            client.client = mock_openai_instance
            yield client

    @pytest.mark.asyncio
    async def test_generate_returns_answer(self, mock_client):
        """Tests that generate returns the generated answer."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Generated answer"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await mock_client.generate("What is Python?", max_tokens=500, temperature=0.7, system_message=None)

        assert result == "Generated answer"

    @pytest.mark.asyncio
    async def test_generate_sends_correct_messages(self, mock_client):
        """Tests that generate sends correct messages to API."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await mock_client.generate("Test prompt", max_tokens=500, temperature=0.7, system_message=None)

        mock_client.client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.client.chat.completions.create.call_args[1]

        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["messages"] == [{"role": "user", "content": "Test prompt"}]

    @pytest.mark.asyncio
    async def test_generate_with_system_message(self, mock_client):
        """Tests that generate includes system message when provided."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await mock_client.generate("User question", max_tokens=500, temperature=0.7, system_message="You are helpful.")

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]

        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are helpful."}
        assert messages[1] == {"role": "user", "content": "User question"}

    @pytest.mark.asyncio
    async def test_generate_respects_max_tokens(self, mock_client):
        """Tests that generate respects max_tokens parameter."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await mock_client.generate("Prompt", max_tokens=100, temperature=0.7, system_message=None)

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_generate_respects_temperature(self, mock_client):
        """Tests that generate respects temperature parameter."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await mock_client.generate("Prompt", max_tokens=500, temperature=0.0, system_message=None)

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_generate_handles_empty_content(self, mock_client):
        """Tests that generate handles None content gracefully."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await mock_client.generate("Prompt", max_tokens=500, temperature=0.7, system_message=None)

        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_raises_on_api_error(self, mock_client):
        """Tests that generate raises OpenAIError on API failure."""
        mock_client.client.chat.completions.create = AsyncMock(side_effect=OpenAIError("API Error"))

        with pytest.raises(OpenAIError):
            await mock_client.generate("Prompt", max_tokens=500, temperature=0.7, system_message=None)


class TestOpenAIClientGenerateWithContext:
    """Tests for OpenAIClient.generate_with_context method."""

    @pytest.fixture
    def mock_client(self):
        """Create OpenAIClient with mocked AsyncOpenAI."""
        with patch("src.llm.openai_client.AsyncOpenAI") as mock_async_openai:
            mock_openai_instance = MagicMock()
            mock_async_openai.return_value = mock_openai_instance
            client = OpenAIClient(
                api_key="test-key",
                model="gpt-4o-mini",
                max_retries=3,
                timeout=60,
                base_url=None,
            )
            client.client = mock_openai_instance
            yield client

    @pytest.mark.asyncio
    async def test_generate_with_context_builds_rag_prompt(self, mock_client):
        """Tests that generate_with_context builds correct RAG prompt."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer based on context"))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await mock_client.generate_with_context(
            query="What is Python?",
            context="Python is a programming language.",
            max_tokens=500,
            temperature=0.7,
        )

        assert result == "Answer based on context"

        # Verify the prompt structure
        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        prompt = call_kwargs["messages"][0]["content"]

        assert "Python is a programming language." in prompt
        assert "What is Python?" in prompt
        assert "Context:" in prompt
        assert "Question:" in prompt

    @pytest.mark.asyncio
    async def test_generate_with_context_respects_max_tokens(self, mock_client):
        """Tests that generate_with_context respects max_tokens."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await mock_client.generate_with_context(query="Question", context="Context", max_tokens=200, temperature=0.7)

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 200

    @pytest.mark.asyncio
    async def test_generate_with_context_respects_temperature(self, mock_client):
        """Tests that generate_with_context respects temperature."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Answer"))]
        mock_response.usage = None

        mock_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await mock_client.generate_with_context(query="Question", context="Context", max_tokens=500, temperature=0.5)

        call_kwargs = mock_client.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.5


class TestOpenAIClientHealthCheck:
    """Tests for OpenAIClient.health_check method."""

    @pytest.fixture
    def mock_client(self):
        """Create OpenAIClient with mocked AsyncOpenAI."""
        with patch("src.llm.openai_client.AsyncOpenAI") as mock_async_openai:
            mock_openai_instance = MagicMock()
            mock_async_openai.return_value = mock_openai_instance
            client = OpenAIClient(
                api_key="test-key",
                model="gpt-4o-mini",
                max_retries=3,
                timeout=60,
                base_url=None,
            )
            client.client = mock_openai_instance
            yield client

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self, mock_client):
        """Tests that health_check returns True when models.list succeeds."""
        mock_models = MagicMock()
        mock_client.client.models.list = AsyncMock(return_value=mock_models)

        result = await mock_client.health_check()

        assert result is True
        mock_client.client.models.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_uses_models_list_not_completions(self, mock_client):
        """Tests that health_check uses models.list endpoint (no token consumption)."""
        mock_models = MagicMock()
        mock_client.client.models.list = AsyncMock(return_value=mock_models)
        mock_client.client.chat.completions.create = AsyncMock()

        await mock_client.health_check()

        # Should use models.list, not chat.completions.create
        mock_client.client.models.list.assert_called_once()
        mock_client.client.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self, mock_client):
        """Tests that health_check returns False on error."""
        mock_client.client.models.list = AsyncMock(side_effect=Exception("API Error"))

        result = await mock_client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_none_response(self, mock_client):
        """Tests that health_check returns False when response is None."""
        mock_client.client.models.list = AsyncMock(return_value=None)

        result = await mock_client.health_check()

        assert result is False


class TestOpenAIClientClose:
    """Tests for OpenAIClient.close method."""

    @pytest.fixture
    def mock_client(self):
        """Create OpenAIClient with mocked AsyncOpenAI."""
        with patch("src.llm.openai_client.AsyncOpenAI") as mock_async_openai:
            mock_openai_instance = MagicMock()
            mock_openai_instance.close = AsyncMock()
            mock_async_openai.return_value = mock_openai_instance
            client = OpenAIClient(
                api_key="test-key",
                model="gpt-4o-mini",
                max_retries=3,
                timeout=60,
                base_url=None,
            )
            client.client = mock_openai_instance
            yield client

    @pytest.mark.asyncio
    async def test_close_closes_client(self, mock_client):
        """Tests that close calls client.close()."""
        await mock_client.close()

        mock_client.client.close.assert_called_once()
