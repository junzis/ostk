//! Tauri commands for OSTK - exposed to JavaScript frontend.

use crate::agent::{Agent, QueryType};
use crate::config::LlmConfig;
use crate::llm::GroqClient;
use crate::state::{ExecutionResult, SharedState};
use chrono::{Datelike, Duration, Local, Timelike};
use opensky::{build_query_preview_method, build_history_query, build_flightlist_query, build_rawdata_query, Bounds, QueryParams, RawTable, Trino};
use serde_json::{json, Value};
use tauri::State;

// ========== Query Parameter Commands ==========

#[tauri::command]
pub async fn get_query_params(state: State<'_, SharedState>) -> Result<Value, String> {
    let state = state.lock().await;
    Ok(json!({
        "icao24": state.query_params.icao24,
        "start": state.query_params.start,
        "stop": state.query_params.stop,
        "callsign": state.query_params.callsign,
        "departure_airport": state.query_params.departure_airport,
        "arrival_airport": state.query_params.arrival_airport,
        "airport": state.query_params.airport,
        "limit": state.query_params.limit,
        "bounds": state.query_params.bounds,
    }))
}

#[tauri::command]
pub async fn set_query_param(
    state: State<'_, SharedState>,
    key: String,
    value: Value,
) -> Result<Value, String> {
    let mut app_state = state.lock().await;

    match key.as_str() {
        "icao24" => app_state.query_params.icao24 = value.as_str().map(String::from),
        "start" => app_state.query_params.start = value.as_str().map(String::from),
        "stop" => app_state.query_params.stop = value.as_str().map(String::from),
        "callsign" => app_state.query_params.callsign = value.as_str().map(String::from),
        "departure_airport" => app_state.query_params.departure_airport = value.as_str().map(String::from),
        "arrival_airport" => app_state.query_params.arrival_airport = value.as_str().map(String::from),
        "airport" => app_state.query_params.airport = value.as_str().map(String::from),
        "limit" => app_state.query_params.limit = value.as_u64().map(|v| v as u32),
        "bounds" => {
            // Bounds is sent as [west, south, east, north] array
            if value.is_null() {
                app_state.query_params.bounds = None;
            } else if let Some(arr) = value.as_array() {
                if arr.len() == 4 {
                    let west = arr[0].as_f64().unwrap_or(0.0);
                    let south = arr[1].as_f64().unwrap_or(0.0);
                    let east = arr[2].as_f64().unwrap_or(0.0);
                    let north = arr[3].as_f64().unwrap_or(0.0);
                    app_state.query_params.bounds = Some(Bounds::new(west, south, east, north));
                }
            }
        }
        _ => return Err(format!("Unknown parameter: {}", key)),
    }

    // Return current params
    Ok(json!({
        "icao24": app_state.query_params.icao24,
        "start": app_state.query_params.start,
        "stop": app_state.query_params.stop,
        "callsign": app_state.query_params.callsign,
        "departure_airport": app_state.query_params.departure_airport,
        "arrival_airport": app_state.query_params.arrival_airport,
        "airport": app_state.query_params.airport,
        "limit": app_state.query_params.limit,
        "bounds": app_state.query_params.bounds,
    }))
}

#[tauri::command]
pub async fn clear_query_params(state: State<'_, SharedState>) -> Result<Value, String> {
    let mut state = state.lock().await;
    state.query_params = QueryParams::new();
    Ok(json!({}))
}

#[tauri::command]
pub async fn get_query_type(state: State<'_, SharedState>) -> Result<String, String> {
    let state = state.lock().await;
    Ok(state.query_type.to_string())
}

#[tauri::command]
pub async fn set_query_type(state: State<'_, SharedState>, query_type: String) -> Result<Value, String> {
    let mut state = state.lock().await;
    state.query_type = match query_type.as_str() {
        "trajectory" => QueryType::Trajectory,
        "flights" => QueryType::Flights,
        "rawdata" => QueryType::Rawdata,
        _ => return Err(format!("Unknown query type: {}", query_type)),
    };
    Ok(json!({"query_type": state.query_type.to_string()}))
}

