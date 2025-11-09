"""CLI for ostk package."""

import configparser
import os
from pathlib import Path

import click
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.history import FileHistory
from pyopensky.config import DEFAULT_CONFIG


def get_config_path() -> Path:
    """Get the pyopensky configuration file path using pyopensky.config.opensky_config_dir."""
    from pyopensky.config import opensky_config_dir

    return Path(opensky_config_dir) / "settings.conf"


def get_agent_config_dir() -> Path:
    """Get the ostk agent configuration directory path."""
    home = Path.home()
    if os.name == "posix":
        # Linux/macOS
        config_dir = home / ".config" / "ostk"
    elif os.name == "nt":
        # Windows
        config_dir = home / "AppData" / "Local" / "ostk"
    else:
        config_dir = home / ".ostk"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_agent_history_path() -> Path:
    """Get the agent history file path."""
    return get_agent_config_dir() / "agent_history"


@click.group()
def cli():
    """OSTK (OpenSky ToolKit) - Nifty tools for opensky with good vibes."""

    import click

    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()


@cli.group()
def pyopensky():
    """PyOpenSky related commands."""
    pass


@pyopensky.command("clearcache")
def clearcache():
    """Clear all cached pyopensky data."""
    import shutil

    from pyopensky.config import cache_dir

    cache_path = Path(cache_dir)
    if not cache_path.exists():
        click.secho(f"No cache directory found at: {cache_path}", fg="yellow")
        return
    click.secho(
        f"This will delete ALL cached pyopensky data at: {cache_path}", fg="red"
    )
    confirm = click.confirm("Are you sure you want to clear the cache?", default=False)
    if not confirm:
        click.echo("Cache clear cancelled.")
        return
    try:
        shutil.rmtree(cache_path)
        click.secho("Cache cleared successfully.", fg="green")
    except Exception as e:
        click.secho(f"Failed to clear cache: {e}", fg="red")


@pyopensky.group()
def config():
    """Manage PyOpenSky configuration."""
    pass


@config.command("set")
def config_set():
    """Set or update PyOpenSky credentials and parameters."""
    config_file = get_config_path()

    if config_file.exists():
        click.echo(f"Configuration file already exists at: {config_file}")
        overwrite = click.confirm("Do you want to overwrite it?", default=False)
        if not overwrite:
            click.echo("Configuration update cancelled.")
            return

    click.echo("Setting PyOpenSky configuration...")
    click.echo()

    # Prompt for Trino credentials
    username = click.prompt(
        "Trino username (for Trino interface)",
        default="",
        show_default=False,
    )
    password = pt_prompt(
        "Trino password (for Trino interface): ",
        is_password=True,
    )

    # Prompt for Live API credentials
    client_id = click.prompt(
        "Live API client_id (for OpenSky Live API)",
        default="",
        show_default=False,
    )
    client_secret = pt_prompt(
        "Live API client_secret (for OpenSky Live API): ",
        is_password=True,
    )

    # Prompt for cache purge days
    cache_purge = click.prompt(
        "Cache purge (e.g. '90 days')",
        default="90 days",
        show_default=True,
    )

    # Create config directory if it doesn't exist
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Prepare config content
    config_content = DEFAULT_CONFIG
    config_content = config_content.replace("username =", f"username = {username}")
    config_content = config_content.replace("password =", f"password = {password}")
    config_content = config_content.replace("client_id =", f"client_id = {client_id}")
    config_content = config_content.replace(
        "client_secret =", f"client_secret = {client_secret}"
    )
    config_content = config_content.replace("purge = 90 days", f"purge = {cache_purge}")

    config_file.write_text(config_content)

    click.echo()
    click.echo(f"Configuration file updated successfully at: {config_file}")
    click.secho("Note: Keep your credentials secure!", fg="yellow")


