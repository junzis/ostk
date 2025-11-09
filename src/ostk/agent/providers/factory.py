"""Factory for creating LLM provider instances."""

from typing import Any

from .base import LLMProvider
from .groq_provider import GroqProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


class LLMProviderFactory:
    """Factory class to create LLM provider instances."""

    _providers = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "groq": GroqProvider,
    }

    @classmethod
    def create(cls, provider_name: str, **kwargs: Any) -> LLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider_name: Name of the provider (openai, ollama, groq)
            **kwargs: Provider-specific configuration (api_key, model, base_url, etc.)

        Returns:
            An instance of the requested LLM provider

        Raises:
            ValueError: If provider name is not supported
        """
        provider_name = provider_name.lower()
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        provider_class = cls._providers[provider_name]
        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return a list of available provider names."""
        return list(cls._providers.keys())
