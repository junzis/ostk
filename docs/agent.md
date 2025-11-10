# LLM Agent Guide

## Overview

OSTK includes an LLM-powered agent that converts natural language queries into OpenSky Trino database queries. This allows you to query flight data without knowing the exact API parameters.

## Setup

### OpenAI API Key Required

The agent uses OpenAI's GPT models and requires an API key. You have two options:

**Option 1: Environment Variable (Recommended)**

```sh
# Linux/macOS
export OPENAI_API_KEY=sk-...yourkey...

# Windows (Command Prompt)
set OPENAI_API_KEY=sk-...yourkey...

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-...yourkey..."
```

**Option 2: Config File**

```sh
ostk agent config set-key
```

This stores your key in:
- Linux/macOS: `~/.config/ostk/settings.conf`
- Windows: `%LOCALAPPDATA%\ostk\settings.conf`

The config file format:
```ini
[llm]
openai_api_key=sk-...yourkey...
```

### Important Notes

- Never hard-code your API key in source code
- Keep your API key secure
- OpenAI API usage incurs costs based on tokens used
- The agent defaults to `gpt-4o-mini` for cost efficiency

## Interactive Console

The recommended way to use the agent is through the interactive console:

```sh
ostk agent start
```

### Console Features

1. **Natural Language Queries**: Type your questions in plain English
2. **LLM Response Display**: See the raw response from the LLM (useful for debugging)
3. **Query Preview**: See the generated Python code before execution
4. **Confirmation**: Approve or reject the generated query
5. **Save Options**: Choose CSV or Parquet format
6. **Command History**: Use up/down arrows to recall previous queries
7. **Rich Output**: Color-coded interface with progress indicators

### Example Session

```
✨ OSTK LLM Agent

Tell me what OpenSky history data you want to download.
Example: State vectors from Amsterdam Schiphol to London Heatharow on 08/11/2025 between 13:00 and 15:00
Type exit or quit to leave

❯ Show me all flights from Amsterdam to London on Nov 8, 2025

🤖 LLM Response
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{'icao24': None, 'start': '2025-11-08 00:00:00', 'stop': '2025-11-08 23:59:59', 
'bounds': None, 'callsign': None, 'departure_airport': 'EHAM', 
'arrival_airport': 'EGLL', 'airport': None, 'time_buffer': None, 'limit': None, 
'selected_columns': ("time", "icao24", "lat", "lon", "velocity", "heading", 
"vertrate", "callsign", "onground", "squawk", "baroaltitude", "geoaltitude", "hour")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 Generated Query
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
trino.history(start='2025-11-08 00:00:00', stop='2025-11-08 23:59:59', 
              departure_airport='EHAM', arrival_airport='EGLL')
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proceed with this query? [Y/n]: y

Save format (csv, parquet) [csv]: csv

Output folder (leave blank for current folder): 

⠋ Fetching data from OpenSky...

Success!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Saved 1,234 rows
📁 state_vectors_20251108_140532.csv
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❯ exit
👋 Goodbye!
```

### Natural Language Query Examples

**Route-based queries:**
```
> Flights from Amsterdam to London on Nov 8, 2025
> Show me aircraft from EHAM to EGLL between 13:00 and 15:00
> All flights departing from Paris Charles de Gaulle today
```

**Location-based queries:**
```
> Aircraft over Paris between 10:00 and 12:00
> Show me flights in the Netherlands on Nov 8
> List aircraft near London Heathrow
```

**Aircraft-specific queries:**
```
> Trajectory for ICAO24 485A32 on Nov 8
> Show me flight data for aircraft 400A0E between 12:00 and 15:00
> Get position data for transponder code 3C6481
```

**Callsign queries:**
```
> All KLM flights on Nov 8, 2025
> Show me Lufthansa aircraft between 10:00 and 12:00
> Find flights with callsign BAW123
```

**Time-based queries:**
```
> Flights on November 8, 2025 between 13:00 and 15:00
> Aircraft data from 10am to 2pm on Nov 8
> Show me data for yesterday between noon and 3pm
```

## Python API Usage

You can also use the agent programmatically:

### Basic Usage

```python
from ostk import Agent

# Initialize agent
agent = Agent()

# Parse query
params = agent.parse_query(
    "Show me all flights from Amsterdam to London on Nov 8, 2025"
)

# Review generated query (optional)
print(agent.build_history_call(params))

# Execute query
df = agent.execute_query(params)

# Save results
output_path = agent.save_result(df, fmt="csv")
print(f"Saved to {output_path}")
```

