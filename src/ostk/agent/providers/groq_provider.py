"""Groq provider implementation."""

from typing import Dict, List

from openai import OpenAI

from .base import LLMProvider


class GroqProvider(LLMProvider):
    """Groq LLM provider implementation using OpenAI-compatible API."""

    def __init__(self, api_key: str | None = None, model: str | None = None, **kwargs):
        """
        Initialize Groq provider.

        Args:
            api_key: Groq API key (required)
            model: Model name (required)
            **kwargs: Additional configuration (unused)
        """
        super().__init__(api_key=api_key, model=model, **kwargs)

        if not api_key:
            raise ValueError("Groq API key is required")

        self.api_key = api_key
        self.client = OpenAI(
            api_key=self.api_key, base_url="https://api.groq.com/openai/v1"
        )

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 400,
    ) -> str:
        """
        Send a completion request to Groq.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate

        Returns:
            The completion text from the LLM
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
