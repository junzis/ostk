"""Python API exposed to JavaScript via PyWebView."""

import multiprocessing as mp
from datetime import datetime, timedelta
from typing import Any, Optional

import webview

from .state import AppState, QueryParams
from .utils import (
    get_provider_display_name,
    load_llm_config,
    load_pyopensky_config,
    save_llm_config,
    save_pyopensky_config,
)


def _run_query_process(params: dict, result_q: mp.Queue, log_q: mp.Queue):
    """Run query in separate process (can be terminated)."""
    import io
    import logging
    import sys

    import tqdm.std

    class LogCapture(io.StringIO):
        def __init__(self, q):
            super().__init__()
            self.q = q

        def write(self, text):
            super().write(text)
            if "\r" in text:
                parts = text.split("\r")
                if parts[-1].strip():
                    self.q.put(("progress", parts[-1]))
            elif text.strip():
                for line in text.split("\n"):
                    if line.strip():
                        self.q.put(("line", line))

        def flush(self):
            pass

    class QueueLogHandler(logging.Handler):
        def __init__(self, q):
            super().__init__()
            self.q = q

        def emit(self, record):
            self.q.put(("line", f"{record.name}: {record.getMessage()}"))

    captured = LogCapture(log_q)
    sys.stdout = captured
    sys.stderr = captured

    # Patch tqdm
    import pyopensky.trino

    class CaptureTqdm(tqdm.std.tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["file"] = captured
            kwargs["dynamic_ncols"] = False
            kwargs["ncols"] = 80
            kwargs["disable"] = False
            super().__init__(*args, **kwargs)

    pyopensky.trino.tqdm = CaptureTqdm

    # Patch Trino.process_result to capture query_id
    from pyopensky.trino import Trino

    original_process_result = Trino.process_result

    def patched_process_result(self, res, batch_size=50_000):
        if res.cursor is not None and hasattr(res.cursor, "query_id"):
            query_id = res.cursor.query_id
            log_q.put(("query_id", query_id))
        return original_process_result(self, res, batch_size)

    Trino.process_result = patched_process_result

    # Setup logging
    handler = QueueLogHandler(log_q)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    for name in ["pyopensky", "trino", "httpx"]:
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    try:
        from pyopensky.trino import Trino

        trino = Trino()
        df = trino.history(**params)

        if df is not None and not df.empty:
            df = df.sort_values(["icao24", "time"]).reset_index(drop=True)
            log_q.put(("line", f"Retrieved {len(df):,} rows"))
            result_q.put(("success", df))
        else:
            result_q.put(("no_data", None))
    except Exception as ex:
        result_q.put(("error", str(ex)))


def _cancel_trino_query(query_id: str) -> bool:
    """Cancel a Trino query via REST API."""
    import httpx
    from pyopensky.config import trino_username
    from pyopensky.trino import Trino

    try:
        trino = Trino()
        token = trino.token()

        if token is None:
            return False

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Trino-User": trino_username or "pyopensky",
        }

        response = httpx.delete(
            f"https://trino.opensky-network.org/v1/query/{query_id}",
            headers=headers,
            timeout=10.0,
        )

        return response.status_code in (200, 204, 404)
    except Exception:
        return False