### Custom Model Selection

```python
from ostk import Agent

# Use GPT-4 for better accuracy (higher cost)
agent = Agent(llm_model="gpt-4")

# Use GPT-4o-mini for speed and lower cost (default)
agent = Agent(llm_model="gpt-4o-mini")

# Use Ollama with a local model
agent = Agent(provider="ollama", model="llama3:8b")

# Use Groq for fast inference
agent = Agent(provider="groq", model="llama-3.1-70b-versatile")
```

### Model Recommendations by Provider

**OpenAI:**
- `gpt-4o-mini` (default): Fast and cost-effective, good for most queries
- `gpt-4o`: More capable, better for complex queries
- `gpt-4`: Most capable, highest cost

**Ollama (local models):**
- `gemma3:12b`: **Recommended** - Excellent for structured output
- `llama3:8b` or larger: Good alternative
- **Avoid reasoning models** like `qwen3` - they output thought process instead of just the dictionary
- Smaller models (<7B parameters) may struggle with structured output
- Test your model first with simple queries

**Groq:**
- `llama-3.1-70b-versatile`: Fast and capable
- `mixtral-8x7b-32768`: Good alternative

### Error Handling

```python
from ostk import Agent

agent = Agent()

try:
    params = agent.parse_query("Flights from Amsterdam to London on Nov 8")
    df = agent.execute_query(params)
    
    if df is None or df.empty:
        print("No data found")
    else:
        print(f"Found {len(df)} records")
        agent.save_result(df, fmt="csv", output="results.csv")
        
except RuntimeError as e:
    print(f"API key error: {e}")
except ValueError as e:
    print(f"Query parsing error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Batch Processing

```python
from ostk import Agent

agent = Agent()

queries = [
    "Flights from Amsterdam to London on Nov 8",
    "Aircraft over Paris between 13:00 and 15:00 on Nov 8",
    "KLM flights on November 8, 2025"
]

for i, query in enumerate(queries):
    print(f"Processing query {i+1}: {query}")
    
    params = agent.parse_query(query)
    df = agent.execute_query(params)
    
    if df is not None and not df.empty:
        filename = f"query_{i+1}.csv"
        agent.save_result(df, fmt="csv", output=filename)
        print(f"  Saved {len(df)} records to {filename}")
    else:
        print(f"  No data found")
