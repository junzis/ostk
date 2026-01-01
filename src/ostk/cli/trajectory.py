"""Trajectory CLI commands."""

import click


@click.group()
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
    """Fetch trajectory using pyopensky Trino history() between START and STOP.

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
