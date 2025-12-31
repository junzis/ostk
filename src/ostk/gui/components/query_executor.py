"""Reusable query executor component with log display, cancellation, and export."""

import asyncio
import multiprocessing as mp
from datetime import datetime

import flet as ft


def _run_query_process(params, result_q, log_q):
    """Run query in separate process (can be terminated).

    This function must be at module level to be picklable for spawn context.
    """
    import sys
    import io
    import logging
    import tqdm.std
    import pyopensky.trino
    from ostk.agent import Agent

    class LogCapture(io.StringIO):
        def __init__(self, q):
            super().__init__()
            self.q = q

        def write(self, text):
            super().write(text)
            if '\r' in text:
                parts = text.split('\r')
                if parts[-1].strip():
                    self.q.put(('progress', parts[-1]))
            elif text.strip():
                for line in text.split('\n'):
                    if line.strip():
                        self.q.put(('line', line))

        def flush(self):
            pass

    class QueueLogHandler(logging.Handler):
        def __init__(self, q):
            super().__init__()
            self.q = q

        def emit(self, record):
            self.q.put(('line', f"{record.name}: {record.getMessage()}"))

    captured = LogCapture(log_q)
    sys.stdout = captured
    sys.stderr = captured

    # Patch tqdm
    class CaptureTqdm(tqdm.std.tqdm):
        def __init__(self, *args, **kwargs):
            kwargs['file'] = captured
            kwargs['dynamic_ncols'] = False
            kwargs['ncols'] = 80
            kwargs['disable'] = False
            super().__init__(*args, **kwargs)

    pyopensky.trino.tqdm = CaptureTqdm

    # Patch Trino.process_result to capture the EXECUTE query_id
    from pyopensky.trino import Trino
    original_process_result = Trino.process_result

    def patched_process_result(self, res, batch_size=50_000):
        """Patched to capture the actual EXECUTE query_id."""
        if res.cursor is not None and hasattr(res.cursor, 'query_id'):
            query_id = res.cursor.query_id
            log_q.put(('query_id', query_id))

        # Return original generator directly (don't wrap it)
        return original_process_result(self, res, batch_size)

    Trino.process_result = patched_process_result

    # Setup logging
    handler = QueueLogHandler(log_q)
    handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
    for name in ['pyopensky', 'trino', 'httpx']:
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    try:
        agent = Agent()
        df = agent.execute_query(params)
        if df is not None:
            log_q.put(('line', f"Preparing {len(df):,} rows for display..."))
            result_q.put(('success', df.to_dict('records'), list(df.columns)))
        else:
            result_q.put(('success', None, None))
    except Exception as ex:
        result_q.put(('error', str(ex), None))


def _cancel_trino_query(query_id: str) -> bool:
    """Cancel a specific Trino query by ID.

    Args:
        query_id: The Trino query ID (e.g., '20251231_160335_08268_yxhpk')

    Returns:
        True if cancellation was successful, False otherwise
    """
    import httpx
    from pyopensky.trino import Trino
    from pyopensky.config import trino_username

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


