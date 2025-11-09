"""OpenAI provider implementation."""

from typing import Any

from openai import OpenAI

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""

    def __init__(
        self, api_key: str | None = None, model: str | None = None, **kwargs: Any
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (required)
            model: Model name (required)
            **kwargs: Additional configuration (unused)
        """
        super().__init__(api_key=api_key, model=model, **kwargs)

        if not api_key:
            raise ValueError("OpenAI API key is required")

        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 400,
    ) -> str:
        """
        Send a completion request to OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate

        Returns:
            The completion text from the LLM
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
