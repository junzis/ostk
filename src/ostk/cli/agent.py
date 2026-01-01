"""Agent CLI commands."""

import configparser
import os
from pathlib import Path

import click
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.history import FileHistory


def get_agent_config_dir() -> Path:
    """Get the ostk agent configuration directory path."""
    home = Path.home()
    if os.name == "posix":
        config_dir = home / ".config" / "ostk"
    elif os.name == "nt":
        config_dir = home / "AppData" / "Local" / "ostk"
    else:
        config_dir = home / ".ostk"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_agent_history_path() -> Path:
    """Get the agent history file path."""
    return get_agent_config_dir() / "agent_history"


def fetch_groq_models(api_key: str, tool_use_only: bool = True) -> list[dict]:
    """Fetch available models from Groq API."""
    import httpx

    from ostk.agent.providers.groq_models import EXCLUDE_PATTERNS, TOOL_USE_MODELS

    try:
        response = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        models = data.get("data", [])

        if tool_use_only:
            tool_use_set = set(TOOL_USE_MODELS)
            filtered = []
            for m in models:
                model_id = m.get("id", "")
                if any(pattern in model_id.lower() for pattern in EXCLUDE_PATTERNS):
                    continue
                if model_id in tool_use_set:
                    filtered.append(m)
            return filtered

        return models
    except Exception:
        return []


@click.group()
def agent():
    """LLM agent commands for OpenSky Trino queries."""
    pass


