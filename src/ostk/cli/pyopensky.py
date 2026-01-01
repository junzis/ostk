"""PyOpenSky CLI commands."""

import configparser
from pathlib import Path

import click
from prompt_toolkit import prompt as pt_prompt
from pyopensky.config import DEFAULT_CONFIG


def get_config_path() -> Path:
    """Get the pyopensky configuration file path."""
    from pyopensky.config import opensky_config_dir

    return Path(opensky_config_dir) / "settings.conf"


@click.group()
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