#[tauri::command]
pub fn get_quick_time_preset(preset: String) -> Result<Value, String> {
    let now = Local::now().naive_local();
    let now = now.with_second(0).unwrap().with_nanosecond(0).unwrap();

    let (start, stop) = match preset.as_str() {
        "yesterday" => {
            let yesterday = now.date() - Duration::days(1);
            let start = yesterday.and_hms_opt(0, 0, 0).unwrap();
            let stop = now.date().and_hms_opt(0, 0, 0).unwrap();
            (start, stop)
        }
        "last_week" => {
            let days_since_monday = now.weekday().num_days_from_monday() as i64;
            let last_monday = now.date() - Duration::days(days_since_monday + 7);
            let last_sunday = last_monday + Duration::days(6);
            let start = last_monday.and_hms_opt(0, 0, 0).unwrap();
            let stop = last_sunday.and_hms_opt(23, 59, 59).unwrap();
            (start, stop)
        }
        _ => return Ok(json!({})),
    };

    Ok(json!({
        "start": start.format("%Y-%m-%d %H:%M:%S").to_string(),
        "stop": stop.format("%Y-%m-%d %H:%M:%S").to_string(),
    }))
}

#[tauri::command]
pub async fn build_query_preview_cmd(state: State<'_, SharedState>) -> Result<String, String> {
    let state = state.lock().await;

    if state.query_params.start.is_none() {
        return Ok("# Error: Start time is required".to_string());
    }

    // Use correct method name based on query type
    let method_name = match state.query_type {
        QueryType::Trajectory => "history",
        QueryType::Flights => "flightlist",
        QueryType::Rawdata => "rawdata",
    };

    Ok(build_query_preview_method(&state.query_params, method_name))
}

// ========== Query Execution Commands ==========

#[tauri::command]
pub async fn execute_query_async(state: State<'_, SharedState>) -> Result<Value, String> {
    let mut app_state = state.lock().await;

    if app_state.query_params.start.is_none() {
        return Ok(json!({"error": "Start time is required"}));
    }

    if app_state.execution.is_executing {
        return Ok(json!({"error": "A query is already running"}));
    }

    // Reset execution state
    app_state.reset_execution();
    app_state.add_log("Starting query execution");

    // Clone params and query type for async execution
    let params = app_state.query_params.clone();
    let query_type = app_state.query_type;
    drop(app_state);

    // Spawn background task
    let state_clone = state.inner().clone();
    tokio::spawn(async move {
        execute_query_background(state_clone, params, query_type).await;
    });

    Ok(json!({"started": true}))
}

