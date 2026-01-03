//! Groq API client for LLM completions.

use super::{CompletionOptions, LlmError, Message};
use serde::{Deserialize, Serialize};

const GROQ_API_URL: &str = "https://api.groq.com/openai/v1/chat/completions";

/// Groq API client.
#[derive(Debug, Clone)]
pub struct GroqClient {
    api_key: String,
    model: String,
    client: reqwest::Client,
}

#[derive(Debug, Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    temperature: f32,
    max_tokens: u32,
}

#[derive(Debug, Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Debug, Deserialize)]
struct Choice {
    message: ResponseMessage,
}

#[derive(Debug, Deserialize)]
struct ResponseMessage {
    content: String,
}

#[derive(Debug, Deserialize)]
struct ErrorResponse {
    error: ErrorDetail,
}

#[derive(Debug, Deserialize)]
struct ErrorDetail {
    message: String,
}

impl GroqClient {
    /// Create a new Groq client.
    pub fn new(api_key: impl Into<String>, model: impl Into<String>) -> Self {
        Self {
            api_key: api_key.into(),
            model: model.into(),
            client: reqwest::Client::new(),
        }
    }

    /// Send a chat completion request.
    pub async fn complete(
        &self,
        messages: Vec<Message>,
        options: CompletionOptions,
    ) -> Result<String, LlmError> {
        let request = ChatRequest {
            model: self.model.clone(),
            messages,
            temperature: options.temperature,
            max_tokens: options.max_tokens,
        };

        let response = self
            .client
            .post(GROQ_API_URL)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let error: ErrorResponse = response.json().await?;
            return Err(LlmError::Api(error.error.message));
        }

        let chat_response: ChatResponse = response.json().await?;

        chat_response
            .choices
            .first()
            .map(|c| c.message.content.clone())
            .ok_or_else(|| LlmError::Api("No response from model".to_string()))
    }

    /// Get the model name.
    #[allow(dead_code)]  // Used by Agent::model()
    pub fn model(&self) -> &str {
        &self.model
    }
}

/// Fetch available models from Groq API.
pub async fn fetch_models(api_key: &str) -> Result<Vec<String>, LlmError> {
    let client = reqwest::Client::new();

    let response = client
        .get("https://api.groq.com/openai/v1/models")
        .header("Authorization", format!("Bearer {}", api_key))
        .send()
        .await?;

    if !response.status().is_success() {
        let error: ErrorResponse = response.json().await?;
        return Err(LlmError::Api(error.error.message));
    }

    #[derive(Deserialize)]
    struct ModelsResponse {
        data: Vec<ModelInfo>,
    }

    #[derive(Deserialize)]
    struct ModelInfo {
        id: String,
    }

    let models: ModelsResponse = response.json().await?;
    Ok(models.data.into_iter().map(|m| m.id).collect())
}
