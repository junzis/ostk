//! OSTK - OpenSky Toolkit
//!
//! A desktop application for querying OpenSky Network flight data.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod agent;
mod commands;
mod config;
mod llm;
mod state;

use state::new_shared_state;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(new_shared_state())
        .invoke_handler(tauri::generate_handler![
            // Query parameter commands
            commands::get_query_params,
            commands::set_query_param,
            commands::clear_query_params,
            commands::get_quick_time_preset,
            commands::build_query_preview_cmd,
            // Query execution commands
            commands::execute_query_async,
            commands::get_execution_status,
            commands::cancel_query,
            // Export commands
            commands::export_csv,
            commands::export_parquet,
            // Chat commands
            commands::get_messages,
            commands::clear_messages,
            commands::send_message,
            // Config commands
            commands::get_opensky_config,
            commands::save_opensky_config,
            commands::get_llm_config,
            commands::save_llm_config,
            commands::get_agent_status,
            commands::fetch_groq_models,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
