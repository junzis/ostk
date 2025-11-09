# Examples and Use Cases

## Basic Trajectory Reconstruction

### Simple Query

```python
from ostk import rebuild

# Reconstruct trajectory for a single flight
df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00"
)

print(df.head())
```

Output:
```
                 time  icao24        lat        lon  baroaltitude  velocity  heading  vertrate
0 2025-11-08 12:00:15  485a32  52.308926   4.763832       30.48      140.5    245.2      0.0
1 2025-11-08 12:00:18  485a32  52.308123   4.761945       45.72      145.2    245.8      5.1
...
```

### Save to File

```python
from ostk import rebuild

df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00"
)

if df is not None:
    df.to_csv("flight_485A32.csv", index=False)
    print(f"Saved {len(df)} data points")
else:
    print("No data available")
```

## Comparison: rebuild() vs history()

### Accuracy Comparison

```python
from ostk import rebuild
from pyopensky.trino import Trino

trino = Trino()

# Method 1: Enhanced reconstruction with OSTK
traj_rebuild = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 13:00:00"
)

# Method 2: Standard history query
traj_history = trino.history(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 13:00:00"
)

print(f"Rebuild points: {len(traj_rebuild)}")
print(f"History points: {len(traj_history)}")

# Compare altitude profiles
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

ax1.plot(traj_history.time, traj_history.baroaltitude, 'o-', label='history()', alpha=0.6)
ax1.set_ylabel('Altitude (m)')
ax1.legend()
ax1.grid(True)

ax2.plot(traj_rebuild.time, traj_rebuild.baroaltitude, 'o-', label='rebuild()', color='orange', alpha=0.6)
ax2.set_ylabel('Altitude (m)')
ax2.set_xlabel('Time')
ax2.legend()
ax2.grid(True)

plt.tight_layout()
plt.savefig('comparison.png')
```

### When to Use Each Method

**Use `rebuild()` when:**

```python
# 1. You need maximum accuracy for a single aircraft
df = rebuild(icao24="485A32", start="...", stop="...")

# 2. You want fewer outliers and position jumps
# The enhanced CPR decoding reduces errors significantly

# 3. You're analyzing detailed flight characteristics
# Better altitude and position accuracy for analysis
```

**Use `history()` when:**

```python
from pyopensky.trino import Trino
trino = Trino()

# 1. You need fast queries for multiple aircraft
df = trino.history(
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00",
    bounds=(4.0, 52.0, 5.0, 53.0)  # All aircraft in area
)

# 2. You need complex filtering
df = trino.history(
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00",
    departure_airport="EHAM",
    arrival_airport="EGLL",
    callsign="KLM%"
)

# 3. Speed is more important than perfect accuracy
```

## Working with Results

### Filter and Clean Data

```python
from ostk import rebuild

df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00"
)

# Filter by altitude
high_altitude = df[df['baroaltitude'] > 10000]

# Filter by speed
cruise_phase = df[df['velocity'] > 200]

# Remove ground data (if any)
airborne = df[df['baroaltitude'] > 100]

# Calculate statistics
print(f"Max altitude: {df['baroaltitude'].max():.0f} m")
print(f"Max speed: {df['velocity'].max():.1f} m/s")
print(f"Flight duration: {(df['time'].max() - df['time'].min()).total_seconds() / 60:.1f} min")
```

### Visualize Trajectory

```python
from ostk import rebuild
import matplotlib.pyplot as plt

df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00"
)

# Create 2D trajectory plot
fig, ax = plt.subplots(figsize=(10, 8))
scatter = ax.scatter(
    df['lon'], 
    df['lat'], 
    c=df['baroaltitude'],
    cmap='viridis',
    s=20
)
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
ax.set_title('Flight Trajectory')
plt.colorbar(scatter, ax=ax, label='Altitude (m)')
plt.tight_layout()
plt.savefig('trajectory_2d.png')
```

### Convert Units

```python
from ostk import rebuild

df = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00"
)

# Convert to common aviation units
df['altitude_ft'] = df['baroaltitude'] * 3.28084  # meters to feet
df['speed_kts'] = df['velocity'] * 1.94384  # m/s to knots
df['vspeed_fpm'] = df['vertrate'] * 196.85  # m/s to feet per minute

print(df[['time', 'altitude_ft', 'speed_kts', 'vspeed_fpm']].head())
```

## LLM Agent Examples

### Basic Agent Usage

