# Python API Reference

## Installation

```sh
pip install ostk
```

## Core Functions

### rebuild()

Reconstruct flight trajectory from raw ADS-B messages with enhanced CPR decoding.

```python
from ostk import rebuild

df = rebuild(
    icao24: str,
    start: timelike,
    stop: timelike,
    trino: Trino | None = None,
    cached: bool = True,
    compress: bool = False
) -> pd.DataFrame | None
```

**Parameters:**

- `icao24` (str) - Aircraft transponder code (24-bit hex string, e.g., "485A32")
- `start` (str | datetime | timestamp) - Start time in UTC
  - String: ISO format "YYYY-MM-DD HH:MM:SS"
  - datetime: Python datetime or pandas Timestamp
  - int/float: Unix timestamp
- `stop` (str | datetime | timestamp) - End time in UTC (same formats as start)
- `trino` (Trino, optional) - pyopensky Trino instance. Default: creates new instance
- `cached` (bool) - Use cached results if available. Default: True
- `compress` (bool) - Compress cache files. Default: False

**Returns:**

- `pd.DataFrame` - Trajectory data with columns:
  - `time` (datetime) - Timestamp in UTC
  - `icao24` (str) - Aircraft transponder code
  - `lat` (float) - Latitude in degrees
  - `lon` (float) - Longitude in degrees
  - `baroaltitude` (float) - Barometric altitude in meters
  - `velocity` (float) - Ground speed in m/s
  - `heading` (float) - Track angle in degrees
  - `vertrate` (float) - Vertical rate in m/s
- `None` - If no data available

**Example:**

```python
from ostk import rebuild

# Basic usage
df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00"
)

# With custom Trino instance
from pyopensky.trino import Trino
trino = Trino()

df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00",
    trino=trino,
    cached=False  # Force fresh query
)

# Save to file
if df is not None:
    df.to_csv("trajectory.csv", index=False)
```

**Notes:**

- More accurate than `pyopensky.trino.history()` due to enhanced CPR decoding
- Slower than `history()` due to message decoding overhead
- Only supports filtering by icao24 and time range
- Requires valid OpenSky Trino credentials

## LLM Agent

### Agent

LLM-powered agent for natural language OpenSky queries.

```python
from ostk import Agent

agent = Agent(llm_model: str = "gpt-4o-mini")
```

**Parameters:**

- `llm_model` (str) - OpenAI model to use. Default: "gpt-4o-mini"

**Setup:**

Requires OpenAI API key via environment variable or config file:

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-...yourkey..."
```

Or use CLI to set in config:
```sh
ostk agent config set-key
```

### Methods

#### parse_query()

Parse natural language query into pyopensky history() parameters.

```python
params = agent.parse_query(user_query: str) -> dict
```

**Example:**

```python
params = agent.parse_query(
    "Show me flights from Amsterdam to London on Nov 8, 2025"
)
# Returns: {
#     'start': '2025-11-08 00:00:00',
#     'stop': '2025-11-08 23:59:59',
#     'departure_airport': 'EHAM',
#     'arrival_airport': 'EGLL',
#     ...
# }
```

#### execute_query()

Execute query with parsed parameters.

```python
df = agent.execute_query(params: dict) -> pd.DataFrame
```

**Example:**

```python
params = agent.parse_query("Flights for ICAO24 485A32 on Nov 8")
df = agent.execute_query(params)
```

#### save_result()

Save DataFrame to file.

```python
path = agent.save_result(
    df: pd.DataFrame,
    fmt: str = "csv",
    output: str | None = None
) -> str
```

**Parameters:**

- `df` - DataFrame to save
- `fmt` - Format: "csv" or "parquet"
- `output` - Output path. Default: auto-generated timestamp filename

**Returns:** Output file path

#### build_history_call()

Generate Python code string for the query (for preview/logging).

```python
code = agent.build_history_call(params: dict) -> str
```

**Example:**

```python
params = {'icao24': '485A32', 'start': '2025-11-08 12:00:00', ...}
code = agent.build_history_call(params)
print(code)
# Output: trino.history(icao24='485A32', start='2025-11-08 12:00:00', ...)
```

### Complete Example

```python
from ostk import Agent

# Initialize agent
agent = Agent()

# Parse natural language query
params = agent.parse_query(
    "Show me flights from Amsterdam to London on Nov 8, 2025 between 13:00 and 15:00"
)

# Review generated query
print(agent.build_history_call(params))

# Execute query
df = agent.execute_query(params)

# Save results
output_path = agent.save_result(df, fmt="csv")
print(f"Saved to {output_path}")
```

## Error Handling

```python
from ostk import rebuild

try:
    df = rebuild(
        icao24="485A32",
        start="2025-11-08 12:00:00",
        stop="2025-11-08 15:00:00"
    )
    
    if df is None:
        print("No data available for this query")
    else:
        print(f"Retrieved {len(df)} data points")
        
except Exception as e:
    print(f"Error: {e}")
```

## Type Hints

```python
from typing import Union
from datetime import datetime
import pandas as pd
from pyopensky.trino import Trino

# timelike accepts multiple types
timelike = Union[str, datetime, pd.Timestamp, int, float]
```

## Performance Tips

1. **Use caching:** Default `cached=True` speeds up repeated queries
2. **Reuse Trino instance:** Pass same `trino` object for multiple queries
3. **Compress for large datasets:** Set `compress=True` to reduce disk space
4. **Choose right method:**
   - Use `rebuild()` for single aircraft, maximum accuracy
   - Use `pyopensky.trino.history()` for bulk queries or complex filters

## See Also

- [CLI Reference](cli.md) - Command-line interface
- [Examples](examples.md) - Usage examples
- [pyopensky documentation](https://open-aviation.github.io/pyopensky/)
