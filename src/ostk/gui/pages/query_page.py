"""Query page for OSTK GUI - manual query builder."""

import asyncio
from datetime import datetime, timedelta, timezone

import flet as ft

from ..components import QueryExecutor
from ..state import AppState

# Available query tags with metadata
QUERY_TAGS = {
    "start": {
        "label": "start",
        "hint": "YYYY-MM-DD HH:MM:SS",
        "description": "Start time (required)",
        "required": True,
        "type": "datetime",
    },
    "stop": {
        "label": "stop",
        "hint": "YYYY-MM-DD HH:MM:SS",
        "description": "End time (defaults to 1 day after start)",
        "type": "datetime",
    },
    "icao24": {
        "label": "icao24",
        "hint": "e.g., 3c6755 or 3c6755,4840d6",
        "description": "Aircraft transponder code(s)",
        "type": "string",
    },
    "callsign": {
        "label": "callsign",
        "hint": "e.g., KLM% or DLH123",
        "description": "Flight callsign (wildcards: _ for char, % for sequence)",
        "type": "string",
    },
    "departure": {
        "label": "departure_airport",
        "hint": "4-letter ICAO, e.g., EHAM",
        "description": "Departure airport ICAO code",
        "type": "icao",
    },
    "arrival": {
        "label": "arrival_airport",
        "hint": "4-letter ICAO, e.g., EGLL",
        "description": "Arrival airport ICAO code",
        "type": "icao",
    },
    "airport": {
        "label": "airport",
        "hint": "4-letter ICAO code",
        "description": "Either departure or arrival airport",
        "type": "icao",
    },
    "serials": {
        "label": "serials",
        "hint": "e.g., 1234 or 1234,5678",
        "description": "Sensor serial number(s)",
        "type": "integer_list",
    },
    "bounds": {
        "label": "bounds",
        "hint": "west,south,east,north",
        "description": "Geographic bounds (cannot combine with airport)",
        "type": "bounds",
    },
    "limit": {
        "label": "limit",
        "hint": "e.g., 1000",
        "description": "Maximum number of rows",
        "type": "integer",
    },
}


