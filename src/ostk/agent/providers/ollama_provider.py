"""Ollama provider implementation."""

from typing import Dict, List

from ollama import Client, ResponseError

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "http://localhost:11434",
        **kwargs,
    ):
        """
        Initialize Ollama provider.

        Args:
            api_key: Not used for Ollama (no API key required)
            model: Model name (required)
            base_url: Ollama server URL (default: http://localhost:11434)
            **kwargs: Additional configuration (unused)
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.client = Client(host=base_url)

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 400,
    ) -> str:
        """
        Send a completion request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate

        Returns:
            The completion text from the LLM
        """
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )

            # Handle both object and dict response types
            # Newer Ollama API returns ChatResponse object
            if hasattr(response, "message"):
                content = response.message.content or ""
                thinking = response.message.thinking or ""
            else:
                # Fallback for dict-based response
                message = response.get("message", {})
                content = message.get("content", "")
                thinking = message.get("thinking", "")

            # For reasoning models, the actual response may be in 'thinking' field
            # Return thinking if content is empty
            result = content if content else thinking

            if not result:
                raise RuntimeError(
                    "Ollama returned an empty response. "
                    "This may indicate the model is not responding correctly."
                )

            return result

        except ResponseError as e:
            raise RuntimeError(
                f"Failed to connect to Ollama. "
                f"Make sure Ollama is running and model '{self.model}' is available. "
                f"Error: {e.error}"
            )
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with Ollama: {e}")