@config.command("show")
def config_show():
    """Show PyOpenSky configuration."""
    config_file = get_config_path()

    if not config_file.exists():
        click.secho("Configuration file not found!", fg="red")
        click.echo()
        click.echo("Please run the following command to set credentials:")
        click.secho("  ostk pyopensky config set", fg="green")
        return

    click.echo(f"Configuration file location: {config_file}")
    click.echo()

    # Read and display the config file
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file)

    # Display configuration (mask password and client_secret)
    for section in config_parser.sections():
        click.secho(f"[{section}]", fg="cyan", bold=True)
        for key, value in config_parser.items(section):
            if key in ("password", "client_secret") and value:
                display_value = "*" * len(value)
            else:
                display_value = value if value else "(not set)"
            click.echo(f"  {key} = {display_value}")
        click.echo()


@cli.group()
def trajectory():
    """Trajectory tools."""
    pass


@trajectory.command()
@click.option("--icao24", required=True, help="ICAO24 transponder code")
@click.option("--start", required=True, help="Start time (UTC)")
@click.option("--stop", required=True, help="Stop time (UTC)")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output file to write results (CSV format)",
)
@click.option("--cached/--no-cached", default=True, help="Use cached results")
@click.option("--compress/--no-compress", default=False, help="Compress cache files")
def rebuild(icao24, start, stop, output, cached, compress):
    """Rebuild trajectory for ICAO24 between START and STOP.

    Example:
        ostk trajectory rebuild --icao24 485A32 --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00"
    """
    import pandas as pd

    from ostk.rebuild import rebuild as rebuild_func

    click.echo(f"Rebuilding trajectory for {icao24} from {start} to {stop}...")
    df = rebuild_func(icao24, start, stop, cached=cached, compress=compress)
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        click.secho("No data found for the given parameters.", fg="red")
    else:
        if output:
            df.to_csv(output, index=False)
            click.secho(f"Output written to {output}", fg="green")
        else:
            click.echo(df.to_string(index=False))


@trajectory.command()
@click.option("--start", required=True, help="Start time (UTC)")
@click.option("--stop", required=True, help="Stop time (UTC)")
@click.option("--icao24", default=None, help="ICAO24 transponder address")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output file to write results (CSV format)",
)
@click.option(
    "--callsign", default=None, help="Callsign (string or comma-separated list)"
)
@click.option(
    "--serials", default=None, help="Sensor serials (int or comma-separated list)"
)
@click.option(
    "--bounds", default=None, help="Geographical bounds (format: west,south,east,north)"
)
@click.option("--departure-airport", default=None, help="Departure airport ICAO code")
@click.option("--arrival-airport", default=None, help="Arrival airport ICAO code")
@click.option("--airport", default=None, help="Airport ICAO code")
@click.option("--time-buffer", default=None, help="Time buffer (e.g. '10m', '1h')")
@click.option("--cached/--no-cached", default=True, help="Use cached results")
@click.option("--compress/--no-compress", default=False, help="Compress cache files")
@click.option("--limit", default=None, type=int, help="Limit number of records")
def history(
    start,
    stop,
    icao24,
    output,
    callsign,
    serials,
    bounds,
    departure_airport,
    arrival_airport,
    airport,
    time_buffer,
    cached,
    compress,
    limit,
):
    """Fetch trajectory using pyopensky Trino history() between START and STOP, with advanced filtering options.

    Example:
        ostk trajectory history --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" --icao24 485A32
    """
    import pandas as pd
    from pyopensky.trino import Trino

    if icao24:
        click.echo(
            f"Fetching history trajectory for {icao24} from {start} to {stop}..."
        )
    else:
        click.echo(f"Fetching history trajectory from {start} to {stop}...")
    trino = Trino()

    # Parse callsign and serials as lists if comma-separated
    if callsign:
        callsign = (
            [c.strip() for c in callsign.split(",")] if "," in callsign else callsign
        )
    if serials:
        serials = (
            [int(s.strip()) for s in serials.split(",")]
            if "," in serials
            else int(serials)
        )
    # Parse bounds as tuple if provided
    if bounds:
        try:
            bounds = tuple(float(x) for x in bounds.split(","))
        except Exception:
            click.secho("Invalid bounds format. Use: west,south,east,north", fg="red")
            return
    # Parse time_buffer as string (let pandas handle)
    # Compose kwargs
    kwargs = dict(
        callsign=callsign,
        serials=serials,
        bounds=bounds,
        departure_airport=departure_airport,
        arrival_airport=arrival_airport,
        airport=airport,
        time_buffer=time_buffer,
        cached=cached,
        compress=compress,
        limit=limit,
    )
    # Remove None values
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    df = trino.history(start=start, stop=stop, icao24=icao24, **kwargs)
    df = df[
        [
            "time",
            "icao24",
            "lat",
            "lon",
            "baroaltitude",
            "velocity",
            "heading",
            "vertrate",
        ]
    ]
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        click.secho("No data found for the given parameters.", fg="red")
    else:
        if output:
            df.to_csv(output, index=False)
            click.secho(f"Output written to {output}", fg="green")
        else:
            click.echo(df.to_string(index=False))


