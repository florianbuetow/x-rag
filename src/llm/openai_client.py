"""OpenAI LLM client for answer generation.

Provides async wrapper around OpenAI API with retry logic,
error handling, and cost tracking.
"""

import logging
from typing import Dict, Optional

from openai import AsyncOpenAI, OpenAIError

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Async client for OpenAI LLM API.

    Handles answer generation using OpenAI's chat models with
    proper error handling and retry logic.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        timeout: int = 60,
    ) -> None:
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model to use (e.g., "gpt-4o-mini", "gpt-4")
            max_retries: Maximum number of retries on failure
            timeout: Request timeout in seconds
        """
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout,
        )
        logger.info(f"✓ OpenAI client initialized (model={model})")

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        system_message: Optional[str] = None,
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
            messages: list[Dict[str, str]] = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})

            # Call OpenAI API
            logger.debug(f"Calling OpenAI API (model={self.model}, max_tokens={max_tokens})")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Extract response text
            answer = response.choices[0].message.content or ""

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
        max_tokens: int = 500,
        temperature: float = 0.7,
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
        )

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a minimal API call to test connectivity
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return response is not None
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.close()