class QueryExecutor:
    """Reusable query executor with log display, cancellation, and export."""

    def __init__(self, page: ft.Page, on_result=None, on_status=None):
        """Initialize the query executor.

        Args:
            page: Flet page for UI updates
            on_result: Callback(df) when query completes successfully
            on_status: Callback(message) for status updates
        """
        self.page = page
        self.on_result = on_result
        self.on_status = on_status

        self._cancel_flag = {"value": False}
        self._trino_query_id = None
        self._last_result = None
        self._was_cancelled = False
        self._no_data = False

        # Build UI components
        self._build_ui()

    def _build_ui(self):
        """Build the UI components."""
        # Log display
        self.log_listview = ft.ListView(
            controls=[],
            height=120,
            auto_scroll=True,
            spacing=2,
        )

        self.log_container = ft.Container(
            visible=False,
            bgcolor=ft.Colors.GREY_900,
            padding=12,
            border_radius=8,
            content=ft.Column(
                controls=[
                    ft.Text("PyOpenSky Log", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400),
                    self.log_listview,
                ],
                spacing=4,
            ),
        )

        # Status and progress
        self.progress_ring = ft.ProgressRing(visible=False, width=20, height=20)
        self.status_text = ft.Text("", size=14)

        # Cancel button
        self.cancel_btn = ft.OutlinedButton(
            "Cancel",
            icon=ft.Icons.CANCEL,
            visible=False,
            on_click=self._on_cancel_click,
        )

        # Export buttons
        self.export_row = ft.Row(visible=False, spacing=8)
        self.export_row.controls = [
            ft.FilledButton("Save CSV", icon=ft.Icons.DOWNLOAD, on_click=lambda e: self.page.run_task(self._export_csv, e)),
            ft.FilledButton("Save Parquet", icon=ft.Icons.DOWNLOAD, on_click=lambda e: self.page.run_task(self._export_parquet, e)),
        ]

    def get_controls(self) -> list:
        """Get the UI controls to add to a page layout."""
        return [
            self.log_container,
            ft.Row([self.progress_ring, self.status_text, self.cancel_btn], spacing=8),
            self.export_row,
        ]

    def add_log_line(self, text: str, color=ft.Colors.GREY_300, max_lines: int = 20):
        """Add a line to the log."""
        self.log_listview.controls.append(
            ft.Text(text, font_family="monospace", size=10, selectable=True, color=color)
        )
        if len(self.log_listview.controls) > max_lines:
            self.log_listview.controls.pop(0)
        self.page.update()

    def _on_cancel_click(self, e):
        """Handle cancel button click."""
        self._cancel_flag["value"] = True
        self.cancel_btn.disabled = True
        self.cancel_btn.text = "Cancelling..."
        self.page.update()

    def _set_status(self, message: str):
        """Update status text."""
        self.status_text.value = message
        if self.on_status:
            self.on_status(message)
        self.page.update()

    async def execute(self, params: dict):
        """Execute a query with the given parameters."""
        # Use 'spawn' to avoid fork() deadlock warnings
        ctx = mp.get_context('spawn')

        # Reset state
        self._cancel_flag["value"] = False
        self._trino_query_id = None
        self._last_result = None

        # Update UI
        self.progress_ring.visible = True
        self.cancel_btn.visible = False  # Show only after we get query ID
        self.cancel_btn.disabled = False
        self.cancel_btn.text = "Cancel"
        self.export_row.visible = False
        self._set_status("Connecting to OpenSky...")
        self.log_listview.controls.clear()
        self.log_container.visible = True
        self.page.update()

        # Start query process
        result_queue = ctx.Queue()
        log_queue = ctx.Queue()

        query_process = ctx.Process(
            target=_run_query_process,
            args=(params, result_queue, log_queue)
        )
        query_process.start()

        # Poll for updates
        cancelled = False
        result_ready = False
        result_data = None

        while query_process.is_alive() or not result_ready:
            # Check for cancellation
            if self._cancel_flag["value"] and not cancelled:
                cancelled = True
                self._set_status("Cancelling Trino query...")

                if self._trino_query_id:
                    self.add_log_line(f"Cancelling query {self._trino_query_id}...", ft.Colors.AMBER_300)
                    cancel_success = await asyncio.to_thread(_cancel_trino_query, self._trino_query_id)
                    if cancel_success:
                        self.add_log_line("Trino query cancelled", ft.Colors.GREEN_300)
                    else:
                        self.add_log_line("Failed to cancel Trino query", ft.Colors.ORANGE_300)
                else:
                    self.add_log_line("No query ID captured yet", ft.Colors.GREY_500)

                query_process.terminate()
                query_process.join(timeout=2)
                if query_process.is_alive():
                    query_process.kill()
                break

            # Process log messages
            try:
                while not log_queue.empty():
                    msg_type, msg_data = log_queue.get_nowait()
                    if msg_type == 'query_id':
                        self._trino_query_id = msg_data
                        self.cancel_btn.visible = True
                        self._set_status("Fetching data from OpenSky...")
                        self.add_log_line(f"Query ID: {self._trino_query_id}", ft.Colors.CYAN_300)
                    elif msg_type == 'progress':
                        self._set_status(msg_data.strip()[:80])
                    elif msg_type == 'line':
                        # Detect phase transitions from log messages
                        if "Saving results to" in msg_data:
                            self._set_status("Saving results to cache...")
                        elif "Preparing" in msg_data and "rows for display" in msg_data:
                            self._set_status("Preparing results...")
                        self.add_log_line(msg_data)
            except Exception:
                pass

            # Check for result (prevents deadlock - subprocess may block on put())
            try:
                if not result_ready:
                    result_data = result_queue.get_nowait()
                    result_ready = True
            except Exception:
                pass

            # If process died and we still don't have result, break
            if not query_process.is_alive() and not result_ready:
                break

            await asyncio.sleep(0.1)

        # Process result
        if cancelled:
            self._set_status("Query cancelled")
            self._last_result = None
            self._was_cancelled = True
            self._no_data = False
        elif result_data:
            try:
                status, data, columns = result_data
                if status == 'error':
                    self._set_status(f"Query failed: {data}")
                    self.add_log_line(str(data), ft.Colors.RED_300)
                    self._was_cancelled = False
                    self._no_data = False
                elif data is None:
                    self._set_status("No data found for the given parameters.")
                    self._last_result = None
                    self._was_cancelled = False
                    self._no_data = True
                else:
                    import pandas as pd
                    df = pd.DataFrame(data, columns=columns)
                    self._last_result = df
                    self._set_status(f"Retrieved {len(df):,} rows!")
                    self.export_row.visible = True
                    self._was_cancelled = False
                    self._no_data = False
                    if self.on_result:
                        self.on_result(df)
            except Exception:
                self._set_status("Query completed (no result)")
                self._was_cancelled = False
                self._no_data = False
                self._last_result = None
        else:
            self._set_status("Query completed (no result)")
            self._was_cancelled = False
            self._no_data = False
            self._last_result = None

        self.cancel_btn.visible = False
        self.progress_ring.visible = False
        self.page.update()

        return self._last_result

    async def _export_csv(self, e):
        """Export results to CSV."""
        if self._last_result is None:
            return
        default_name = f"flight_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = await ft.FilePicker().save_file(
            dialog_title="Save as CSV",
            file_name=default_name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"],
        )
        if path:
            try:
                self._last_result.to_csv(path, index=False)
                self._show_snack(f"Saved to {path}")
            except Exception as ex:
                self._show_snack(f"Error saving: {ex}")

    async def _export_parquet(self, e):
        """Export results to Parquet."""
        if self._last_result is None:
            return
        default_name = f"flight_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        path = await ft.FilePicker().save_file(
            dialog_title="Save as Parquet",
            file_name=default_name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["parquet"],
        )
        if path:
            try:
                self._last_result.to_parquet(path, index=False)
                self._show_snack(f"Saved to {path}")
            except Exception as ex:
                self._show_snack(f"Error saving: {ex}")

    def _show_snack(self, message: str):
        """Show a snackbar message."""
        self.page.snack_bar = ft.SnackBar(ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()

    def get_last_result(self):
        """Get the last query result."""
        return self._last_result

    @property
    def was_cancelled(self) -> bool:
        """Return True if the last execution was cancelled."""
        return self._was_cancelled

    @property
    def no_data(self) -> bool:
        """Return True if the last execution returned no data."""
        return self._no_data
