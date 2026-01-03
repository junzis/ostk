//! Application state management for OSTK.

use opensky::{FlightData, QueryParams};
use std::sync::Arc;
use tokio::sync::Mutex;

/// Chat message structure.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
    #[serde(rename = "type")]
    pub msg_type: String,
}

impl ChatMessage {
    pub fn new(role: impl Into<String>, content: impl Into<String>, msg_type: impl Into<String>) -> Self {
        Self {
            role: role.into(),
            content: content.into(),
            msg_type: msg_type.into(),
        }
    }
}

/// Execution status during a query.
#[derive(Debug, Clone, serde::Serialize)]
pub struct ExecutionState {
    pub is_executing: bool,
    pub status: String,
    pub logs: Vec<String>,
    pub query_id: Option<String>,
    pub result: Option<ExecutionResult>,
}

impl Default for ExecutionState {
    fn default() -> Self {
        Self {
            is_executing: false,
            status: String::new(),
            logs: Vec::new(),
            query_id: None,
            result: None,
        }
    }
}

/// Result of query execution.
#[derive(Debug, Clone, serde::Serialize)]
#[serde(untagged)]
pub enum ExecutionResult {
    Success { success: bool, row_count: usize, columns: Vec<String> },
    NoData { error: String, row_count: usize },
    Error { error: String },
    Cancelled { cancelled: bool },
}

/// Application state shared across Tauri commands.
pub struct AppState {
    /// Current query parameters.
    pub query_params: QueryParams,

    /// Chat message history.
    pub messages: Vec<ChatMessage>,

    /// Last query result (DataFrame).
    pub last_result: Option<FlightData>,

    /// Current execution state.
    pub execution: ExecutionState,

    /// LLM agent status.
    pub agent_configured: bool,
    pub provider_name: String,
    pub model_name: String,
    pub error_message: Option<String>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            query_params: QueryParams::new(),
            messages: Vec::new(),
            last_result: None,
            execution: ExecutionState::default(),
            agent_configured: false,
            provider_name: String::new(),
            model_name: String::new(),
            error_message: None,
        }
    }
}

impl AppState {
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a chat message.
    pub fn add_message(&mut self, role: &str, content: &str, msg_type: &str) {
        self.messages.push(ChatMessage::new(role, content, msg_type));
    }

    /// Clear chat messages.
    pub fn clear_messages(&mut self) {
        self.messages.clear();
    }

    /// Add execution log entry.
    pub fn add_log(&mut self, message: &str) {
        let timestamp = chrono::Local::now().format("%H:%M:%S").to_string();
        self.execution.logs.push(format!("[{}] {}", timestamp, message));
    }

    /// Reset execution state for new query.
    pub fn reset_execution(&mut self) {
        self.execution = ExecutionState {
            is_executing: true,
            status: "Connecting to OpenSky...".to_string(),
            logs: Vec::new(),
            query_id: None,
            result: None,
        };
    }
}

/// Thread-safe state wrapper.
pub type SharedState = Arc<Mutex<AppState>>;

/// Create a new shared state instance.
pub fn new_shared_state() -> SharedState {
    Arc::new(Mutex::new(AppState::new()))
}
