# Command Line Interface Reference

## Overview

OSTK provides a comprehensive CLI for trajectory reconstruction, configuration management, and LLM-powered queries.

## Global Commands

```sh
ostk --help    # Show all available commands
```

## Configuration Management

### PyOpenSky Configuration

Set up OpenSky Network credentials for accessing historical data:

```sh
ostk pyopensky config set
```

Interactive prompts for:
- Trino username and password (for historical database access)
- Live API client_id and client_secret (for real-time API)
- Cache purge period (default: 90 days)

**Show current configuration:**
```sh
ostk pyopensky config show
```
Displays configuration with passwords masked.

**Config file location:**
- Managed by pyopensky: `pyopensky.config.opensky_config_dir/settings.conf`

### Clear Cache

```sh
ostk pyopensky clearcache
```

Removes all cached OpenSky data. You'll be prompted for confirmation.

**Cache location:** `pyopensky.config.cache_dir`

## Trajectory Commands

### Rebuild (Enhanced Accuracy)

Reconstruct trajectory from raw ADS-B messages with enhanced CPR decoding:

```sh
ostk trajectory rebuild --icao24 ICAO24 --start START --stop STOP [OPTIONS]
```

**Required Options:**
- `--icao24 TEXT` - Aircraft transponder code (e.g., 485A32)
- `--start TEXT` - Start time (e.g., "2025-11-08 12:00:00")
- `--stop TEXT` - Stop time (e.g., "2025-11-08 15:00:00")

**Optional Flags:**
- `-o, --output PATH` - Save to CSV file (default: print to terminal)
- `--cached/--no-cached` - Use cached results (default: cached)
- `--compress/--no-compress` - Compress cache files (default: no-compress)

**Examples:**

Print to terminal:
```sh
ostk trajectory rebuild --icao24 485A32 --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00"
```

Save to file:
```sh
ostk trajectory rebuild --icao24 485A32 --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" -o flight.csv
```

Force fresh query:
```sh
ostk trajectory rebuild --icao24 485A32 --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" --no-cached
```

**Output columns:**
`time`, `icao24`, `lat`, `lon`, `baroaltitude`, `velocity`, `heading`, `vertrate`

### History (Fast Queries)

Query pre-computed state vectors using pyopensky's Trino interface:

```sh
ostk trajectory history --start START --stop STOP [OPTIONS]
```

**Required Options:**
- `--start TEXT` - Start time (e.g., "2025-11-08 12:00:00")
- `--stop TEXT` - Stop time (e.g., "2025-11-08 15:00:00")

**Filtering Options:**
- `--icao24 TEXT` - Filter by ICAO24 transponder code
- `--callsign TEXT` - Filter by callsign (comma-separated for multiple)
- `--serials INT` - Filter by sensor serials (comma-separated for multiple)
- `--bounds WEST,SOUTH,EAST,NORTH` - Geographical bounding box
- `--departure-airport CODE` - Departure airport ICAO code
- `--arrival-airport CODE` - Arrival airport ICAO code
- `--airport CODE` - Airport code (departure or arrival)
- `--time-buffer TEXT` - Time buffer around flight (e.g., "10m", "1h")
- `--limit INT` - Limit number of records

**Output Options:**
- `-o, --output PATH` - Save to CSV file
- `--cached/--no-cached` - Use cached results (default: cached)
- `--compress/--no-compress` - Compress cache (default: no-compress)

**Examples:**

Basic query:
```sh
ostk trajectory history --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" --icao24 485A32
```

With filters:
```sh
ostk trajectory history --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" \
    --icao24 485A32 \
    --callsign KLM123 \
    --departure-airport EHAM \
    --arrival-airport EGLL \
    -o flight.csv
```

Geographic bounds:
```sh
ostk trajectory history --start "2025-11-08 12:00:00" --stop "2025-11-08 15:00:00" \
    --bounds 4.5,52.0,5.0,52.5
```

## LLM Agent Commands

### Interactive Console

Launch an interactive agent for natural language queries:

```sh
ostk agent console
```

**Example queries:**
```
> Show me all flights from Amsterdam to London on Nov 8, 2025
> List aircraft over Paris between 13:00 and 15:00
> Get state vectors for ICAO24 485A32 on Nov 8
```

**Features:**
- Natural language query interpretation
- Generated query preview with confirmation
- Interactive save format and location selection
- Command history (use up/down arrows)

**Exit:** Type `exit`, `quit`, or press Ctrl+C

### Agent Configuration

**Set OpenAI API key:**
```sh
ostk agent config set-key
```

Prompts for your OpenAI API key and stores it securely in the config file.

**Clear command history:**
```sh
ostk agent clear-history
```

Removes saved command history from previous console sessions.

**Config locations:**
- Linux/macOS: `~/.config/ostk/settings.conf`
- Windows: `%LOCALAPPDATA%\ostk\settings.conf`
- History: Same directory as config + `agent_history` file

## Environment Variables

**OpenAI API Key (alternative to config file):**
```sh
export OPENAI_API_KEY=sk-...yourkey...
```

The agent will check environment variables first, then the config file.

## Tips

1. **Date formats:** Use ISO format with quotes: "YYYY-MM-DD HH:MM:SS"
2. **ICAO24 codes:** Can be uppercase or lowercase
3. **Caching:** Use `--no-cached` for fresh data, but note it's slower
4. **Agent usage:** Requires OpenAI API key (usage costs apply)
5. **Multiple values:** Use comma-separated lists for callsigns and serials
