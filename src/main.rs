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

/// Apply workarounds for NVIDIA + Wayland + WebKitGTK compatibility issues.
/// Must be called before Tauri/WebKit initialization.
#[cfg(target_os = "linux")]
fn apply_nvidia_wayland_workaround() {
    use std::env;
    use std::path::Path;

    // Check if already set by user
    if env::var("WEBKIT_DISABLE_DMABUF_RENDERER").is_ok() {
        return;
    }

    // Detect Wayland session
    let is_wayland = env::var("XDG_SESSION_TYPE")
        .map(|v| v == "wayland")
        .unwrap_or(false)
        || env::var("WAYLAND_DISPLAY").is_ok();

    // Detect NVIDIA driver (presence of /proc/driver/nvidia)
    let has_nvidia = Path::new("/proc/driver/nvidia").exists();

    if is_wayland && has_nvidia {
        // SAFETY: Called at start of main() before any threads are spawned
        unsafe {
            env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
        }
    }
}

#[cfg(not(target_os = "linux"))]
fn apply_nvidia_wayland_workaround() {
    // No-op on non-Linux platforms
}

fn main() {
    apply_nvidia_wayland_workaround();
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(new_shared_state())
        .invoke_handler(tauri::generate_handler![
            // Query parameter commands
            commands::get_query_params,
            commands::set_query_param,
            commands::clear_query_params,
            commands::get_query_type,
            commands::set_query_type,
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
