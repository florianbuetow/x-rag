"""OpenAI LLM client for answer generation.

Provides async wrapper around OpenAI API with retry logic,
error handling, and cost tracking.
"""

import logging

from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Async client for OpenAI LLM API.

    Handles answer generation using OpenAI's chat models with
    proper error handling and retry logic.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_retries: int,
        timeout: int,
        base_url: str | None,
    ) -> None:
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model to use (e.g., "gpt-4o-mini", "gpt-4")
            max_retries: Maximum number of retries on failure
            timeout: Request timeout in seconds
            base_url: Optional base URL for OpenAI-compatible APIs (e.g., LM Studio)
        """
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout,
            base_url=base_url,
        )
        base_info = f", base_url={base_url}" if base_url else ""
        logger.info(f"✓ OpenAI client initialized (model={model}{base_info})")

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_message: str | None,
    ) -> str:
        """Generate text using OpenAI chat model.

        Args:
            prompt: User prompt/question
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-2.0)
            system_message: Optional system message

        Returns:
            Generated text response

        Raises:
            OpenAIError: If API call fails after retries
        """
        try:
            # Build messages
            messages: list[ChatCompletionMessageParam] = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})

            # Call OpenAI API
            logger.debug(f"Calling OpenAI API (model={self.model}, max_tokens={max_tokens})")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Extract response text
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("OpenAI returned None for message content")
            answer = content

            # Log token usage
            if response.usage:
                logger.info(
                    f"OpenAI usage: prompt={response.usage.prompt_tokens}, "
                    f"completion={response.usage.completion_tokens}, "
                    f"total={response.usage.total_tokens}"
                )

            return answer

        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def generate_with_context(
        self,
        query: str,
        context: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Generate answer based on context (RAG pattern).

        Args:
            query: User question
            context: Retrieved context to answer from
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Generated answer
        """
        # Build RAG prompt
        prompt = f"""Context:
{context}

Question: {query}

Answer the question using only the information from the context above.
If the context doesn't contain enough information to answer the question,
say "I don't have enough information to answer this question."

Answer:"""

        return await self.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system_message=None,
        )

    async def health_check(self) -> bool:
        """Check if OpenAI/LLM API is accessible.

        Uses the models list endpoint instead of making a completion call
        to avoid consuming tokens on every health check.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Use models.list() endpoint - doesn't consume tokens
            # For OpenAI: lists available models
            # For local LLMs (LM Studio/Ollama): also supports this endpoint
            models = await self.client.models.list()
            return models is not None
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.close()
