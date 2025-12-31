"""Chat page for OSTK GUI - LLM-assisted query interface."""

import asyncio
from datetime import datetime

import flet as ft

from ..components import QueryExecutor
from ..state import AppState


def create_chat_page(page: ft.Page, state: AppState) -> ft.View:
    """Create the chat page."""

    def show_snack(message: str):
        """Show a snackbar message."""
        page.snack_bar = ft.SnackBar(ft.Text(message))
        page.snack_bar.open = True
        page.update()

    chat_list = ft.ListView(
        expand=True,
        spacing=8,
        padding=12,
        auto_scroll=True,
    )

    chat_input = ft.TextField(
        hint_text="Ask about flight data... (Shift+Enter to send)",
        expand=True,
        multiline=True,
        min_lines=1,
        max_lines=4,
        border_radius=8,
        shift_enter=True,  # Shift+Enter sends, Enter creates new line
        on_submit=lambda e: page.run_task(handle_send, e),
    )

    chat_progress = ft.ProgressRing(visible=False, width=20, height=20)

    def create_message_bubble(
        name: str,
        content: str,
        is_user: bool = False,
        is_code: bool = False,
        is_error: bool = False,
        params: dict | None = None,
    ) -> ft.Container:
        """Create a chat message bubble with optional execute button for code."""

        # Create a fresh executor for each code message
        local_executor = None
        execute_btn = None

        if is_code:
            # Each code bubble gets its own executor
            def on_result(df):
                state.last_result = df
                # Don't call refresh_chat() - it would destroy the executor with its export buttons

            local_executor = QueryExecutor(page, on_result=on_result)

        async def execute_code(e):
            """Execute the query from chat using QueryExecutor."""
            if not state.agent or not params or not local_executor:
                show_snack("Cannot execute - missing agent or parameters")
                return

            if not params.get("start") or not params.get("stop"):
                show_snack("Start and Stop times are required")
                return

            # Disable input and execute button during execution
            chat_input.disabled = True
            if execute_btn:
                execute_btn.disabled = True
            page.update()

            try:
                result = await local_executor.execute(params)

                if result is None:
                    if local_executor.was_cancelled:
                        state.add_message("assistant", "Query was cancelled.", "error")
                        refresh_chat()
                    elif local_executor.no_data:
                        state.add_message("assistant", "No data found for the given parameters.", "error")
                        refresh_chat()
                    # else: error already shown by executor, no refresh needed
                # Success case: executor already updated UI with export buttons, no refresh needed
            except asyncio.CancelledError:
                # Task was cancelled (e.g., user navigated away)
                return
            finally:
                # Re-enable input (guard against destroyed session)
                try:
                    chat_input.disabled = False
                    if execute_btn:
                        execute_btn.disabled = False
                    page.update()
                except RuntimeError:
                    # Session was destroyed, ignore
                    return

        if is_code:
            execute_btn = ft.FilledTonalButton(
                "Execute",
                icon=ft.Icons.PLAY_ARROW,
                on_click=lambda e: page.run_task(execute_code, e),
            )
            text_content = ft.Column(
                spacing=8,
                controls=[
                    ft.Container(
                        bgcolor=ft.Colors.GREY_900,
                        padding=8,
                        border_radius=6,
                        content=ft.Text(
                            content,
                            font_family="monospace",
                            size=11,
                            selectable=True,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                    ft.Row(controls=[execute_btn]),
                    # Each code message has its own executor controls
                    *local_executor.get_controls(),
                ],
            )
        else:
            text_content = ft.Markdown(
                content,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            )

        return ft.Container(
            margin=ft.Margin(
                left=40 if is_user else 0,
                top=0,
                right=0 if is_user else 40,
                bottom=0,
            ),
            padding=8,
            bgcolor=(
                ft.Colors.BLUE_100 if is_user
                else ft.Colors.RED_100 if is_error
                else ft.Colors.SURFACE_CONTAINER_HIGHEST
            ),
            border_radius=8,
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Text(name, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600),
                    text_content,
                ],
            ),
        )

    def refresh_chat():
        """Refresh the chat display."""
        chat_list.controls.clear()

        if not state.messages:
            chat_list.controls.append(
                create_message_bubble(
                    "OSTK",
                    "**Welcome to OSTK Chat!** I can help you query flight data from OpenSky.\n\n"
                    "Try asking something like:\n"
                    "- *Get all flights from Amsterdam to London yesterday*\n"
                    "- *Show me aircraft 3c6755 on December 15, 2024*\n"
                    "- *Flights departing EGLL in the last hour*",
                    is_user=False,
                )
            )
        else:
            for msg in state.messages:
                params = state.current_params.to_dict() if msg.msg_type == "code" else None
                chat_list.controls.append(
                    create_message_bubble(
                        "You" if msg.role == "user" else "OSTK",
                        msg.content,
                        is_user=(msg.role == "user"),
                        is_code=(msg.msg_type == "code"),
                        is_error=(msg.msg_type == "error"),
                        params=params,
                    )
                )

        page.update()

    async def handle_send(e):
        """Handle sending a chat message."""
        message = chat_input.value.strip()
        if not message:
            return

        chat_input.value = ""
        page.update()

        if not state.agent:
            state.add_message("assistant", "Please configure your LLM provider in Settings first.", "error")
            refresh_chat()
            return

        state.add_message("user", message)
        refresh_chat()

        chat_progress.visible = True
        page.update()

        try:
            params = await asyncio.to_thread(state.agent.parse_query, message)
            state.current_params.update_from_dict(params)

            code = state.agent.build_history_call(params)
            state.add_message("assistant", "I've parsed your query. Click **Execute** to run it:")
            state.add_message("assistant", code, "code")

        except Exception as ex:
            state.add_message("assistant", f"Error parsing query: {ex}", "error")

        chat_progress.visible = False
        refresh_chat()

    def clear_chat(e):
        """Clear chat history."""
        state.messages.clear()
        refresh_chat()

    refresh_chat()

    # Chat content
    content = ft.Container(
        padding=16,
        expand=True,
        content=ft.Column(
            expand=True,
            spacing=8,
            controls=[
                ft.Container(
                    expand=True,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=8,
                    padding=8,
                    content=chat_list,
                ),
                ft.Row(
                    controls=[
                        chat_input,
                        chat_progress,
                        ft.IconButton(
                            icon=ft.Icons.SEND,
                            tooltip="Send",
                            on_click=lambda e: page.run_task(handle_send, e),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Clear chat",
                            on_click=clear_chat,
                        ),
                    ],
                ),
            ],
        ),
    )

    # Model info chip (shown after title)
    model_chip = ft.Chip(
        label=ft.Text(
            f"{state.provider_name}: {state.model_name}"
            if state.agent
            else "Not Configured"
        ),
        bgcolor=ft.Colors.GREEN_900 if state.agent else ft.Colors.AMBER_900,
    )

    return ft.View(
        route="/chat",
        padding=0,
        appbar=ft.AppBar(
            title=ft.Row(
                controls=[
                    ft.Text("OSTK - Chat"),
                    model_chip,
                ],
                spacing=12,
            ),
            center_title=False,
            automatically_imply_leading=False,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[
                ft.OutlinedButton("Query", icon=ft.Icons.TABLE_CHART, on_click=lambda e: page.run_task(page.push_route, "/")),
                ft.FilledTonalButton("AI Chat", icon=ft.Icons.CHAT, disabled=True),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    tooltip="Settings",
                    on_click=lambda e: page.run_task(page.push_route, "/settings"),
                ),
            ],
        ),
        controls=[content],
    )