@cli.group()
def agent():
    """LLM agent commands for OpenSky Trino queries."""
    pass


@agent.command("console")
def agent_console():
    """Interactive LLM agent for OpenSky Trino queries."""
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
        agent = Agent()
    except (RuntimeError, ValueError) as e:
        console.print()
        console.print(
            Panel(
                f"[red bold]Agent Configuration Error![/red bold]\n\n"
                f"{str(e)}\n\n"
                "[cyan]Quick Setup:[/cyan]\n"
                "[bold yellow]  ostk agent config[/bold yellow]  # Interactive setup wizard (recommended)\n\n"
                "[cyan]Manual Configuration:[/cyan]\n"
                "[bold yellow]  ostk agent config set-provider <provider>[/bold yellow]  # Set provider\n"
                "[bold yellow]  ostk agent config set-model --provider <provider> <model>[/bold yellow]  # Set model\n"
                "[bold yellow]  ostk agent config set-key --provider <provider>[/bold yellow]  # Set API key\n"
                "[bold yellow]  ostk agent config show[/bold yellow]  # Show current config\n",
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
        "State vectors from Amsterdam Schiphol to London Heatharow on 08/11/2025 between 13:00 and 15:00",
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
            # Get user input with custom prompt
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
            # Parse query with spinner
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn("[cyan]Analyzing your query..."),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("parse", total=None)
                params = agent.parse_query(user_query)

            # Display generated query
            console.print()
            query_code = agent.build_history_call(params)
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

            # Confirm execution
            if not Confirm.ask(
                "[cyan]Proceed with this query?", default=True, console=console
            ):
                console.print("[dim]Query cancelled[/dim]")
                console.print()
                continue

            # Get format
            console.print()
            fmt = Prompt.ask(
                "[cyan]Save format",
                choices=["csv", "parquet"],
                default="csv",
                console=console,
            )

            # Get output path
            output = Prompt.ask(
                "[cyan]Output folder[/cyan] [dim](leave blank for current folder)[/dim]",
                default="",
                console=console,
            )
            output = output if output else None

            console.print()

            # Execute query with spinner
            with Progress(
                SpinnerColumn(spinner_name="bouncingBar"),
                TextColumn("[green]Fetching data from OpenSky..."),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("execute", total=None)
                df = agent.execute_query(params)

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
                # Save results
                out_path = agent.save_result(df, fmt=fmt, output=output)

                # Success message with stats
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
    import configparser

    from prompt_toolkit import prompt as pt_prompt
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.text import Text

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

    # Provider information
    provider_info = {
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

        "groq": {
            "name": "Groq",
            "description": "Fast inference with open models",
            "models": [
                "llama-3.3-70b-versatile",
                "llama-3.1-70b-versatile",
                "mixtral-8x7b-32768",
            ],
            "default_model": "llama-3.3-70b-versatile",
            "requires_key": True,
            "key_url": "https://console.groq.com",
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

    provider_map = {"1": "openai", "2": "ollama", "3": "groq"}

    selected_provider = provider_map[provider_choice]
    provider_data = provider_info[selected_provider]

    console.print()
    console.print(f"✓ Selected: [bold green]{provider_data['name']}[/bold green]")
    console.print()

    # Step 2: Choose model
    console.print(
        f"[bold yellow]Step 2:[/bold yellow] Choose a model for {provider_data['name']}"
    )
    console.print()
    console.print(
        f"  Recommended models: [dim]{', '.join(provider_data['models'])}[/dim]"
    )
    console.print()

    model = Prompt.ask(
        "[cyan]Enter model name[/cyan]", default=provider_data["default_model"]
    )

    console.print()
    console.print(f"✓ Model: [bold green]{model}[/bold green]")
    console.print()

    # Step 3: API key (if needed)
    api_key = None
    base_url = None

    if selected_provider == "ollama":
        console.print("[bold yellow]Step 3:[/bold yellow] Configure Ollama")
        console.print()
        console.print(
            "  [dim]Ollama runs locally and doesn't require an API key.[/dim]"
        )
        console.print()

        base_url = Prompt.ask(
            "[cyan]Ollama base URL[/cyan]", default="http://localhost:11434"
        )

        console.print()
        console.print(f"✓ Base URL: [bold green]{base_url}[/bold green]")
        console.print()

    elif provider_data["requires_key"]:
        console.print(f"[bold yellow]Step 3:[/bold yellow] Enter API key")
        console.print()
        console.print(
            f"  Get your API key from: [cyan]{provider_data['key_url']}[/cyan]"
        )
        console.print()

        api_key = pt_prompt(f"{provider_data['name']} API key: ", is_password=True)

        if not api_key:
            console.print()
            console.print("[red]Error: API key is required for this provider.[/red]")
            console.print()
            return

        console.print()
        console.print(f"✓ API key saved (hidden for security)")
        console.print()

    # Step 4: Confirm and save
    console.print("[bold yellow]Step 4:[/bold yellow] Review configuration")
    console.print()

    summary = Text()
    summary.append(f"Provider: ", style="dim")
    summary.append(f"{provider_data['name']}\n", style="bold")
    summary.append(f"Model: ", style="dim")
    summary.append(f"{model}\n", style="bold")

    if selected_provider == "ollama":
        summary.append(f"Base URL: ", style="dim")
        summary.append(f"{base_url}\n", style="bold")
    elif provider_data["requires_key"]:
        summary.append(f"API Key: ", style="dim")
        summary.append(f"{'*' * 16} (hidden)\n", style="bold")

    console.print(Panel(summary, title="Configuration Summary", border_style="cyan"))
    console.print()

    if not Confirm.ask("[cyan]Save this configuration?[/cyan]", default=True):
        console.print()
        console.print("[yellow]Configuration cancelled.[/yellow]")
        return

    # Save configuration
    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    config = configparser.ConfigParser()

    if config_path.exists():
        config.read(config_path)

    if not config.has_section("llm"):
        config.add_section("llm")

    # Set provider
    config.set("llm", "provider", selected_provider)

    # Set model
    model_key = f"{selected_provider}_model"
    config.set("llm", model_key, model)

    # Set API key or base URL
    if selected_provider == "ollama" and base_url:
        config.set("llm", "ollama_base_url", base_url)
    elif api_key:
        api_key_key = f"{selected_provider}_api_key"
        config.set("llm", api_key_key, api_key)

    # Write config
    with open(config_path, "w") as f:
        config.write(f)

    console.print()
    console.print(
        Panel(
            f"[bold green]✓ Configuration saved successfully![/bold green]\n\n"
            f"Config file: [dim]{config_path}[/dim]\n\n"
            f"You can now use the agent by running:\n"
            f"[bold cyan]  ostk agent console[/bold cyan]",
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
        # Run interactive setup wizard
        agent_config_setup_wizard()


@config.command("set-key")
@click.option(
    "--provider",
    type=click.Choice(["openai", "ollama", "groq"]),
    default="openai",
    help="LLM provider",
)
def agent_config_set_key(provider):
    """Set or update API key for LLM provider (for quick updates; use 'ostk agent config' for full setup)."""
    import configparser
    from pathlib import Path

    import click

    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    config = configparser.ConfigParser()
    if config_path.exists():
        config.read(config_path)
    if not config.has_section("llm"):
        config.add_section("llm")

    # Ollama doesn't require an API key
    if provider == "ollama":
        click.secho("Ollama doesn't require an API key (it runs locally).", fg="yellow")
        base_url = click.prompt(
            "Ollama base URL", default="http://localhost:11434", show_default=True
        )
        config.set("llm", "ollama_base_url", base_url)
        with open(config_path, "w") as f:
            config.write(f)
        click.secho(
            f"Ollama base URL updated in {config_path} [llm] section.", fg="green"
        )
        return

    from prompt_toolkit import prompt as pt_prompt

    key_name = f"{provider}_api_key"
    prompt_text = f"Enter your {provider.replace('_', ' ').title()} API key: "
    api_key = pt_prompt(prompt_text, is_password=True)
    config.set("llm", key_name, api_key)
    with open(config_path, "w") as f:
        config.write(f)
    click.secho(
        f"{provider.replace('_', ' ').title()} API key updated in {config_path} [llm] section.",
        fg="green",
    )


@config.command("set-provider")
@click.argument(
    "provider_name", type=click.Choice(["openai", "ollama", "groq"])
)
def agent_config_set_provider(provider_name):
    """Set the default LLM provider (for quick updates; use 'ostk agent config' for full setup)."""
    import configparser

    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    config = configparser.ConfigParser()
    if config_path.exists():
        config.read(config_path)
    if not config.has_section("llm"):
        config.add_section("llm")

    config.set("llm", "provider", provider_name)
    with open(config_path, "w") as f:
        config.write(f)
    click.secho(
        f"Default provider set to '{provider_name}' in {config_path} [llm] section.",
        fg="green",
    )


@config.command("set-model")
@click.option(
    "--provider",
    type=click.Choice(["openai", "ollama", "groq"]),
    required=True,
    help="LLM provider",
)
@click.argument("model_name")
def agent_config_set_model(provider, model_name):
    """Set the model for a specific provider (for quick updates; use 'ostk agent config' for full setup)."""
    import configparser

    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"
    config = configparser.ConfigParser()
    if config_path.exists():
        config.read(config_path)
    if not config.has_section("llm"):
        config.add_section("llm")

    model_key = f"{provider}_model"
    config.set("llm", model_key, model_name)
    with open(config_path, "w") as f:
        config.write(f)
    click.secho(
        f"Model for '{provider}' set to '{model_name}' in {config_path} [llm] section.",
        fg="green",
    )


@config.command("show")
def agent_config_show():
    """Show current LLM provider configuration."""
    import configparser

    config_dir = get_agent_config_dir()
    config_path = config_dir / "settings.conf"

    if not config_path.exists():
        click.secho("No configuration file found!", fg="red")
        click.echo()
        click.echo("Run the following command to configure the agent:")
        click.secho("  ostk agent config set-provider <provider>", fg="green")
        return

    config = configparser.ConfigParser()
    config.read(config_path)

    if not config.has_section("llm"):
        click.secho("No [llm] section found in config!", fg="red")
        return

    click.echo(f"Configuration file: {config_path}")
    click.echo()

    provider = config.get("llm", "provider", fallback="openai")
    click.secho(f"Current provider: {provider}", fg="cyan", bold=True)
    click.echo()

    # Show provider-specific settings
    click.secho("Provider Settings:", fg="yellow")
    for provider_name in ["openai", "ollama", "groq"]:
        model_key = f"{provider_name}_model"
        api_key_key = f"{provider_name}_api_key"

        model = config.get("llm", model_key, fallback=None)
        api_key = config.get("llm", api_key_key, fallback=None)

        if model or api_key:
            click.echo(f"  [{provider_name}]")
            if model:
                click.echo(f"    model: {model}")
            if api_key:
                click.echo(f"    api_key: {'*' * 8}")

            # Show base_url for ollama
            if provider_name == "ollama":
                base_url = config.get(
                    "llm", "ollama_base_url", fallback="http://localhost:11434"
                )
                click.echo(f"    base_url: {base_url}")

    click.echo()


@agent.command("clear-history")
def agent_clear_history():
    """Clear agent console command history."""
    history_path = get_agent_history_path()
    if history_path.exists():
        history_path.unlink()
        click.secho("Agent command history cleared successfully.", fg="green")
    else:
        click.secho("No command history found.", fg="yellow")


if __name__ == "__main__":
    cli()