async fn execute_query_background(state: SharedState, params: QueryParams, query_type: QueryType) {
    // Build SQL query for logging
    let sql = match query_type {
        QueryType::Trajectory => build_history_query(&params),
        QueryType::Flights => build_flightlist_query(&params),
        QueryType::Rawdata => build_rawdata_query(&params, RawTable::default()),
    };

    // Log start and SQL
    {
        let mut app_state = state.lock().await;
        let type_str = match query_type {
            QueryType::Trajectory => "trajectory",
            QueryType::Flights => "flight list",
            QueryType::Rawdata => "raw data",
        };
        app_state.add_log(&format!("Starting {} query execution", type_str));
        app_state.add_log("───── SQL Query ─────");
        // Log each line of SQL separately for better formatting
        for line in sql.lines() {
            app_state.add_log(line);
        }
        app_state.add_log("─────────────────────");
    }

    // Initialize Trino client
    let trino_result = Trino::new().await;

    let mut trino = match trino_result {
        Ok(mut t) => {
            t.set_source("ostk");
            t
        }
        Err(e) => {
            let mut app_state = state.lock().await;
            app_state.add_log(&format!("Connection error: {}", e));
            app_state.execution.status = "Error".to_string();
            app_state.execution.result = Some(ExecutionResult::Error {
                error: e.to_string(),
            });
            app_state.execution.is_executing = false;
            return;
        }
    };

    {
        let mut app_state = state.lock().await;
        app_state.add_log("Connected to OpenSky Trino");
        app_state.execution.status = "Executing query...".to_string();
    }

    // Create progress callback (reused for all query types)
    let make_progress_callback = |state: SharedState| {
        move |status: opensky::QueryStatus| {
            let state_clone = state.clone();
            tokio::spawn(async move {
                let mut app_state = state_clone.lock().await;
                app_state.execution.status = format!(
                    "{} | {:.1}% | {} rows",
                    status.state, status.progress, status.row_count
                );
                if let Some(qid) = &status.query_id {
                    if app_state.execution.query_id.is_none() {
                        app_state.execution.query_id = Some(qid.clone());
                        app_state.add_log(&format!("Query ID: {}", qid));
                        app_state.add_log(&format!("Check progress at: https://trino.opensky-network.org/ui/query.html?{}", qid));
                    }
                }
            });
        }
    };

    // Execute query based on type (all with progress callback for cancel support)
    let result = match query_type {
        QueryType::Trajectory => {
            trino
                .history_with_progress(params, make_progress_callback(state.clone()))
                .await
        }
        QueryType::Flights => {
            trino
                .flightlist_with_progress(params, make_progress_callback(state.clone()))
                .await
        }
        QueryType::Rawdata => {
            trino
                .rawdata_with_progress(params, make_progress_callback(state.clone()))
                .await
        }
    };

    // Handle result
    let mut app_state = state.lock().await;
    match result {
        Ok(data) => {
            let row_count = data.len();
            let columns = data.columns();

            if row_count == 0 {
                app_state.add_log("No data found");
                app_state.execution.status = "No data found".to_string();
                app_state.execution.result = Some(ExecutionResult::NoData {
                    error: "No data found".to_string(),
                    row_count: 0,
                });
            } else {
                app_state.add_log(&format!("Retrieved {} rows", row_count));
                app_state.execution.status = "Complete".to_string();
                app_state.execution.result = Some(ExecutionResult::Success {
                    success: true,
                    row_count,
                    columns,
                });
                app_state.last_result = Some(data);
            }
        }
        Err(e) => {
            app_state.add_log(&format!("Error: {}", e));
            app_state.execution.status = "Error".to_string();
            app_state.execution.result = Some(ExecutionResult::Error {
                error: e.to_string(),
            });
        }
    }

    app_state.execution.is_executing = false;
}

#[tauri::command]
pub async fn get_execution_status(state: State<'_, SharedState>) -> Result<Value, String> {
    let app_state = state.lock().await;

    let result_json = app_state.execution.result.as_ref().map(|r| {
        match r {
            ExecutionResult::Success { success, row_count, columns } => {
                json!({"success": success, "row_count": row_count, "columns": columns})
            }
            ExecutionResult::NoData { error, row_count } => {
                json!({"error": error, "row_count": row_count})
            }
            ExecutionResult::Error { error } => json!({"error": error}),
            ExecutionResult::Cancelled { cancelled } => json!({"cancelled": cancelled}),
        }
    });

    Ok(json!({
        "is_executing": app_state.execution.is_executing,
        "status": app_state.execution.status,
        "logs": app_state.execution.logs.iter().collect::<Vec<_>>(),
        "complete": app_state.execution.result.is_some(),
        "result": result_json,
        "can_cancel": app_state.execution.is_executing && app_state.execution.query_id.is_some(),
    }))
}

#[tauri::command]
pub async fn cancel_query(state: State<'_, SharedState>) -> Result<Value, String> {
    let mut app_state = state.lock().await;

    if !app_state.execution.is_executing {
        return Ok(json!({"error": "No query is running"}));
    }

    app_state.add_log("Cancellation requested...");
    app_state.execution.status = "Cancelling...".to_string();

    // Clone query_id for use after mutable borrow
    let query_id = app_state.execution.query_id.clone();

    // Cancel via Trino REST API if we have a query ID
    if let Some(qid) = query_id {
        app_state.add_log(&format!("Cancelling Trino query {}...", qid));

        // Try to cancel via new Trino connection (best effort)
        match Trino::new().await {
            Ok(mut trino) => {
                trino.set_source("ostk");
                match trino.cancel(&qid).await {
                    Ok(_) => app_state.add_log("Trino query cancelled"),
                    Err(e) => app_state.add_log(&format!("Cancel error: {}", e)),
                }
            }
            Err(e) => app_state.add_log(&format!("Connection error: {}", e)),
        }
    }

    app_state.execution.status = "Cancelled".to_string();
    app_state.execution.result = Some(ExecutionResult::Cancelled { cancelled: true });
    app_state.execution.is_executing = false;

    Ok(json!({"success": true, "message": "Query cancelled"}))
}

