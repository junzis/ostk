"""
LLM-powered agent for querying OpenSky Trino via natural language.
Supports multiple LLM providers: OpenAI, Ollama, Groq.
"""

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from pyopensky.trino import Trino

from .providers.base import LLMProvider
from .providers.factory import LLMProviderFactory


class Agent:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **provider_kwargs: Any,
    ):
        """
        Initialize the Agent with a specific LLM provider.

        Args:
            provider: Name of LLM provider (openai, ollama, groq)
                     If None, reads from config file (defaults to openai)
            model: Model name to use. If None, reads from config file.
                   Model MUST be specified either here or in config.
            **provider_kwargs: Additional provider-specific arguments
        """
        self.trino = Trino()

        # Load provider configuration
        config = self._load_config()

        # Determine provider
        if provider is None:
            provider = config.get("provider", "openai")
        self.provider_name = provider

        # Determine model
        if model is None:
            model_key = f"{provider}_model"
            model = config.get(model_key)
            if not model:
                raise ValueError(
                    f"Model not specified for provider '{provider}'. "
                    f"Set it via config file or pass 'model' parameter."
                )

        # Get provider-specific configuration
        provider_config = self._get_provider_config(
            provider, config, model, provider_kwargs
        )

        # Create the LLM provider instance
        self.llm_provider: LLMProvider = LLMProviderFactory.create(
            provider, **provider_config
        )

    def _load_config(self) -> Dict[str, str]:
        """Load LLM configuration from config file."""
        config_path = self._get_config_path()
        config_dict = {}

        if config_path and os.path.exists(config_path):
            import configparser

            config = configparser.ConfigParser()
            config.read(config_path)

            if config.has_section("llm"):
                for key, value in config.items("llm"):
                    config_dict[key] = value.strip()

        return config_dict

    def _get_provider_config(
        self,
        provider: str,
        config: Dict[str, str],
        model: str,
        provider_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get provider-specific configuration from config file and kwargs.

        Args:
            provider: Provider name
            config: Config dictionary from config file
            model: Model name
            provider_kwargs: Additional kwargs passed to __init__

        Returns:
            Dict of configuration to pass to provider constructor
        """
        provider_config = {"model": model, **provider_kwargs}

        # Get API key if not already provided
        if "api_key" not in provider_kwargs:
            api_key_from_config = config.get(f"{provider}_api_key")
            if api_key_from_config:
                provider_config["api_key"] = api_key_from_config
            else:
                # Try environment variables
                env_var_map = {
                    "openai": "OPENAI_API_KEY",
                    "groq": "GROQ_API_KEY",
                }
                if provider in env_var_map:
                    env_key = os.getenv(env_var_map[provider])
                    if env_key:
                        provider_config["api_key"] = env_key

        # Get provider-specific settings
        if provider == "ollama":
            # Ollama may have base_url setting
            if "base_url" not in provider_kwargs:
                ollama_url = config.get("ollama_base_url", "http://localhost:11434")
                provider_config["base_url"] = ollama_url

        return provider_config

    def _get_config_path(self) -> Optional[str]:
        """Get platform-specific config file path."""
        home = os.path.expanduser("~")
        if os.name == "posix":
            # Linux/macOS
            config_dir = os.path.join(home, ".config", "ostk")
        elif os.name == "nt":
            # Windows
            config_dir = os.path.join(home, "AppData", "Local", "ostk")
        else:
            config_dir = os.path.join(home, ".ostk")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "settings.conf")

    def parse_query(self, user_query: str, return_raw_response: bool = False):
        """
        Use LLM to parse user natural language query into pyopensky history() parameters.

        Args:
            user_query: Natural language query from the user
            return_raw_response: If True, return tuple of (params, raw_response)

        Returns:
            Dict of parameters for history(), or tuple of (params, raw_response) if return_raw_response=True
        """
        # Read prompt from markdown file
        prompt_path = os.path.join(os.path.dirname(__file__), "agent.md")
        with open(prompt_path, "r") as f:
            prompt_template = f.read()
        prompt = prompt_template.replace("{user_query}", user_query)

        # Call the LLM provider
        response_text = self.llm_provider.complete(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1000,
        )

        # Try to extract the dictionary from the response
        # Use regex to extract dict
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            try:
                params = eval(match.group(0), {"__builtins__": None}, {})
                if return_raw_response:
                    return params, response_text
                return params
            except Exception:
                pass
        raise ValueError(
            f"Could not parse parameters from LLM response: {response_text}"
        )

    def build_history_call(self, params: Dict[str, Any]) -> str:
        """
        Build the pyopensky history() function call as a string for user confirmation.
        """
        args = []
        for k, v in params.items():
            if v is not None:
                args.append(f"{k}={repr(v)}")
        return f"trino.history({', '.join(args)})"

    def execute_query(self, params: Dict[str, Any]) -> pd.DataFrame:
        """
        Execute the history() query with the given parameters.
        """
        # Remove None values
        return self.trino.history(**params).sort_values(["icao24", "time"])

    def save_result(
        self, df: pd.DataFrame, fmt: str = "csv", output: Optional[str] = None
    ):
        """
        Save the DataFrame to CSV or Parquet.
        """
        if output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = f"state_vectors_{timestamp}.{fmt}"
        if fmt == "csv":
            df.to_csv(output, index=False)
        elif fmt == "parquet":
            df.to_parquet(output, index=False)
        else:
            raise ValueError("Format must be 'csv' or 'parquet'")
        return output