```python
from ostk import Agent

# Initialize agent
agent = Agent()

# Parse natural language query
params = agent.parse_query(
    "Show me all flights from Amsterdam to London on Nov 8, 2025"
)

# Preview generated query
print(agent.build_history_call(params))

# Execute query
df = agent.execute_query(params)

# Save results
output_path = agent.save_result(df, fmt="csv", output="amsterdam_london.csv")
print(f"Saved {len(df)} flights to {output_path}")
```

### Complex Queries

```python
from ostk import Agent

agent = Agent()

# Query with time range and location
params = agent.parse_query(
    "Aircraft over Paris between 13:00 and 15:00 on November 8, 2025"
)
df = agent.execute_query(params)

# Query specific aircraft
params = agent.parse_query(
    "Get trajectory for ICAO24 485A32 on Nov 8, 2025"
)
df = agent.execute_query(params)

# Query with callsign
params = agent.parse_query(
    "Show me all KLM flights on November 8, 2025 between 10:00 and 12:00"
)
df = agent.execute_query(params)
```

### Using Different Models

```python
from ostk import Agent

# Use GPT-4 for better accuracy (more expensive)
agent = Agent(llm_model="gpt-4")

# Use GPT-4o-mini for faster, cheaper queries (default)
agent = Agent(llm_model="gpt-4o-mini")
```

## Batch Processing

### Process Multiple Aircraft

```python
from ostk import rebuild
import pandas as pd

aircraft_list = ["485A32", "400A0E", "3C6481"]
start = "2025-11-08 12:00:00"
stop = "2025-11-08 15:00:00"

all_trajectories = []

for icao24 in aircraft_list:
    print(f"Processing {icao24}...")
    df = rebuild(icao24=icao24, start=start, stop=stop)
    if df is not None:
        all_trajectories.append(df)
    else:
        print(f"  No data for {icao24}")

# Combine all trajectories
combined = pd.concat(all_trajectories, ignore_index=True)
combined.to_csv("all_flights.csv", index=False)
print(f"Total: {len(combined)} data points from {len(all_trajectories)} aircraft")
```

### Daily Processing

```python
from ostk import rebuild
from datetime import datetime, timedelta

icao24 = "485A32"
start_date = datetime(2025, 11, 8)

# Process 7 days
for day in range(7):
    current_day = start_date + timedelta(days=day)
    start = current_day.strftime("%Y-%m-%d 00:00:00")
    stop = current_day.strftime("%Y-%m-%d 23:59:59")
    
    print(f"Processing {current_day.date()}...")
    df = rebuild(icao24=icao24, start=start, stop=stop)
    
    if df is not None:
        filename = f"flight_{icao24}_{current_day.date()}.csv"
        df.to_csv(filename, index=False)
        print(f"  Saved {len(df)} points to {filename}")
    else:
        print(f"  No data for this day")
```

## Advanced Usage

### Custom Trino Configuration

```python
from ostk import rebuild
from pyopensky.trino import Trino

# Create custom Trino instance with specific settings
trino = Trino()

# Use it for multiple queries (reuses connection)
df1 = rebuild(icao24="485A32", start="...", stop="...", trino=trino)
df2 = rebuild(icao24="400A0E", start="...", stop="...", trino=trino)
df3 = rebuild(icao24="3C6481", start="...", stop="...", trino=trino)
```

### Error Handling

```python
from ostk import rebuild

def safe_rebuild(icao24, start, stop, max_retries=3):
    """Rebuild with retry logic."""
    for attempt in range(max_retries):
        try:
            df = rebuild(icao24=icao24, start=start, stop=stop)
            if df is not None:
                return df
            else:
                print(f"No data available for {icao24}")
                return None
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print(f"Failed after {max_retries} attempts")
                return None

# Use the safe version
df = safe_rebuild("485A32", "2025-11-08 12:00:00", "2025-11-08 15:00:00")
```

## CLI Examples

See [CLI Reference](cli.md) for comprehensive command-line examples.

Quick reference:

```sh
# Basic reconstruction
ostk trajectory rebuild 485A32 "2025-11-08 12:00:00" "2025-11-08 15:00:00"

# Save to file
ostk trajectory rebuild 485A32 "2025-11-08 12:00:00" "2025-11-08 15:00:00" -o output.csv

# Use history for fast queries
ostk trajectory history 485A32 "2025-11-08 12:00:00" "2025-11-08 15:00:00" --departure-airport EHAM

# Use LLM agent
ostk agent console
```
