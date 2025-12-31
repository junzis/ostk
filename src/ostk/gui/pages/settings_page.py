"""Settings page for OSTK GUI - LLM provider and PyOpenSky configuration."""

import asyncio

import flet as ft

from ..state import AppState
from ..utils import (
    load_llm_config,
    load_pyopensky_config,
    save_llm_config,
    save_pyopensky_config,
)


async def _navigate(page: ft.Page, route: str) -> None:
    """Navigate to a route."""
    await page.push_route(route)


def create_settings_page(page: ft.Page, state: AppState) -> ft.View:
    """Create the settings page."""

    def show_snack(message: str):
        """Show a snackbar message."""
        page.snack_bar = ft.SnackBar(ft.Text(message))
        page.snack_bar.open = True
        page.update()

    config = load_llm_config()
    current_provider = config.get("provider", "groq")

    # Load PyOpenSky config
    pyopensky_config = load_pyopensky_config()

    # Provider selection
    provider_group = ft.RadioGroup(
        value=current_provider,
        content=ft.Column(
            controls=[
                ft.Radio(value="groq", label="Groq (Recommended - Fast & Free tier)"),
                ft.Radio(value="openai", label="OpenAI"),
                ft.Radio(value="ollama", label="Ollama (Local - No API key needed)"),
            ],
        ),
    )

    # Provider-specific config containers
    groq_config = ft.Column(visible=(current_provider == "groq"))
    openai_config = ft.Column(visible=(current_provider == "openai"))
    ollama_config = ft.Column(visible=(current_provider == "ollama"))

    # Groq fields
    groq_api_key = ft.TextField(
        label="API Key",
        value=config.get("groq_api_key", ""),
        password=True,
        can_reveal_password=True,
        hint_text="Get from console.groq.com",
        dense=True,
        text_size=13,
    )
    groq_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "qwen/qwen3-32b",
    ]
    groq_model = ft.Dropdown(
        label="Model",
        value=config.get("groq_model", "llama-3.3-70b-versatile"),
        options=[ft.dropdown.Option(m) for m in groq_models],
    )

    async def fetch_groq_models(e):
        """Fetch available models from Groq API."""
        api_key = groq_api_key.value
        if not api_key:
            show_snack("Enter API key first")
            return

        show_snack("Fetching models...")

        try:
            from ostk.cli import fetch_groq_models as fetch_models

            models = await asyncio.to_thread(fetch_models, api_key, tool_use_only=True)

            if models:
                model_ids = [m["id"] for m in models]
                groq_model.options = [ft.dropdown.Option(m) for m in model_ids]
                page.update()
                show_snack(f"Found {len(models)} models")
            else:
                show_snack("No models found or invalid API key")

        except Exception as ex:
            show_snack(f"Error: {ex}")

    groq_config.controls = [
        ft.Text("Groq Configuration", size=16, weight=ft.FontWeight.BOLD),
        ft.Text("Get your free API key from console.groq.com", size=12, color=ft.Colors.GREY_400),
        groq_api_key,
        ft.Row(
            controls=[
                groq_model,
                ft.FilledButton(
                    "Fetch Models",
                    icon=ft.Icons.REFRESH,
                    on_click=lambda e: page.run_task(fetch_groq_models, e),
                ),
            ],
        ),
    ]

    # OpenAI fields
    openai_api_key = ft.TextField(
        label="API Key",
        value=config.get("openai_api_key", ""),
        password=True,
        can_reveal_password=True,
        hint_text="Get from platform.openai.com",
        dense=True,
        text_size=13,
    )
    openai_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
    openai_model = ft.Dropdown(
        label="Model",
        value=config.get("openai_model", "gpt-4o-mini"),
        options=[ft.dropdown.Option(m) for m in openai_models],
    )

    openai_config.controls = [
        ft.Text("OpenAI Configuration", size=16, weight=ft.FontWeight.BOLD),
        ft.Text("Get your API key from platform.openai.com", size=12, color=ft.Colors.GREY_400),
        openai_api_key,
        openai_model,
    ]

    # Ollama fields
    ollama_url = ft.TextField(
        label="Base URL",
        value=config.get("ollama_base_url", "http://localhost:11434"),
        dense=True,
        text_size=13,
    )
    ollama_models = ["qwen2.5-coder:7b", "gemma3:12b", "llama3.1:8b", "mistral:7b"]
    ollama_model = ft.Dropdown(
        label="Model",
        value=config.get("ollama_model", "qwen2.5-coder:7b"),
        options=[ft.dropdown.Option(m) for m in ollama_models],
    )

    ollama_config.controls = [
        ft.Text("Ollama Configuration", size=16, weight=ft.FontWeight.BOLD),
        ft.Text("Run LLMs locally with ollama.ai - No API key required!", size=12, color=ft.Colors.GREY_400),
        ollama_url,
        ollama_model,
    ]

    # PyOpenSky configuration fields
    opensky_username = ft.TextField(
        label="Username",
        value=pyopensky_config.get("username", ""),
        hint_text="OpenSky username (for Trino)",
        dense=True,
        text_size=13,
        expand=True,
    )
    opensky_password = ft.TextField(
        label="Password",
        value=pyopensky_config.get("password", ""),
        password=True,
        can_reveal_password=True,
        hint_text="OpenSky password (for Trino)",
        dense=True,
        text_size=13,
        expand=True,
    )
    opensky_client_id = ft.TextField(
        label="Client ID",
        value=pyopensky_config.get("client_id", ""),
        hint_text="For Live API (optional)",
        dense=True,
        text_size=13,
        expand=True,
    )
    opensky_client_secret = ft.TextField(
        label="Client Secret",
        value=pyopensky_config.get("client_secret", ""),
        password=True,
        can_reveal_password=True,
        hint_text="For Live API (optional)",
        dense=True,
        text_size=13,
        expand=True,
    )
    cache_purge = ft.TextField(
        label="Cache Purge",
        value=pyopensky_config.get("cache_purge", "90 days"),
        hint_text="e.g., 90 days",
        dense=True,
        text_size=13,
        width=150,
    )

    def on_provider_change(e):
        """Show/hide provider-specific config."""
        provider = e.control.value
        groq_config.visible = (provider == "groq")
        openai_config.visible = (provider == "openai")
        ollama_config.visible = (provider == "ollama")
        page.update()

    provider_group.on_change = on_provider_change

    def save_config(e):
        """Save configuration and reinitialize agent."""
        provider = provider_group.value

        # Get values based on provider
        if provider == "groq":
            api_key = groq_api_key.value
            model = groq_model.value
            base_url = None
        elif provider == "openai":
            api_key = openai_api_key.value
            model = openai_model.value
            base_url = None
        else:  # ollama
            api_key = None
            model = ollama_model.value
            base_url = ollama_url.value

        # Validate
        if provider in ["groq", "openai"] and not api_key:
            show_snack("API key is required")
            return

        try:
            # Save LLM config
            save_llm_config(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
            )

            # Save PyOpenSky config
            save_pyopensky_config(
                username=opensky_username.value or "",
                password=opensky_password.value or "",
                client_id=opensky_client_id.value or "",
                client_secret=opensky_client_secret.value or "",
                cache_purge=cache_purge.value or "90 days",
            )

            show_snack("Configuration saved!")

            # Reinitialize agent
            try:
                from ostk.agent import Agent

                state.agent = Agent()
                state.provider_name = state.agent.provider_name
                state.model_name = state.agent.llm_provider.model
                state.error_message = None

                show_snack("Agent initialized successfully!")

            except Exception as ex:
                state.agent = None
                state.error_message = str(ex)
                show_snack(f"Agent init failed: {ex}")

            # Navigate back
            page.run_task(page.push_route, "/")

        except Exception as ex:
            show_snack(f"Error saving: {ex}")

    return ft.View(
        route="/settings",
        scroll=ft.ScrollMode.AUTO,
        appbar=ft.AppBar(
            leading=ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(_navigate, page, "/"),
            ),
            title=ft.Text("Settings"),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        ),
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        # PyOpenSky Configuration (first)
                        ft.Text("PyOpenSky Configuration", size=18, weight=ft.FontWeight.BOLD),
                        ft.Card(
                            content=ft.Container(
                                padding=16,
                                content=ft.Column(
                                    spacing=8,
                                    controls=[
                                        ft.Text("OpenSky Credentials", size=14, weight=ft.FontWeight.BOLD),
                                        ft.Text(
                                            "Register at opensky-network.org to get credentials for Trino database access.",
                                            size=12,
                                            color=ft.Colors.GREY_600,
                                        ),
                                        ft.Row([opensky_username, opensky_password], spacing=8),
                                        ft.Divider(height=1),
                                        ft.Text("Live API (Optional)", size=14, weight=ft.FontWeight.BOLD),
                                        ft.Text(
                                            "For real-time flight data. Only needed if using Live API features.",
                                            size=12,
                                            color=ft.Colors.GREY_600,
                                        ),
                                        ft.Row([opensky_client_id, opensky_client_secret], spacing=8),
                                        ft.Divider(height=1),
                                        ft.Text("Cache Settings", size=14, weight=ft.FontWeight.BOLD),
                                        cache_purge,
                                    ],
                                ),
                            ),
                        ),
                        # LLM Provider Configuration (second)
                        ft.Container(height=8),
                        ft.Text("LLM Provider Configuration", size=18, weight=ft.FontWeight.BOLD),
                        ft.Card(
                            content=ft.Container(
                                padding=16,
                                content=ft.Column(
                                    spacing=8,
                                    controls=[
                                        ft.Text("Select Provider", size=14, weight=ft.FontWeight.BOLD),
                                        provider_group,
                                        ft.Divider(),
                                        groq_config,
                                        openai_config,
                                        ollama_config,
                                    ],
                                ),
                            ),
                        ),
                        ft.Container(height=12),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            controls=[
                                ft.TextButton("Cancel", on_click=lambda e: page.run_task(_navigate, page, "/")),
                                ft.FilledButton(
                                    "Save Configuration",
                                    icon=ft.Icons.SAVE,
                                    on_click=save_config,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        ],
    )
