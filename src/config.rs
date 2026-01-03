//! Configuration management for OSTK.

use configparser::ini::Ini;
use std::path::PathBuf;

/// LLM configuration.
#[derive(Debug, Clone, Default)]
pub struct LlmConfig {
    pub provider: String,
    pub groq_api_key: Option<String>,
    pub groq_model: String,
    pub openai_api_key: Option<String>,
    pub openai_model: String,
    pub ollama_base_url: String,
    pub ollama_model: String,
}

impl LlmConfig {
    /// Load LLM configuration from config file.
    pub fn load() -> Self {
        let config_path = Self::config_path();
        let mut config = LlmConfig::default();

        // Set defaults (models are empty until configured or fetched)
        config.provider = "groq".to_string();
        config.ollama_base_url = "http://localhost:11434".to_string();

        if let Some(path) = config_path {
            if path.exists() {
                let mut ini = Ini::new();
                if ini.load(&path).is_ok() {
                    // Load [llm] section
                    if let Some(provider) = ini.get("llm", "provider") {
                        config.provider = provider;
                    }

                    // Groq settings
                    if let Some(key) = ini.get("llm", "groq_api_key") {
                        if !key.is_empty() {
                            config.groq_api_key = Some(key);
                        }
                    }
                    if let Some(model) = ini.get("llm", "groq_model") {
                        config.groq_model = model;
                    }

                    // OpenAI settings
                    if let Some(key) = ini.get("llm", "openai_api_key") {
                        if !key.is_empty() {
                            config.openai_api_key = Some(key);
                        }
                    }
                    if let Some(model) = ini.get("llm", "openai_model") {
                        config.openai_model = model;
                    }

                    // Ollama settings
                    if let Some(url) = ini.get("llm", "ollama_base_url") {
                        config.ollama_base_url = url;
                    }
                    if let Some(model) = ini.get("llm", "ollama_model") {
                        config.ollama_model = model;
                    }
                }
            }
        }

        // Also check environment variables
        if config.groq_api_key.is_none() {
            if let Ok(key) = std::env::var("GROQ_API_KEY") {
                config.groq_api_key = Some(key);
            }
        }
        if config.openai_api_key.is_none() {
            if let Ok(key) = std::env::var("OPENAI_API_KEY") {
                config.openai_api_key = Some(key);
            }
        }

        config
    }

    /// Save LLM configuration to config file.
    pub fn save(&self) -> Result<(), String> {
        let config_path = Self::config_path()
            .ok_or("Could not determine config directory")?;

        // Ensure directory exists
        if let Some(parent) = config_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("Failed to create config directory: {}", e))?;
        }

        let mut ini = Ini::new();

        // Load existing config to preserve other sections
        if config_path.exists() {
            let _ = ini.load(&config_path);
        }

        // Set [llm] section
        ini.set("llm", "provider", Some(self.provider.clone()));
        ini.set("llm", "groq_api_key", self.groq_api_key.clone());
        ini.set("llm", "groq_model", Some(self.groq_model.clone()));
        ini.set("llm", "openai_api_key", self.openai_api_key.clone());
        ini.set("llm", "openai_model", Some(self.openai_model.clone()));
        ini.set("llm", "ollama_base_url", Some(self.ollama_base_url.clone()));
        ini.set("llm", "ollama_model", Some(self.ollama_model.clone()));

        ini.write(&config_path)
            .map_err(|e| format!("Failed to write config file: {}", e))?;

        Ok(())
    }

    /// Get the config file path.
    fn config_path() -> Option<PathBuf> {
        dirs::config_dir().map(|d| d.join("ostk").join("settings.conf"))
    }

    /// Check if the current provider is configured with API key.
    pub fn is_configured(&self) -> bool {
        match self.provider.as_str() {
            "groq" => self.groq_api_key.is_some(),
            "openai" => self.openai_api_key.is_some(),
            "ollama" => true, // Ollama doesn't need API key
            _ => false,
        }
    }
}
