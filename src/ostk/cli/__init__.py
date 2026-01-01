"""CLI for ostk package."""

import os
from pathlib import Path

import click

from .agent import agent
from .pyopensky import pyopensky
from .trajectory import trajectory


def get_config_path() -> Path:
    """Get the pyopensky configuration file path using pyopensky.config.opensky_config_dir."""
    from pyopensky.config import opensky_config_dir

    return Path(opensky_config_dir) / "settings.conf"


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


@click.group(invoke_without_command=True)
@click.option(
    "--no-gui",
    is_flag=True,
    help="Show CLI help instead of launching GUI",
)
@click.pass_context
def cli(ctx, no_gui: bool):
    """OSTK (OpenSky ToolKit) - Nifty tools for opensky with good vibes.

    Run without arguments to launch the GUI, or use subcommands for CLI mode.
    """
    if ctx.invoked_subcommand is None:
        if no_gui:
            click.echo(ctx.get_help())
        else:
            from ostk.gui import run_gui

            run_gui()


# Register command groups
cli.add_command(pyopensky)
cli.add_command(trajectory)
cli.add_command(agent)


if __name__ == "__main__":
    cli()