// ========== Export Commands ==========

#[tauri::command]
pub async fn export_csv(state: State<'_, SharedState>, filepath: String) -> Result<Value, String> {
    let app_state = state.lock().await;

    match &app_state.last_result {
        Some(data) => {
            data.to_csv(&filepath)
                .map_err(|e| e.to_string())?;
            Ok(json!({"success": true, "filepath": filepath}))
        }
        None => Ok(json!({"error": "No data to export"})),
    }
}

#[tauri::command]
pub async fn export_parquet(state: State<'_, SharedState>, filepath: String) -> Result<Value, String> {
    let app_state = state.lock().await;

    match &app_state.last_result {
        Some(data) => {
            data.to_parquet(&filepath)
                .map_err(|e| e.to_string())?;
            Ok(json!({"success": true, "filepath": filepath}))
        }
        None => Ok(json!({"error": "No data to export"})),
    }
}

// ========== Chat Commands ==========

#[tauri::command]
pub async fn get_messages(state: State<'_, SharedState>) -> Result<Value, String> {
    let app_state = state.lock().await;
    Ok(json!(app_state.messages))
}

#[tauri::command]
pub async fn clear_messages(state: State<'_, SharedState>) -> Result<Value, String> {
    let mut app_state = state.lock().await;
    app_state.clear_messages();
    Ok(json!([]))
}

#[tauri::command]
pub async fn send_message(
    state: State<'_, SharedState>,
    user_message: String,
) -> Result<Value, String> {
    // Add user message
    {
        let mut app_state = state.lock().await;
        app_state.add_message("user", &user_message, "text");
    }

    // Load LLM config
    let config = LlmConfig::load();

    if !config.is_configured() {
        let mut app_state = state.lock().await;
        app_state.add_message(
            "assistant",
            "LLM not configured. Please add your API key in Settings.",
            "error",
        );
        return Ok(json!({
            "messages": app_state.messages,
        }));
    }

    // Create agent based on provider
    let agent = match config.provider.as_str() {
        "groq" => {
            let api_key = config.groq_api_key.unwrap();
            let client = GroqClient::new(api_key, &config.groq_model);
            Agent::new(client)
        }
        _ => {
            let mut app_state = state.lock().await;
            app_state.add_message(
                "assistant",
                &format!("Provider '{}' not yet supported. Use Groq for now.", config.provider),
                "error",
            );
            return Ok(json!({
                "messages": app_state.messages,
            }));
        }
    };

    // Parse the query
    match agent.parse_query(&user_message).await {
        Ok((parsed_query, _raw_response)) => {
            let mut app_state = state.lock().await;

            // Update query params
            app_state.query_params = parsed_query.params.clone();

            // Build query preview with correct method name based on query type
            let method_name = match parsed_query.query_type {
                QueryType::Trajectory => "history",
                QueryType::Flights => "flightlist",
                QueryType::Rawdata => "rawdata",
            };
            let preview = build_query_preview_method(&parsed_query.params, method_name);

            // Add "code" type message with hint - frontend renders hint between code and button
            app_state.add_message_with_hint("assistant", &preview, "code", &parsed_query.hint);

            // Store agent info
            app_state.agent_configured = true;
            app_state.provider_name = config.provider.clone();
            app_state.model_name = config.groq_model.clone();

            Ok(json!({
                "messages": app_state.messages,
                "query_type": parsed_query.query_type.to_string(),
                "hint": parsed_query.hint,
                "params": json!({
                    "icao24": parsed_query.params.icao24,
                    "start": parsed_query.params.start,
                    "stop": parsed_query.params.stop,
                    "callsign": parsed_query.params.callsign,
                    "departure_airport": parsed_query.params.departure_airport,
                    "arrival_airport": parsed_query.params.arrival_airport,
                    "airport": parsed_query.params.airport,
                    "limit": parsed_query.params.limit,
                }),
            }))
        }
        Err(e) => {
            let mut app_state = state.lock().await;
            app_state.add_message(
                "assistant",
                &format!("Sorry, I couldn't understand that query: {}", e),
                "error",
            );
            Ok(json!({
                "messages": app_state.messages,
            }))
        }
    }
}