@agent.command("start")
def agent_start():
    """Start interactive LLM agent for OpenSky Trino queries."""
    import sys

    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm, Prompt
    from rich.syntax import Syntax
    from rich.text import Text

    from ostk.agent import Agent

    console = Console()

    try:
        agent_instance = Agent()
    except (RuntimeError, ValueError) as e:
        console.print()
        console.print(
            Panel(
                f"[red bold]Agent Configuration Error![/red bold]\n\n"
                f"{str(e)}\n\n"
                "[cyan]Quick Setup:[/cyan]\n"
                "[bold yellow]  ostk agent config[/bold yellow]  # Interactive setup wizard\n\n"
                "[cyan]Manual Configuration:[/cyan]\n"
                "[bold yellow]  ostk agent config set-provider <provider>[/bold yellow]\n"
                "[bold yellow]  ostk agent config set-model --provider <provider> <model>[/bold yellow]\n"
                "[bold yellow]  ostk agent config set-key --provider <provider>[/bold yellow]\n",
                border_style="red",
                padding=(1, 2),
            )
        )
        console.print()
        sys.exit(1)

    history_path = get_agent_history_path()
    history = FileHistory(str(history_path))

    # Welcome banner
    welcome_text = Text()
    welcome_text.append("✨ OSTK ", style="bold cyan")
    welcome_text.append("LLM Agent\n", style="bold white")
    welcome_text.append(
        "\nTell me what OpenSky history data you want to download. \nExample:",
        style="dim",
    )
    welcome_text.append(
        "State vectors from Amsterdam Schiphol to London Heathrow on 08/11/2025 between 13:00 and 15:00",
        style="bold yellow",
    )
    welcome_text.append("\nType ", style="dim")
    welcome_text.append("exit", style="bold yellow")
    welcome_text.append(" or ", style="dim")
    welcome_text.append("quit", style="bold yellow")
    welcome_text.append(" to leave", style="dim")

    console.print(Panel(welcome_text, border_style="cyan", padding=(1, 2)))
    console.print()

    while True:
        try:
            user_query = pt_prompt("❯❯ ", history=history)
        except (KeyboardInterrupt, EOFError):
            console.print("\n")
            console.print("👋 Goodbye!", style="bold cyan")
            break

        if user_query.strip().lower() in ("exit", "quit"):
            console.print("👋 Goodbye!", style="bold cyan")
            break

        if not user_query.strip():
            continue

        try:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn("[cyan]Analyzing your query..."),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("parse", total=None)
                params = agent_instance.parse_query(user_query)

            console.print()
            query_code = agent_instance.build_history_call(params)
            syntax = Syntax(
                query_code,
                "python",
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
            )
            console.print(
                Panel(
                    syntax,
                    title="[bold yellow]📝 Generated Query",
                    title_align="left",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            console.print()

            if not Confirm.ask(
                "[cyan]Proceed with this query?", default=True, console=console
            ):
                console.print("[dim]Query cancelled[/dim]")
                console.print()
                continue

            console.print()
            fmt = Prompt.ask(
                "[cyan]Save format",
                choices=["csv", "parquet"],
                default="csv",
                console=console,
            )

            output = Prompt.ask(
                "[cyan]Output folder[/cyan] [dim](leave blank for current folder)[/dim]",
                default="",
                console=console,
            )
            output = output if output else None

            console.print()

            with Progress(
                SpinnerColumn(spinner_name="bouncingBar"),
                TextColumn("[green]Fetching data from OpenSky..."),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("execute", total=None)
                df = agent_instance.execute_query(params)

            console.print()

            if df is None or df.empty:
                console.print(
                    Panel(
                        "[yellow]⚠️  No data found for the given parameters.[/yellow]\n\nTry adjusting your query parameters or time range.",
                        border_style="yellow",
                        padding=(1, 2),
                    )
                )
            else:
                out_path = agent_instance.save_result(df, fmt=fmt, output=output)
                stats = Text()
                stats.append(f"✓ Saved {len(df):,} rows\n", style="bold green")
                stats.append(f"📁 {out_path}", style="dim")
                console.print(
                    Panel(
                        stats,
                        title="[bold green]Success!",
                        title_align="left",
                        border_style="green",
                        padding=(1, 2),
                    )
                )

            console.print()

        except Exception as e:
            console.print()
            console.print(
                Panel(
                    f"[red bold]Error:[/red bold]\n{str(e)}",
                    border_style="red",
                    padding=(1, 2),
                )
            )
            console.print()


def agent_config_setup_wizard():
    """Interactive setup wizard for agent configuration."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.text import Text

    from ostk.agent.providers.groq_models import DEFAULT_MODEL, TOOL_USE_MODELS

    console = Console()

    # Welcome banner
    welcome = Text()
    welcome.append("🚀 OSTK Agent Configuration Wizard\n\n", style="bold cyan")
    welcome.append(
        "This wizard will guide you through setting up your LLM provider.\n",
        style="dim",
    )
    welcome.append(
        "You can change these settings anytime by running this command again.",
        style="dim",
    )

    console.print(Panel(welcome, border_style="cyan", padding=(1, 2)))
    console.print()

    provider_info = {
        "groq": {
            "name": "Groq (with free APIs)",
            "description": "Fast inference with open models",
            "models": TOOL_USE_MODELS,
            "default_model": DEFAULT_MODEL,
            "requires_key": True,
            "key_url": "https://console.groq.com",
        },
        "openai": {
            "name": "OpenAI",
            "description": "Official OpenAI API (GPT-4, GPT-3.5, etc.)",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            "default_model": "gpt-4o-mini",
            "requires_key": True,
            "key_url": "https://platform.openai.com/api-keys",
        },
        "ollama": {
            "name": "Ollama",
            "description": "Local LLM runner (no API key required)",
            "models": ["qwen2.5-coder:7b", "gemma3:12b"],
            "default_model": "qwen2.5-coder:7b",
            "requires_key": False,
            "key_url": None,
        },
    }

    # Step 1: Choose provider
    console.print("[bold yellow]Step 1:[/bold yellow] Choose your LLM provider")
    console.print()

    for idx, (key, info) in enumerate(provider_info.items(), 1):
        console.print(f"  [cyan]{idx}.[/cyan] [bold]{info['name']}[/bold]")
        console.print(f"     {info['description']}")
        console.print()

    provider_choice = Prompt.ask(
        "[cyan]Select provider[/cyan]", choices=["1", "2", "3"], default="1"
    )

    provider_map = {"1": "groq", "2": "openai", "3": "ollama"}
    selected_provider = provider_map[provider_choice]
    provider_data = provider_info[selected_provider]

    console.print()
    console.print(f"✓ Selected: [bold green]{provider_data['name']}[/bold green]")
    console.print()

    api_key = None
    base_url = None
    model = None

    # Provider-specific configuration
    if selected_provider == "groq":
        # Step 2: API key
        console.print("[bold yellow]Step 2:[/bold yellow] Enter Groq API key")
        console.print()
        console.print(f"  Get your API key from: [cyan]{provider_data['key_url']}[/cyan]")
        console.print()

        api_key = pt_prompt("Groq API key: ", is_password=True)

        if not api_key:
            console.print("\n[red]Error: API key is required for Groq.[/red]\n")
            return

        console.print("\n✓ API key saved (hidden for security)\n")

        # Step 3: Fetch and select model
        console.print("[bold yellow]Step 3:[/bold yellow] Choose a Groq model")
        console.print("\n  [dim]Fetching models with tool calling support...[/dim]")

        groq_models = fetch_groq_models(api_key, tool_use_only=True)

        if groq_models:
            default_model = provider_data["default_model"]
            all_model_ids = [m["id"] for m in groq_models]
            other_models = sorted([m for m in all_model_ids if m != default_model])

            if default_model in all_model_ids:
                model_ids = [default_model] + other_models
            else:
                model_ids = other_models

            console.print(f"\n  [green]Found {len(model_ids)} models:[/green]\n")

            for idx, model_id in enumerate(model_ids, 1):
                if model_id == default_model:
                    console.print(f"    [cyan]{idx:2}.[/cyan] {model_id} [dim](default)[/dim]")
                else:
                    console.print(f"    [cyan]{idx:2}.[/cyan] {model_id}")

            console.print("\n  [dim]Or enter a custom model name.[/dim]\n")

            model_input = Prompt.ask("[cyan]Enter model number or name[/cyan]", default="1")

            if model_input.isdigit():
                model_idx = int(model_input)
                if 1 <= model_idx <= len(model_ids):
                    model = model_ids[model_idx - 1]
                else:
                    model = provider_data["default_model"]
            else:
                model = model_input
        else:
            console.print("\n  [yellow]Could not fetch models. Using defaults.[/yellow]")
            model = Prompt.ask("[cyan]Enter model name[/cyan]", default=provider_data["default_model"])

        console.print(f"\n✓ Model: [bold green]{model}[/bold green]\n")

    elif selected_provider == "ollama":
        # Step 2: Choose model
        console.print(f"[bold yellow]Step 2:[/bold yellow] Choose a model")
        console.print(f"\n  Recommended: [dim]{', '.join(provider_data['models'])}[/dim]\n")

        model = Prompt.ask("[cyan]Enter model name[/cyan]", default=provider_data["default_model"])

        console.print(f"\n✓ Model: [bold green]{model}[/bold green]\n")

        # Step 3: Base URL
        console.print("[bold yellow]Step 3:[/bold yellow] Configure Ollama")
        console.print("\n  [dim]Ollama runs locally and doesn't require an API key.[/dim]\n")

        base_url = Prompt.ask("[cyan]Ollama base URL[/cyan]", default="http://localhost:11434")

        console.print(f"\n✓ Base URL: [bold green]{base_url}[/bold green]\n")

    else:  # OpenAI
        # Step 2: Choose model
        console.print(f"[bold yellow]Step 2:[/bold yellow] Choose a model")
        console.print(f"\n  Recommended: [dim]{', '.join(provider_data['models'])}[/dim]\n")

        model = Prompt.ask("[cyan]Enter model name[/cyan]", default=provider_data["default_model"])

        console.print(f"\n✓ Model: [bold green]{model}[/bold green]\n")

        # Step 3: API key
        console.print("[bold yellow]Step 3:[/bold yellow] Enter API key")
        console.print(f"\n  Get your API key from: [cyan]{provider_data['key_url']}[/cyan]\n")

        api_key = pt_prompt(f"{provider_data['name']} API key: ", is_password=True)

        if not api_key:
            console.print("\n[red]Error: API key is required.[/red]\n")
            return

        console.print("\n✓ API key saved (hidden for security)\n")

    # Step 4: Confirm and save
    console.print("[bold yellow]Step 4:[/bold yellow] Review configuration\n")

    summary = Text()
    summary.append("Provider: ", style="dim")
    summary.append(f"{provider_data['name']}\n", style="bold")
    summary.append("Model: ", style="dim")
    summary.append(f"{model}\n", style="bold")

    if selected_provider == "ollama":
        summary.append("Base URL: ", style="dim")
        summary.append(f"{base_url}\n", style="bold")
    elif provider_data["requires_key"]:
        summary.append("API Key: ", style="dim")
        summary.append("**************** (hidden)\n", style="bold")

    console.print(Panel(summary, title="Configuration Summary", border_style="cyan"))
    console.print()

    if not Confirm.ask("[cyan]Save this configuration?[/cyan]", default=True):
        console.print("\n[yellow]Configuration cancelled.[/yellow]")
        return

    # Save configuration
    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    config = configparser.ConfigParser()

    if config_path.exists():
        config.read(config_path)

    if not config.has_section("llm"):
        config.add_section("llm")

    config.set("llm", "provider", selected_provider)
    config.set("llm", f"{selected_provider}_model", model)

    if selected_provider == "ollama" and base_url:
        config.set("llm", "ollama_base_url", base_url)
    elif api_key:
        config.set("llm", f"{selected_provider}_api_key", api_key)

    with open(config_path, "w") as f:
        config.write(f)

    console.print()
    console.print(
        Panel(
            f"[bold green]✓ Configuration saved successfully![/bold green]\n\n"
            f"Config file: [dim]{config_path}[/dim]\n\n"
            f"You can now use the agent by running:\n"
            f"[bold cyan]  ostk agent start[/bold cyan]",
            border_style="green",
            padding=(1, 2),
        )
    )
    console.print()


@agent.group(invoke_without_command=True)
@click.pass_context
def config(ctx):
    """Agent config management - interactive setup wizard."""
    if ctx.invoked_subcommand is None:
        agent_config_setup_wizard()


@config.command("set-key")
@click.option(
    "--provider",
    type=click.Choice(["openai", "ollama", "groq"]),
    default="openai",
    help="LLM provider",
)
def agent_config_set_key(provider):
    """Set or update API key for LLM provider."""
    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    cfg = configparser.ConfigParser()
    if config_path.exists():
        cfg.read(config_path)
    if not cfg.has_section("llm"):
        cfg.add_section("llm")

    if provider == "ollama":
        click.secho("Ollama doesn't require an API key (it runs locally).", fg="yellow")
        base_url = click.prompt(
            "Ollama base URL", default="http://localhost:11434", show_default=True
        )
        cfg.set("llm", "ollama_base_url", base_url)
        with open(config_path, "w") as f:
            cfg.write(f)
        click.secho(f"Ollama base URL updated in {config_path}.", fg="green")
        return

    key_name = f"{provider}_api_key"
    prompt_text = f"Enter your {provider.title()} API key: "
    api_key = pt_prompt(prompt_text, is_password=True)
    cfg.set("llm", key_name, api_key)
    with open(config_path, "w") as f:
        cfg.write(f)
    click.secho(f"{provider.title()} API key updated in {config_path}.", fg="green")


@config.command("set-provider")
@click.argument("provider_name", type=click.Choice(["openai", "ollama", "groq"]))
def agent_config_set_provider(provider_name):
    """Set the default LLM provider."""
    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    cfg = configparser.ConfigParser()
    if config_path.exists():
        cfg.read(config_path)
    if not cfg.has_section("llm"):
        cfg.add_section("llm")

    cfg.set("llm", "provider", provider_name)
    with open(config_path, "w") as f:
        cfg.write(f)
    click.secho(f"Default provider set to '{provider_name}'.", fg="green")


@config.command("set-model")
@click.option(
    "--provider",
    type=click.Choice(["openai", "ollama", "groq"]),
    required=True,
    help="LLM provider",
)
@click.argument("model_name")
def agent_config_set_model(provider, model_name):
    """Set the model for a specific provider."""
    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    cfg = configparser.ConfigParser()
    if config_path.exists():
        cfg.read(config_path)
    if not cfg.has_section("llm"):
        cfg.add_section("llm")

    model_key = f"{provider}_model"
    cfg.set("llm", model_key, model_name)
    with open(config_path, "w") as f:
        cfg.write(f)
    click.secho(f"Model for '{provider}' set to '{model_name}'.", fg="green")


@config.command("show")
def agent_config_show():
    """Show current LLM provider configuration."""
    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"

    if not config_path.exists():
        click.secho("No configuration file found!", fg="red")
        click.echo("\nRun 'ostk agent config' to configure the agent.")
        return

    cfg = configparser.ConfigParser()
    cfg.read(config_path)

    if not cfg.has_section("llm"):
        click.secho("No [llm] section found in config!", fg="red")
        return

    click.echo(f"Configuration file: {config_path}\n")

    provider = cfg.get("llm", "provider", fallback="openai")
    click.secho(f"Current provider: {provider}", fg="cyan", bold=True)
    click.echo()

    click.secho("Provider Settings:", fg="yellow")
    for provider_name in ["openai", "ollama", "groq"]:
        model_key = f"{provider_name}_model"
        api_key_key = f"{provider_name}_api_key"

        model = cfg.get("llm", model_key, fallback=None)
        api_key = cfg.get("llm", api_key_key, fallback=None)

        if model or api_key:
            click.echo(f"  [{provider_name}]")
            if model:
                click.echo(f"    model: {model}")
            if api_key:
                click.echo(f"    api_key: {'*' * 8}")

            if provider_name == "ollama":
                base_url = cfg.get("llm", "ollama_base_url", fallback="http://localhost:11434")
                click.echo(f"    base_url: {base_url}")

    click.echo()


@agent.command("clear-history")
def agent_clear_history():
    """Clear agent start command history."""
    history_path = get_agent_history_path()
    if history_path.exists():
        history_path.unlink()
        click.secho("Agent command history cleared successfully.", fg="green")
    else:
        click.secho("No command history found.", fg="yellow")