class Api:
    """API class exposed to JavaScript via window.pywebview.api."""

    def __init__(self, window=None):
        self.window = window
        self.state = AppState()
        self._cancel_requested = False
        self._query_process: Optional[mp.Process] = None
        self._result_queue: Optional[mp.Queue] = None
        self._log_queue: Optional[mp.Queue] = None
        self._trino_query_id: Optional[str] = None
        self._execution_logs: list[str] = []
        self._execution_status: str = ""
        self._execution_result: Optional[dict] = None
        self._mp_context = mp.get_context("spawn")
        self._init_agent()

    def set_window(self, window):
        """Set the webview window reference."""
        self.window = window

    def _init_agent(self) -> None:
        """Initialize the LLM agent from config."""
        try:
            from ostk.agent import Agent

            config = load_llm_config()
            provider = config.get("provider", "")

            if not provider:
                self.state.error_message = "No LLM provider configured"
                return

            api_key = config.get(f"{provider}_api_key", "")
            model = config.get(f"{provider}_model", "")
            base_url = config.get("ollama_base_url", "http://localhost:11434")

            if provider in ("groq", "openai") and not api_key:
                self.state.error_message = f"No API key configured for {provider}"
                return

            self.state.agent = Agent(
                provider=provider,
                api_key=api_key if api_key else None,
                model=model if model else None,
                base_url=base_url if provider == "ollama" else None,
            )
            self.state.provider_name = get_provider_display_name(provider)
            self.state.model_name = model
            self.state.error_message = None

        except Exception as e:
            self.state.error_message = str(e)
            self.state.agent = None

    # ========== Query Methods ==========

    def get_query_params(self) -> dict:
        """Get current query parameters."""
        return self.state.current_params.to_dict()

    def set_query_param(self, key: str, value: Any) -> dict:
        """Set a query parameter."""
        if hasattr(self.state.current_params, key):
            setattr(self.state.current_params, key, value)
        return self.state.current_params.to_dict()

    def clear_query_params(self) -> dict:
        """Clear all query parameters."""
        self.state.current_params.clear()
        return {}

    def get_quick_time_preset(self, preset: str) -> dict:
        """Get start/stop times for a preset."""
        now = datetime.now().replace(second=0, microsecond=0)

        if preset == "last_hour":
            stop = now.replace(minute=0)
            start = stop - timedelta(hours=1)
        elif preset == "yesterday":
            yesterday = now.date() - timedelta(days=1)
            start = datetime.combine(yesterday, datetime.min.time())
            stop = datetime.combine(now.date(), datetime.min.time())
        elif preset == "last_week":
            days_since_monday = now.weekday()
            last_monday = now.date() - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            start = datetime.combine(last_monday, datetime.min.time())
            stop = datetime.combine(last_sunday, datetime.max.time().replace(microsecond=0))
        else:
            return {}

        return {
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "stop": stop.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def build_query_preview(self) -> str:
        """Build a preview of the trino.history() call."""
        if not self.state.agent:
            return "# Error: No LLM agent configured"

        params = self.state.current_params.to_dict()
        if not params.get("start"):
            return "# Error: Start time is required"

        return self.state.agent.build_history_call(params)

    def _add_log(self, message: str) -> None:
        """Add a log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._execution_logs.append(f"[{timestamp}] {message}")

    def _process_log_queue(self) -> None:
        """Process messages from the log queue."""
        if not self._log_queue:
            return

        try:
            while not self._log_queue.empty():
                msg_type, msg_data = self._log_queue.get_nowait()
                if msg_type == "query_id":
                    self._trino_query_id = msg_data
                    self._add_log(f"Query ID: {msg_data}")
                    self._execution_status = "Fetching data from OpenSky..."
                elif msg_type == "progress":
                    # Update status with progress info
                    self._execution_status = msg_data.strip()[:80]
                elif msg_type == "line":
                    self._add_log(msg_data)
                    # Detect phase transitions
                    if "Saving results to" in msg_data:
                        self._execution_status = "Saving to cache..."
                    elif "Retrieved" in msg_data and "rows" in msg_data:
                        self._execution_status = "Processing results..."
        except Exception:
            pass

    def _process_result_queue(self) -> bool:
        """Check for results from the query process. Returns True if result received."""
        if not self._result_queue:
            return False

        try:
            status, data = self._result_queue.get_nowait()

            if status == "success":
                self.state.last_result = data
                self._add_log("Query completed successfully")
                self._execution_status = "Complete"
                self._execution_result = {
                    "success": True,
                    "row_count": len(data),
                    "columns": list(data.columns),
                }
            elif status == "no_data":
                self._add_log("No data found")
                self._execution_status = "No data found"
                self._execution_result = {"error": "No data found", "row_count": 0}
            elif status == "error":
                self._add_log(f"Error: {data}")
                self._execution_status = "Error"
                self._execution_result = {"error": data}

            return True
        except Exception:
            return False

    def execute_query_async(self, params: Optional[dict] = None) -> dict:
        """Start query execution in background process. Poll get_execution_status for progress."""
        if params is None:
            params = self.state.current_params.to_dict()

        if not params.get("start"):
            return {"error": "Start time is required"}

        if self.state.is_executing:
            return {"error": "A query is already running"}

        # Reset state
        self._cancel_requested = False
        self._trino_query_id = None
        self._execution_result = None
        self._execution_logs = []
        self._execution_status = "Connecting to OpenSky..."
        self.state.is_executing = True

        # Create queues and start process
        self._result_queue = self._mp_context.Queue()
        self._log_queue = self._mp_context.Queue()

        self._query_process = self._mp_context.Process(
            target=_run_query_process,
            args=(params, self._result_queue, self._log_queue),
        )
        self._query_process.start()
        self._add_log("Starting query execution")

        return {"started": True}

    def get_execution_status(self) -> dict:
        """Get current execution status and logs."""
        # Process any pending log/result messages
        self._process_log_queue()
        result_received = self._process_result_queue()

        # Check if process finished
        process_alive = self._query_process and self._query_process.is_alive()
        is_complete = result_received or self._execution_result is not None

        if not process_alive and not is_complete and self.state.is_executing:
            # Process died without result
            if self._cancel_requested:
                self._execution_status = "Cancelled"
                self._execution_result = {"cancelled": True}
            else:
                self._execution_status = "Error"
                self._execution_result = {"error": "Query process terminated unexpectedly"}
            is_complete = True

        if is_complete:
            self.state.is_executing = False

        return {
            "is_executing": self.state.is_executing,
            "status": self._execution_status,
            "logs": self._execution_logs[-30:],
            "complete": is_complete,
            "result": self._execution_result if is_complete else None,
            "can_cancel": self.state.is_executing and self._trino_query_id is not None,
        }

    def cancel_query(self) -> dict:
        """Cancel the running query."""
        if not self.state.is_executing:
            return {"error": "No query is running"}

        self._cancel_requested = True
        self._add_log("Cancellation requested...")
        self._execution_status = "Cancelling..."

        # Cancel via Trino REST API if we have a query ID
        if self._trino_query_id:
            self._add_log(f"Cancelling Trino query {self._trino_query_id}...")
            try:
                success = _cancel_trino_query(self._trino_query_id)
                if success:
                    self._add_log("Trino query cancelled")
                else:
                    self._add_log("Failed to cancel Trino query")
            except Exception as e:
                self._add_log(f"Cancel error: {e}")

        # Terminate the process
        if self._query_process and self._query_process.is_alive():
            self._query_process.terminate()
            self._query_process.join(timeout=2)
            if self._query_process.is_alive():
                self._query_process.kill()
            self._add_log("Query process terminated")

        self._execution_status = "Cancelled"
        self._execution_result = {"cancelled": True}
        self.state.is_executing = False

        return {"success": True, "message": "Query cancelled"}

    # ========== Export Methods with File Dialogs ==========

    def save_file_dialog(self, format: str) -> dict:
        """Open a save file dialog and export data."""
        if self.state.last_result is None:
            return {"error": "No data to export"}

        if not self.window:
            return {"error": "Window not available"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "csv":
            file_types = ("CSV Files (*.csv)",)
            default_name = f"ostk_export_{timestamp}.csv"
        else:
            file_types = ("Parquet Files (*.parquet)",)
            default_name = f"ostk_export_{timestamp}.parquet"

        try:
            result = self.window.create_file_dialog(
                webview.FileDialog.SAVE,
                directory="",
                save_filename=default_name,
                file_types=file_types
            )

            if result:
                filepath = result if isinstance(result, str) else result[0]

                if format == "csv":
                    self.state.last_result.to_csv(filepath, index=False)
                else:
                    self.state.last_result.to_parquet(filepath, index=False)

                return {"success": True, "filepath": filepath}
            else:
                return {"cancelled": True}

        except Exception as e:
            return {"error": str(e)}

    def export_csv(self, filepath: str = "") -> dict:
        """Export last result to CSV. If no filepath, opens save dialog."""
        if not filepath:
            return self.save_file_dialog("csv")

        if self.state.last_result is None:
            return {"error": "No data to export"}

        try:
            self.state.last_result.to_csv(filepath, index=False)
            return {"success": True, "filepath": filepath}
        except Exception as e:
            return {"error": str(e)}

    def export_parquet(self, filepath: str = "") -> dict:
        """Export last result to Parquet. If no filepath, opens save dialog."""
        if not filepath:
            return self.save_file_dialog("parquet")

        if self.state.last_result is None:
            return {"error": "No data to export"}

        try:
            self.state.last_result.to_parquet(filepath, index=False)
            return {"success": True, "filepath": filepath}
        except Exception as e:
            return {"error": str(e)}

    # ========== Chat Methods ==========

    def get_messages(self) -> list:
        """Get chat message history."""
        return [
            {"role": m.role, "content": m.content, "type": m.msg_type}
            for m in self.state.messages
        ]

    def clear_messages(self) -> list:
        """Clear chat history."""
        self.state.clear_messages()
        return []

    def send_message(self, user_message: str) -> dict:
        """Send a message to the LLM agent and get response."""
        if not self.state.agent:
            return {
                "error": self.state.error_message or "No LLM agent configured",
                "messages": self.get_messages(),
            }

        # Add user message
        self.state.add_message("user", user_message)

        try:
            # Parse query with agent
            params = self.state.agent.parse_query(user_message)

            if not params:
                self.state.add_message(
                    "assistant",
                    "I couldn't parse that query. Please try rephrasing.",
                    "error",
                )
                return {"messages": self.get_messages()}

            # Update current params
            self.state.current_params.update_from_dict(params)

            # Generate confirmation message
            confirmation = self._generate_confirmation(params)
            self.state.add_message("assistant", confirmation)

            # Generate code
            code = self.state.agent.build_history_call(params)
            self.state.add_message("assistant", code, "code")

            return {"messages": self.get_messages(), "params": params}

        except Exception as e:
            self.state.add_message("assistant", f"Error: {str(e)}", "error")
            return {"error": str(e), "messages": self.get_messages()}

    def _generate_confirmation(self, params: dict) -> str:
        """Generate a confirmation message for parsed parameters."""
        parts = []
        if params.get("icao24"):
            parts.append(f"aircraft **{params['icao24']}**")
        if params.get("callsign"):
            parts.append(f"callsign **{params['callsign']}**")
        if params.get("departure_airport"):
            parts.append(f"departing from **{params['departure_airport']}**")
        if params.get("arrival_airport"):
            parts.append(f"arriving at **{params['arrival_airport']}**")
        if params.get("airport"):
            parts.append(f"via airport **{params['airport']}**")

        time_range = ""
        if params.get("start") and params.get("stop"):
            time_range = f" from **{params['start']}** to **{params['stop']}**"
        elif params.get("start"):
            time_range = f" starting from **{params['start']}**"

        if parts:
            return f"Looking for {', '.join(parts)}{time_range}."
        elif time_range:
            return f"Looking for all flights{time_range}."
        return "I'll search for flights with those parameters."

    # ========== Settings Methods ==========

    def get_llm_config(self) -> dict:
        """Get current LLM configuration."""
        config = load_llm_config()
        return {
            "provider": config.get("provider", ""),
            "groq_api_key": config.get("groq_api_key", ""),
            "groq_model": config.get("groq_model", "openai/gpt-oss-120b"),
            "openai_api_key": config.get("openai_api_key", ""),
            "openai_model": config.get("openai_model", "gpt-4o"),
            "ollama_base_url": config.get("ollama_base_url", "http://localhost:11434"),
            "ollama_model": config.get("ollama_model", "llama3.1:8b"),
        }

    def save_llm_config(
        self, provider: str, model: str, api_key: str = "", base_url: str = ""
    ) -> dict:
        """Save LLM configuration."""
        try:
            save_llm_config(
                provider=provider,
                model=model,
                api_key=api_key if api_key else None,
                base_url=base_url if base_url else None,
            )
            # Reinitialize agent
            self._init_agent()

            if self.state.error_message:
                return {"error": self.state.error_message}

            return {"success": True, "provider": self.state.provider_name}
        except Exception as e:
            return {"error": str(e)}

    def get_pyopensky_config(self) -> dict:
        """Get current PyOpenSky configuration."""
        return load_pyopensky_config()

    def save_pyopensky_config(
        self,
        username: str = "",
        password: str = "",
        client_id: str = "",
        client_secret: str = "",
        cache_purge: str = "90 days",
    ) -> dict:
        """Save PyOpenSky configuration."""
        try:
            save_pyopensky_config(
                username=username if username else None,
                password=password if password else None,
                client_id=client_id if client_id else None,
                client_secret=client_secret if client_secret else None,
                cache_purge=cache_purge,
            )
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def get_agent_status(self) -> dict:
        """Get current agent status."""
        return {
            "configured": self.state.agent is not None,
            "provider": self.state.provider_name,
            "model": self.state.model_name,
            "error": self.state.error_message,
        }

    def fetch_groq_models(self, api_key: str) -> dict:
        """Fetch available models from Groq, filtered for text generation."""
        import re

        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            models = client.models.list()

            # Patterns to exclude (non-text models)
            exclude_patterns = ["whisper", "guard", "embed", "tts", "vision", "scout", "maverick"]

            # Get all text generation model IDs
            text_models = []
            for m in models.data:
                model_id = m.id.lower()
                if not any(pat in model_id for pat in exclude_patterns):
                    text_models.append(m.id)

            # Extract size from model name for sorting (e.g., "70b", "8b", "32b")
            def get_model_size(model_name: str) -> float:
                name_lower = model_name.lower()
                # gpt-oss-120b at the very top (default)
                if "gpt-oss-120b" in name_lower:
                    return 99999
                # Compound models next
                if "compound" in name_lower:
                    return 9999
                # Match patterns like "70b", "8b", "120b", "7b"
                match = re.search(r"(\d+\.?\d*)b", name_lower)
                if match:
                    return float(match.group(1))
                return 0

            # Sort by size (largest first)
            text_models.sort(key=get_model_size, reverse=True)

            # Find gpt-oss-120b model for default
            default_model = None
            for m in text_models:
                if "gpt-oss-120b" in m.lower():
                    default_model = m
                    break
            if not default_model and text_models:
                default_model = text_models[0]

            return {
                "success": True,
                "models": text_models,
                "default": default_model,
            }
        except Exception as e:
            return {"error": str(e)}
