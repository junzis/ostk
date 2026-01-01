"""Utility functions for OSTK GUI."""

import configparser
import os
from pathlib import Path
from typing import Optional


def get_config_dir() -> Path:
    """Get platform-specific config directory for OSTK."""
    home = Path.home()
    if os.name == "posix":
        config_dir = home / ".config" / "ostk"
    elif os.name == "nt":
        config_dir = home / "AppData" / "Local" / "ostk"
    else:
        config_dir = home / ".ostk"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the config file path."""
    return get_config_dir() / "settings.conf"


def load_llm_config() -> dict[str, str]:
    """Load LLM configuration from settings.conf."""
    config_path = get_config_path()
    config_dict = {}

    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path)

        if config.has_section("llm"):
            for key, value in config.items("llm"):
                config_dict[key] = value.strip()

    return config_dict


def save_llm_config(
    provider: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> None:
    """Save LLM configuration to settings.conf."""
    config_path = get_config_path()

    config = configparser.ConfigParser()
    if config_path.exists():
        config.read(config_path)

    if not config.has_section("llm"):
        config.add_section("llm")

    config.set("llm", "provider", provider)

    if model:
        config.set("llm", f"{provider}_model", model)

    if api_key:
        config.set("llm", f"{provider}_api_key", api_key)

    if base_url and provider == "ollama":
        config.set("llm", "ollama_base_url", base_url)

    with open(config_path, "w") as f:
        config.write(f)


def get_provider_display_name(provider: str) -> str:
    """Get a display-friendly name for a provider."""
    names = {
        "groq": "Groq",
        "openai": "OpenAI",
        "ollama": "Ollama (Local)",
    }
    return names.get(provider, provider.title())


def get_pyopensky_config_path() -> Path:
    """Get the pyopensky configuration file path."""
    try:
        from pyopensky.config import opensky_config_dir

        return Path(opensky_config_dir) / "settings.conf"
    except ImportError:
        # Fallback if pyopensky is not installed
        home = Path.home()
        if os.name == "posix":
            return home / ".config" / "ostk" / "pyopensky.conf"
        elif os.name == "nt":
            return home / "AppData" / "Local" / "ostk" / "pyopensky.conf"
        return home / ".ostk" / "pyopensky.conf"


def load_pyopensky_config() -> dict[str, str]:
    """Load PyOpenSky configuration from settings.conf."""
    config_path = get_pyopensky_config_path()
    config_dict = {}

    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path)

        # Default section (credentials)
        if config.has_section("default"):
            for key, value in config.items("default"):
                config_dict[key] = value.strip()

        # Cache section
        if config.has_section("cache"):
            for key, value in config.items("cache"):
                config_dict[f"cache_{key}"] = value.strip()

    return config_dict


def save_pyopensky_config(
    username: Optional[str] = None,
    password: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    cache_purge: Optional[str] = None,
) -> None:
    """Save PyOpenSky configuration to settings.conf."""
    try:
        from pyopensky.config import DEFAULT_CONFIG
    except ImportError:
        DEFAULT_CONFIG = """[default]
username =
password =
client_id =
client_secret =

[cache]
purge = 90 days
"""

    config_path = get_pyopensky_config_path()

    # Create config directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Start with default config or read existing
    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path)
    else:
        config = configparser.ConfigParser()
        config.read_string(DEFAULT_CONFIG)

    # Ensure sections exist
    if not config.has_section("default"):
        config.add_section("default")
    if not config.has_section("cache"):
        config.add_section("cache")

    # Update values in [default] section
    if username is not None:
        config.set("default", "username", username)
    if password is not None:
        config.set("default", "password", password)
    if client_id is not None:
        config.set("default", "client_id", client_id)
    if client_secret is not None:
        config.set("default", "client_secret", client_secret)

    # Update cache settings
    if cache_purge is not None:
        config.set("cache", "purge", cache_purge)

    with open(config_path, "w") as f:
        config.write(f)
