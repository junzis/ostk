"""
Curated list of Groq models with tool calling support.

This file can be easily updated when Groq adds new models.
Reference: https://console.groq.com/docs/tool-use
"""

# Models known to support tool use (text generation with function calling)
TOOL_USE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905",
]

# Default model for new configurations
DEFAULT_MODEL = "openai/gpt-oss-120b"

# Models to exclude (non-text tasks: speech, moderation, embeddings)
EXCLUDE_PATTERNS = ["whisper", "guard", "embed", "compound"]
