# OSTK - Nifty OpenSky tools with good vibes

**OSTK  (OpenSky ToolKit)** provides advanced trajectory reconstruction tools for OpenSky Network ADS-B data, through CLI or Python. It offers enhanced trajectory accuracy through improved CPR decoding.It also includes an LLM-powered agent for natural language queries.

## Features

- Accurate trajectory reconstruction from raw ADS-B messages with enhanced CPR decoding
- Outlier filtering for cleaner trajectories
- LLM-powered agent for natural language OpenSky queries
- Command-line interface for trajectory queries and configuration management
- Built on pyopensky's Trino interface with caching support


All can be accessed though your terminal console:

```sh
# get trajectory rebuild from raw ADS-B messages
ostk trajectory rebuild ...

# get historical trajectory data with various filters
ostk trajectory history ...

# download historical data via natural language
ostk agent console
```

or python API:

```python
from ostk import rebuild

flight = rebuild(icao24, start, stop)
```

```python
from ostk import Agent

agent = Agent()
params = agent.parse_query("...")
flight = agent.execute_query(params)
```


## Installation and configure

Install via pip:
```sh
pip install ostk
```

Configure OpenSky credentials (for pyopensky):

```sh
# set credentials
ostk pyopensky config set

# show config
ostk pyopensky config show
```

## Quick Start

### Rebuild Trajectory

```python
from ostk import rebuild

# Rebuild trajectory from raw ADS-B messages
df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00"
)
```

Returns a pandas DataFrame with columns: `time`, `icao24`, `lat`, `lon`, `baroaltitude`, `velocity`, `heading`, `vertrate`

### LLM Agent

```python
from ostk import Agent

# Initialize agent
agent = Agent()

# Parse natural language query
params = agent.parse_query(
    "Download flights from Amsterdam Schiphol to London Heatharow on Nov 8, 2025 between 13:00 and 15:00"
)

# Execute and get results
df = agent.execute_query(params)
```

### Command Line

**Rebuild Trajectory**

```sh
# Rebuild trajectory from raw ADS-B messages
ostk trajectory rebuild --icao24 485A32 --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" -o trajectory_rebuild.csv
```

**Download History Trajectory**

```sh
# Download historical data with icao24 filter
ostk trajectory history --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" --icao24 485A32 -o trajectory_history.csv

# Download historical data with airport filters
ostk trajectory history --start "2025-11-08 13:00:00" --stop "2025-11-08 15:00:00" --departure-airport EHAM --arrival-airport EGLL -o trajectory_history.csv
```

**LLM Agent**

```sh
# set OpenAI API key for LLM agent
ostk agent config set-key

# launch OSTK LLM agent 
ostk agent console
```

![Trajectory Reconstruction Example](docs/figures/ostk_agent.png)


## Setup LLM Agent

To use the LLM-powered agent, config your OpenAI API key:

```sh
ostk agent config set-key
```

The follow the instruction to input your OpenAI API key. The config file locations are:
- Linux/macOS: `~/.config/ostk/settings.conf`
- Windows: `%LOCALAPPDATA%\ostk\settings.conf`

## Documentation

- **[CLI Reference](docs/cli.md)** - Detailed command-line usage
- **[Python API](docs/api.md)** - Complete API documentation
- **[Examples](docs/examples.md)** - Usage examples and comparisons
- **[Agent Guide](docs/agent.md)** - LLM agent usage

## How Does Trajectory Rebuild Work?

The `rebuild()` function reconstructs trajectories by:

1. Querying raw position and velocity messages from OpenSky's database
2. Pairing odd and even CPR frames for accurate global position decoding
3. Validating positions with reference points to filter outliers
4. Merging position and velocity data with temporal alignment

**When to use `rebuild()` vs `pyopensky.trino.history()`:**

| Feature | rebuild() | history() |
|---------|-----------|-----------|
| Accuracy | Higher (raw CPR decoding) | Standard (pre-computed) |
| Outliers | Fewer (with validation) | More common |
| Speed | Slower (decoding overhead) | Faster (direct query) |
| Filtering | icao24 + time only | Full filtering support |

Use `history()` for faster queries with complex filtering, however with many outliers. Use `rebuild()` for maximum accuracy and fewer outliers. 

![Trajectory Reconstruction Example](docs/figures/history_vs_rebuild.png)


## Authors

- Junzi Sun (j.sun-1@tudelft.nl)

## Related Projects

- [pyopensky](https://github.com/open-aviation/pyopensky/) - Python interface for OpenSky Network data
- [pyModeS](https://github.com/junzis/pyModeS) - ADS-B and Mode S message decoder

## License

MIT License
