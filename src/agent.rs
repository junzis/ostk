//! LLM-powered agent for parsing natural language queries into QueryParams.

use crate::llm::{CompletionOptions, GroqClient, LlmError, Message};
use opensky::{Bounds, QueryParams};
use regex::Regex;
use serde::{Deserialize, Serialize};

const PROMPT_TEMPLATE: &str = include_str!("../resources/agent.md");

/// Agent for parsing natural language queries.
pub struct Agent {
    client: GroqClient,
}

/// The type of query to execute.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum QueryType {
    /// Flight list (departures/arrivals with times and airports)
    #[default]
    Flights,
    /// State vector time series (position, altitude, speed over time)
    Trajectory,
    /// Raw ADS-B/Mode S messages for decoding
    Rawdata,
}

impl std::fmt::Display for QueryType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            QueryType::Trajectory => write!(f, "trajectory"),
            QueryType::Flights => write!(f, "flights"),
            QueryType::Rawdata => write!(f, "rawdata"),
        }
    }
}

/// Result of parsing a natural language query.
#[derive(Debug, Clone)]
pub struct ParsedQuery {
    /// The type of query to execute
    pub query_type: QueryType,
    /// User-friendly hint describing what the query will return
    pub hint: String,
    /// The extracted query parameters
    pub params: QueryParams,
}

/// Parsed parameters from LLM response.
#[derive(Debug, Deserialize)]
#[allow(dead_code)]  // Some fields reserved for future use
struct ParsedParams {
    status: String,
    #[serde(default)]
    reason: Option<String>,
    #[serde(default)]
    query_type: Option<QueryType>,
    #[serde(default)]
    hint: Option<String>,
    #[serde(default)]
    icao24: Option<String>,
    #[serde(default)]
    start: Option<String>,
    #[serde(default)]
    stop: Option<String>,
    #[serde(default)]
    callsign: Option<String>,
    #[serde(default)]
    departure_airport: Option<String>,
    #[serde(default)]
    arrival_airport: Option<String>,
    #[serde(default)]
    airport: Option<String>,
    #[serde(default)]
    limit: Option<u32>,
    #[serde(default)]
    bounds: Option<Vec<f64>>,
    #[serde(default)]
    time_buffer: Option<i64>,
}

impl Agent {
    /// Create a new agent with the given Groq client.
    pub fn new(client: GroqClient) -> Self {
        Self { client }
    }

    /// Parse a natural language query into a ParsedQuery.
    ///
    /// Returns the parsed query with type, hint, and parameters,
    /// along with the raw LLM response for debugging.
    pub async fn parse_query(&self, user_query: &str) -> Result<(ParsedQuery, String), LlmError> {
        // Build prompt with current LOCAL time injected
        // Using local time so "yesterday" matches user expectations
        let current_local = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let prompt = PROMPT_TEMPLATE
            .replace("{current_time}", &current_local)
            .replace("{user_query}", user_query);

        // Call LLM
        let messages = vec![
            Message::system("You are a helpful assistant."),
            Message::user(prompt),
        ];

        let response = self
            .client
            .complete(messages, CompletionOptions::default())
            .await?;

        // Extract JSON from response
        let parsed_query = self.extract_params(&response)?;

        Ok((parsed_query, response))
    }

    /// Extract ParsedQuery from LLM response text.
    fn extract_params(&self, response: &str) -> Result<ParsedQuery, LlmError> {
        // Try to find JSON object in response
        let re = Regex::new(r"\{[^{}]*\}").unwrap();

        let json_str = re
            .find(response)
            .map(|m| m.as_str())
            .ok_or_else(|| LlmError::Parse("No JSON object found in response".to_string()))?;

        // Parse JSON
        let parsed: ParsedParams = serde_json::from_str(json_str)
            .map_err(|e| LlmError::Parse(format!("JSON parse error: {}", e)))?;

        // Check if query was unclear
        if parsed.status == "unclear" {
            let reason = parsed.reason.unwrap_or_else(|| "Query not clear".to_string());
            return Err(LlmError::Parse(format!("Query unclear: {}", reason)));
        }

        // Extract query type (default to Trajectory for backwards compatibility)
        let query_type = parsed.query_type.unwrap_or_default();

        // Extract hint (provide default based on query type)
        let hint = parsed.hint.unwrap_or_else(|| match query_type {
            QueryType::Trajectory => "Download trajectory data".to_string(),
            QueryType::Flights => "Download flight list".to_string(),
            QueryType::Rawdata => "Download raw ADS-B messages".to_string(),
        });

        // Convert to QueryParams
        let mut params = QueryParams::new();
        params.start = parsed.start;
        params.stop = parsed.stop;
        params.icao24 = parsed.icao24;
        params.callsign = parsed.callsign;
        params.departure_airport = parsed.departure_airport;
        params.arrival_airport = parsed.arrival_airport;
        params.airport = parsed.airport;
        params.limit = parsed.limit;

        // Convert bounds array [west, south, east, north] to Bounds struct
        if let Some(b) = parsed.bounds {
            if b.len() == 4 {
                params.bounds = Some(Bounds::new(b[0], b[1], b[2], b[3]));
            }
        }

        Ok(ParsedQuery {
            query_type,
            hint,
            params,
        })
    }

    /// Get the model name being used.
    #[allow(dead_code)]  // Useful for debugging
    pub fn model(&self) -> &str {
        self.client.model()
    }
}