def create_query_page(page: ft.Page, state: AppState) -> ft.View:
    """Create the query builder page."""

    def show_snack(message: str):
        """Show a snackbar message."""
        page.snack_bar = ft.SnackBar(ft.Text(message))
        page.snack_bar.open = True
        page.update()

    # Create query executor (handles log, progress, cancel, export)
    def on_query_result(df):
        state.last_result = df

    executor = QueryExecutor(page, on_result=on_query_result)

    # Track active filters
    active_filters: dict = {}

    # Container for active filter rows
    filters_column = ft.Column(spacing=6, expand=True, scroll=ft.ScrollMode.AUTO)

    # Preview area
    preview_code = ft.Text("", font_family="monospace", size=11, selectable=True)
    preview_container = ft.Container(
        visible=False,
        bgcolor=ft.Colors.GREY_900,
        padding=12,
        border_radius=8,
        content=preview_code,
    )

    # Track if preview has been shown
    preview_shown = {"value": False}

    # Execute button
    execute_btn = ft.FilledButton(
        "Execute Query",
        icon=ft.Icons.PLAY_ARROW,
        disabled=True,
        on_click=lambda e: page.run_task(handle_execute, e),
    )

    def update_filter_value(tag: str, value: str):
        """Update the value for a filter."""
        if tag in active_filters:
            active_filters[tag]["value"] = value
        preview_shown["value"] = False
        execute_btn.disabled = True
        preview_container.visible = False
        page.update()

    def remove_filter(tag: str):
        """Remove a filter from active filters."""
        if tag in active_filters:
            row = active_filters[tag]["row"]
            filters_column.controls.remove(row)
            del active_filters[tag]
            preview_shown["value"] = False
            execute_btn.disabled = True
            preview_container.visible = False
            page.update()

    def add_filter(tag: str):
        """Add a new filter row for the given tag."""
        if tag in active_filters:
            show_snack(f"'{tag}' filter already added")
            return

        tag_info = QUERY_TAGS[tag]

        def on_field_change(e, t=tag):
            value = e.control.value
            # Auto-capitalize ICAO airport codes
            if tag_info["type"] == "icao" and value:
                upper_value = value.upper()
                if upper_value != value:
                    e.control.value = upper_value
                    page.update()
                value = upper_value
            update_filter_value(t, value)

        input_field = ft.TextField(
            hint_text=tag_info["hint"],
            dense=True,
            text_size=13,
            expand=True,
            on_change=on_field_change,
        )

        filter_row = ft.Row(
            spacing=8,
            controls=[
                ft.Container(
                    width=130,
                    content=ft.Text(
                        tag_info["label"],
                        weight=ft.FontWeight.BOLD,
                        size=13,
                        color=ft.Colors.PRIMARY,
                    ),
                ),
                ft.Text("=", size=14),
                input_field,
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=18,
                    tooltip="Remove filter",
                    on_click=lambda e, t=tag: remove_filter(t),
                ),
            ],
        )

        active_filters[tag] = {"value": "", "row": filter_row, "input": input_field}
        filters_column.controls.append(filter_row)

        preview_shown["value"] = False
        execute_btn.disabled = True
        preview_container.visible = False
        page.update()

    def create_tag_chip(tag: str) -> ft.Container:
        """Create a clickable tag chip."""
        tag_info = QUERY_TAGS[tag]
        is_required = tag_info.get("required", False)

        return ft.Container(
            content=ft.TextButton(
                content=ft.Row(
                    spacing=4,
                    controls=[
                        ft.Icon(ft.Icons.ADD, size=14),
                        ft.Text(tag + ("*" if is_required else ""), size=12),
                    ],
                ),
                on_click=lambda e, t=tag: add_filter(t),
                tooltip=tag_info["description"],
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=16,
            padding=ft.Padding(4, 0, 8, 0),
        )

    def set_time_preset(preset: str):
        """Set time preset."""
        now = datetime.now(timezone.utc)

        if preset == "yesterday":
            yesterday = now - timedelta(days=1)
            start_val = yesterday.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
            stop_val = yesterday.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%d %H:%M:%S")
        elif preset == "last_week":
            # Last Monday to last Sunday
            days_since_monday = now.weekday()  # Monday=0, Sunday=6
            last_sunday = now - timedelta(days=days_since_monday + 1)
            last_monday = last_sunday - timedelta(days=6)
            start_val = last_monday.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
            stop_val = last_sunday.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%d %H:%M:%S")
        elif preset == "last_hour":
            # Last complete hour (e.g., if 14:35, then 13:00:00 to 13:59:59)
            last_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            start_val = last_hour.strftime("%Y-%m-%d %H:%M:%S")
            stop_val = last_hour.replace(minute=59, second=59).strftime("%Y-%m-%d %H:%M:%S")
        else:
            return

        if "start" not in active_filters:
            add_filter("start")
        active_filters["start"]["input"].value = start_val
        active_filters["start"]["value"] = start_val

        if "stop" not in active_filters:
            add_filter("stop")
        active_filters["stop"]["input"].value = stop_val
        active_filters["stop"]["value"] = stop_val

        preview_shown["value"] = False
        execute_btn.disabled = True
        preview_container.visible = False
        page.update()

    def clear_all_filters(e):
        """Clear all active filters."""
        active_filters.clear()
        filters_column.controls.clear()
        preview_shown["value"] = False
        execute_btn.disabled = True
        preview_container.visible = False
        page.update()

    def get_params_from_filters() -> dict:
        """Build params dict from active filters."""
        params = {}
        for tag, data in active_filters.items():
            value = data["value"].strip()
            if value:
                tag_info = QUERY_TAGS[tag]
                param_name = tag_info["label"]

                if tag_info["type"] == "integer":
                    try:
                        params[param_name] = int(value)
                    except ValueError:
                        pass
                elif tag_info["type"] == "integer_list":
                    try:
                        values = [int(v.strip()) for v in value.split(",")]
                        params[param_name] = values if len(values) > 1 else values[0]
                    except ValueError:
                        pass
                elif tag_info["type"] == "bounds":
                    try:
                        values = [float(v.strip()) for v in value.split(",")]
                        if len(values) == 4:
                            params[param_name] = tuple(values)
                    except ValueError:
                        pass
                else:
                    params[param_name] = value

        return params

    def handle_preview(e):
        """Show preview of generated query."""
        if not state.agent:
            show_snack("Agent not configured")
            return

        params = get_params_from_filters()
        if not params:
            show_snack("No filters set")
            return

        if not params.get("start"):
            show_snack("'start' filter is required")
            return

        state.current_params.update_from_dict(params)

        code = state.agent.build_history_call(params)
        preview_code.value = code
        preview_code.color = ft.Colors.WHITE
        preview_container.visible = True
        preview_shown["value"] = True
        execute_btn.disabled = False
        page.update()

    async def handle_execute(e):
        """Execute the query using QueryExecutor."""
        if not preview_shown["value"]:
            show_snack("Please preview the query first")
            return

        if not state.agent:
            show_snack("Agent not configured")
            return

        params = get_params_from_filters()
        if not params.get("start"):
            show_snack("'start' filter is required")
            return

        # Disable execute button during execution
        execute_btn.disabled = True
        page.update()

        try:
            await executor.execute(params)
        except asyncio.CancelledError:
            pass
        finally:
            execute_btn.disabled = False
            page.update()

    # Build tag chips
    tag_chips = ft.Row(
        wrap=True,
        spacing=6,
        run_spacing=6,
        controls=[create_tag_chip(tag) for tag in QUERY_TAGS.keys()],
    )

    # Time presets
    time_presets = ft.Column(
        spacing=4,
        controls=[
            ft.Text("Quick time presets:", size=12, color=ft.Colors.GREY_600),
            ft.Row(
                wrap=True,
                spacing=4,
                run_spacing=4,
                controls=[
                    ft.TextButton("Last Hour", on_click=lambda e: set_time_preset("last_hour")),
                    ft.TextButton("Yesterday", on_click=lambda e: set_time_preset("yesterday")),
                    ft.TextButton("Last Week", on_click=lambda e: set_time_preset("last_week")),
                ],
            ),
        ],
    )

    # Page content
    content = ft.Container(
        padding=16,
        expand=True,
        content=ft.Row(
            expand=True,
            spacing=16,
            controls=[
                # Left panel: Available tags
                ft.Container(
                    width=200,
                    alignment=ft.Alignment(-1, -1),
                    content=ft.Column(
                        spacing=12,
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            ft.Text("Available Filters", size=14, weight=ft.FontWeight.BOLD),
                            ft.Text("Click to add filter:", size=11, color=ft.Colors.GREY_600),
                            tag_chips,
                            ft.Divider(height=1),
                            time_presets,
                        ],
                    ),
                ),
                ft.VerticalDivider(width=1),
                # Right panel: Active filters and preview
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(-1, -1),
                    content=ft.Column(
                        expand=True,
                        spacing=8,
                        scroll=ft.ScrollMode.AUTO,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("Active Filters", size=14, weight=ft.FontWeight.BOLD),
                                    ft.TextButton("Clear All", on_click=clear_all_filters),
                                ],
                            ),
                            ft.Container(
                                bgcolor=ft.Colors.SURFACE_CONTAINER,
                                border_radius=8,
                                padding=12,
                                content=filters_column,
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                spacing=8,
                                controls=[
                                    ft.OutlinedButton(
                                        "Preview",
                                        icon=ft.Icons.VISIBILITY,
                                        on_click=handle_preview,
                                    ),
                                    execute_btn,
                                ],
                            ),
                            preview_container,
                            # Query executor controls (log, status, cancel, export)
                            *executor.get_controls(),
                        ],
                    ),
                ),
            ],
        ),
    )

    return ft.View(
        route="/",
        padding=0,
        appbar=ft.AppBar(
            title=ft.Text("OSTK - Query Builder"),
            center_title=False,
            automatically_imply_leading=False,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[
                ft.FilledTonalButton("Query", icon=ft.Icons.TABLE_CHART, disabled=True),
                ft.OutlinedButton("AI Chat", icon=ft.Icons.CHAT, on_click=lambda e: page.run_task(page.push_route, "/chat")),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    tooltip="Settings",
                    on_click=lambda e: page.run_task(page.push_route, "/settings"),
                ),
            ],
        ),
        controls=[content],
    )
