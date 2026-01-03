//! LLM-powered agent for parsing natural language queries into QueryParams.

use crate::llm::{CompletionOptions, GroqClient, LlmError, Message};
use opensky::QueryParams;
use regex::Regex;
use serde::Deserialize;

const PROMPT_TEMPLATE: &str = include_str!("../resources/agent.md");

/// Agent for parsing natural language queries.
pub struct Agent {
    client: GroqClient,
}

/// Parsed parameters from LLM response.
#[derive(Debug, Deserialize)]
#[allow(dead_code)]  // Some fields reserved for future use
struct ParsedParams {
    status: String,
    #[serde(default)]
    reason: Option<String>,
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

    /// Parse a natural language query into QueryParams.
    pub async fn parse_query(&self, user_query: &str) -> Result<(QueryParams, String), LlmError> {
        // Build prompt with current UTC time injected
        let current_utc = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let prompt = PROMPT_TEMPLATE
            .replace("{current_utc_time}", &current_utc)
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
        let params = self.extract_params(&response)?;

        Ok((params, response))
    }

    /// Extract QueryParams from LLM response text.
    fn extract_params(&self, response: &str) -> Result<QueryParams, LlmError> {
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

        Ok(params)
    }

    /// Get the model name being used.
    #[allow(dead_code)]  // Useful for debugging
    pub fn model(&self) -> &str {
        self.client.model()
    }
}