```

## How It Works

The agent follows these steps:

1. **Parse Query**: Uses LLM to extract parameters from natural language
   - Converts dates/times to ISO format
   - Identifies airports, routes, aircraft
   - Determines time ranges and filters

2. **Generate Query**: Builds pyopensky `history()` function call
   - Maps parameters to Trino API
   - Adds required column selections
   - Validates parameter combinations

3. **Execute Query**: Runs the query against OpenSky database
   - Uses pyopensky Trino interface
   - Handles caching automatically
   - Returns structured DataFrame

4. **Save Results**: Exports data to file
   - Supports CSV and Parquet formats
   - Auto-generates timestamped filenames
   - Preserves all data columns

## Supported Parameters

The agent can extract and use these pyopensky `history()` parameters:

- `icao24` - Aircraft transponder code
- `start` - Start time (UTC)
- `stop` - End time (UTC)
- `callsign` - Aircraft callsign
- `departure_airport` - ICAO airport code
- `arrival_airport` - ICAO airport code
- `airport` - Either departure or arrival
- `bounds` - Geographic bounding box (west, south, east, north)
- `time_buffer` - Time buffer around flight
- `limit` - Maximum number of records

## Limitations

1. **Query Complexity**: The LLM may struggle with very complex or ambiguous queries
2. **Airport Codes**: Must use ICAO codes (EHAM, EGLL) not IATA (AMS, LHR)
3. **Time Zones**: All times are interpreted as UTC
4. **API Costs**: Each query uses OpenAI API tokens (typically 100-400 tokens)
5. **Database Limits**: Subject to OpenSky Trino rate limits and data availability

## Tips for Better Queries

1. **Be Specific**: Include dates, times, and locations
   - Good: "Flights from EHAM to EGLL on Nov 8, 2025 between 13:00 and 15:00"
   - Poor: "Some flights"

2. **Use ICAO Codes**: When known
   - Good: "Flights from EHAM"
   - Also works: "Flights from Amsterdam Schiphol"

3. **Specify Time Ranges**: Always include start and end times
   - Good: "on Nov 8, 2025 between 10:00 and 12:00"
   - Okay: "on Nov 8, 2025" (assumes full day)

4. **Review Before Executing**: Check the generated query in the console
   - Verify airports, times, and filters are correct
   - Cancel and rephrase if needed

5. **Use UTC Times**: All times are UTC
   - Good: "on Nov 8, 2025 13:00 UTC"
   - Specify timezone if different: "13:00 CET" (agent will try to convert)

## Configuration Management

### Set API Key

```sh
ostk agent config set-key
```

### View Config Location

The config file is stored at:
- Linux/macOS: `~/.config/ostk/settings.conf`
- Windows: `%LOCALAPPDATA%\ostk\settings.conf`

### Clear Command History

```sh
ostk agent clear-history
```

Removes saved console command history (separate from query results).

## Cost Estimation

Typical OpenAI API costs (using gpt-4o-mini):

- Simple query: ~100-200 tokens (~$0.00001-0.00002)
- Complex query: ~200-400 tokens (~$0.00002-0.00004)
- Console session (10 queries): ~$0.0002-0.0004

Using gpt-4 is more expensive:
- Simple query: ~$0.0001-0.0002
- Complex query: ~$0.0002-0.0004

Costs are minimal for individual use but can add up with heavy automation.

## Troubleshooting

### "OpenAI API key not found"

Set your API key via environment variable or config:
```sh
export OPENAI_API_KEY=sk-...
# or
ostk agent config set-key
```

### "Could not parse parameters from LLM response"

The LLM couldn't understand your query or didn't return the expected format. 

**Debug the issue:**
- Check the "🤖 LLM Response" panel in the console to see exactly what the model returned
- Look for extra text, markdown formatting, or explanations around the dictionary
- The response should be a plain Python dictionary, nothing else

**Then try:**
- Being more specific about dates/times
- Using ICAO airport codes
- Simplifying the query
- Checking for typos

**For smaller or local models (like Ollama):**

Smaller models may struggle with the prompt format. The LLM must return ONLY a Python dictionary with no extra text. If you're using a smaller model, consider:
- Using a more capable model (e.g., llama3:8b or larger)
- Checking that your model supports function calling or structured outputs
- Trying a different provider (OpenAI or Groq)

The expected output format is a dictionary like:
```python
{'icao24': None, 'start': '2025-11-08 00:00:00', 'stop': '2025-11-08 23:59:59', 'bounds': None, 'callsign': None, 'departure_airport': 'EHAM', 'arrival_airport': 'EGLL', 'airport': None, 'time_buffer': None, 'limit': None, 'selected_columns': ("time", "icao24", "lat", "lon", "velocity", "heading", "vertrate", "callsign", "onground", "squawk", "baroaltitude", "geoaltitude", "hour")}
```

### "No data found for the given parameters"

The query was valid but returned no results. This could mean:
- No flights match your criteria
- Time range is outside available data
- Airport codes are incorrect
- Aircraft wasn't tracked during that period

### Rate Limiting

If you get Trino rate limit errors:
- Add delays between queries
- Use caching (enabled by default)
- Reduce query frequency

### Ollama Model Issues

If using Ollama with smaller models:

1. **Verify model is running**: `ollama list` to see installed models
2. **Test model capability**: Try a simple query first
3. **Use larger models**: Models under 7B parameters often fail
4. **Check output format**: Smaller models may add explanatory text instead of just the dictionary
5. **Avoid reasoning models**: Models like `qwen3` output their thinking process, not structured output
   - **Recommended**: Use `gemma3:12b` or `llama3:8b+`
   - **Not recommended**: `qwen3:*`, `deepseek-r1:*`, or other reasoning-focused models

**Recommended Ollama models:**
```sh
# Best for structured output (recommended)
ollama pull gemma3:12b

# Good alternative
ollama pull llama3:8b

# Or use an even larger model
ollama pull llama3:70b

# AVOID reasoning models like qwen3 - they output thinking process
# ollama pull qwen3:4b  # ❌ NOT RECOMMENDED
```

**Configure for Ollama:**
```ini
# ~/.config/ostk/settings.conf
[llm]
provider=ollama
ollama_model=gemma3:12b
ollama_base_url=http://localhost:11434
```

## See Also

- [CLI Reference](cli.md) - Command-line usage
- [API Documentation](api.md) - Python API details
- [Examples](examples.md) - More usage examples