// ========== Agent Status ==========

#[tauri::command]
pub async fn get_agent_status(state: State<'_, SharedState>) -> Result<Value, String> {
    let config = LlmConfig::load();
    let app_state = state.lock().await;

    Ok(json!({
        "configured": config.is_configured(),
        "provider": config.provider,
        "model": match config.provider.as_str() {
            "groq" => config.groq_model,
            "openai" => config.openai_model,
            "ollama" => config.ollama_model,
            _ => "unknown".to_string(),
        },
        "error": app_state.error_message,
    }))
}

// ========== Config Commands ==========

#[tauri::command]
pub fn get_opensky_config() -> Result<Value, String> {
    match opensky::Config::load() {
        Ok(config) => {
            let has_password = config.password.is_some();
            Ok(json!({
                "username": config.username.unwrap_or_default(),
                "password": if has_password { "********" } else { "" },
                "has_password": has_password,
            }))
        }
        Err(e) => Ok(json!({
            "error": e.to_string(),
            "username": "",
            "password": "",
        })),
    }
}

#[tauri::command]
pub fn save_opensky_config(username: String, password: String) -> Result<Value, String> {
    // Get config directory
    let config_dir = dirs::config_dir()
        .ok_or("Could not find config directory")?
        .join("opensky");

    // Create directory if needed
    std::fs::create_dir_all(&config_dir)
        .map_err(|e| format!("Failed to create config directory: {}", e))?;

    let config_file = config_dir.join("settings.conf");

    // Write config file
    let content = format!(
        "[default]\nusername = {}\npassword = {}\n",
        username, password
    );

    std::fs::write(&config_file, content)
        .map_err(|e| format!("Failed to write config file: {}", e))?;

    Ok(json!({"success": true}))
}

#[tauri::command]
pub fn get_llm_config() -> Result<Value, String> {
    let config = LlmConfig::load();

    // Mask API keys for display
    let mask_key = |key: &Option<String>| -> String {
        match key {
            Some(k) if k.len() > 8 => format!("{}...{}", &k[..4], &k[k.len()-4..]),
            Some(_) => "****".to_string(),
            None => "".to_string(),
        }
    };

    Ok(json!({
        "provider": config.provider,
        "groq_api_key": mask_key(&config.groq_api_key),
        "groq_model": config.groq_model,
        "has_groq_key": config.groq_api_key.is_some(),
        "openai_api_key": mask_key(&config.openai_api_key),
        "openai_model": config.openai_model,
        "has_openai_key": config.openai_api_key.is_some(),
        "ollama_base_url": config.ollama_base_url,
        "ollama_model": config.ollama_model,
    }))
}

#[tauri::command]
pub fn save_llm_config(
    provider: String,
    model: String,
    api_key: String,
) -> Result<Value, String> {
    let mut config = LlmConfig::load();

    config.provider = provider.clone();

    // Update the appropriate provider settings
    match provider.as_str() {
        "groq" => {
            if !api_key.is_empty() && !api_key.contains("...") {
                config.groq_api_key = Some(api_key);
            }
            config.groq_model = model;
        }
        "openai" => {
            if !api_key.is_empty() && !api_key.contains("...") {
                config.openai_api_key = Some(api_key);
            }
            config.openai_model = model;
        }
        "ollama" => {
            config.ollama_model = model;
        }
        _ => return Err(format!("Unknown provider: {}", provider)),
    }

    config.save()?;

    Ok(json!({"success": true, "provider": provider}))
}

#[tauri::command]
pub async fn fetch_groq_models(api_key: String) -> Result<Value, String> {
    // Use provided key or load from config
    let key = if api_key.is_empty() || api_key.contains("...") {
        let config = LlmConfig::load();
        config.groq_api_key.ok_or("No Groq API key configured")?
    } else {
        api_key
    };

    match crate::llm::fetch_models(&key).await {
        Ok(models) => {
            // Sort models alphabetically
            let mut sorted = models;
            sorted.sort();
            Ok(json!({"models": sorted}))
        }
        Err(e) => Ok(json!({"error": e.to_string()})),
    }
}
