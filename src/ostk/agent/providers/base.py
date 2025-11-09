"""Base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Base class for LLM providers using Strategy pattern."""

    @abstractmethod
    def __init__(self, api_key: str | None = None, model: str | None = None, **kwargs: Any):
        """
        Initialize the LLM provider.
        
        Args:
            api_key: API key for the provider (if required)
            model: Model name to use (required for all providers)
            **kwargs: Additional provider-specific configuration
        """
        if not model:
            raise ValueError(
                f"Model not specified for {self.__class__.__name__}. "
                f"Please set it in your config file or pass it explicitly."
            )
        self.model = model

    @abstractmethod
    def complete(
        self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 400
    ) -> str:
        """
        Send a completion request to the LLM provider.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            The completion text from the LLM
        """
        pass
