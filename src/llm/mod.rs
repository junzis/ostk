//! LLM provider integrations for OSTK.

mod groq;

pub use groq::{fetch_models, GroqClient};

use serde::{Deserialize, Serialize};

/// Chat message for LLM API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

impl Message {
    pub fn system(content: impl Into<String>) -> Self {
        Self {
            role: "system".to_string(),
            content: content.into(),
        }
    }

    pub fn user(content: impl Into<String>) -> Self {
        Self {
            role: "user".to_string(),
            content: content.into(),
        }
    }
}

/// LLM completion options.
#[derive(Debug, Clone)]
pub struct CompletionOptions {
    pub temperature: f32,
    pub max_tokens: u32,
}

impl Default for CompletionOptions {
    fn default() -> Self {
        Self {
            temperature: 0.2,
            max_tokens: 1000,
        }
    }
}

/// Error type for LLM operations.
#[derive(Debug, thiserror::Error)]
#[allow(dead_code)]  // Some variants reserved for future use
pub enum LlmError {
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("API error: {0}")]
    Api(String),

    #[error("Not configured: {0}")]
    NotConfigured(String),

    #[error("Parse error: {0}")]
    Parse(String),
}
