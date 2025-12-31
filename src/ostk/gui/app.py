"""Main Flet application for OSTK."""

from pathlib import Path

import flet as ft

from .state import AppState


def _get_fonts_dir() -> Path:
    """Get the fonts directory path."""
    module_dir = Path(__file__).parent.parent.parent.parent
    fonts_dir = module_dir / "assets" / "fonts"
    if fonts_dir.exists():
        return fonts_dir
    return Path("assets/fonts")


def main(page: ft.Page) -> None:
    """Main entry point for the Flet application."""
    # Configure page
    page.title = "OSTK - OpenSky ToolKit"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.width = 800
    page.window.height = 800
    page.window.min_width = 700
    page.window.min_height = 500

    # Register custom fonts (using static fonts for better rendering)
    fonts_dir = _get_fonts_dir()
    page.fonts = {
        "Noto Sans": str(fonts_dir / "NotoSans-Medium.ttf"),
    }

    # Set default font for the app
    page.theme = ft.Theme(font_family="Noto Sans")

    # Initialize state
    state = AppState()

    # Try to initialize the agent
    try:
        from ostk.agent import Agent

        state.agent = Agent()
        state.provider_name = state.agent.provider_name
        state.model_name = state.agent.llm_provider.model
    except Exception as e:
        state.error_message = str(e)
        state.agent = None

    # Import pages
    from .pages.chat_page import create_chat_page
    from .pages.query_page import create_query_page
    from .pages.settings_page import create_settings_page

    # Cache views to persist state when switching between pages
    cached_views: dict[str, ft.View] = {}

    def get_or_create_view(route: str) -> ft.View:
        """Get a cached view or create a new one."""
        if route not in cached_views:
            if route == "/settings":
                # Settings page is always recreated to reflect current state
                return create_settings_page(page, state)
            elif route == "/chat":
                cached_views[route] = create_chat_page(page, state)
            else:
                cached_views[route] = create_query_page(page, state)
        return cached_views[route]

    def route_change(e: ft.RouteChangeEvent) -> None:
        """Handle route changes."""
        page.views.clear()
        page.views.append(get_or_create_view(page.route))
        page.update()

    def view_pop(e: ft.ViewPopEvent) -> None:
        """Handle back navigation."""
        page.views.pop()
        if page.views:
            top_view = page.views[-1]
            page.route = top_view.route
            page.update()

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Build initial view directly instead of routing
    page.views.append(get_or_create_view("/"))
    page.update()


def run_gui(native_mode: bool | None = None) -> None:
    """Run the OSTK GUI application.

    Args:
        native_mode: Ignored for Flet (always native). Kept for API compatibility.
    """
    print("Starting OSTK GUI (native window)...")
    ft.run(main)


if __name__ == "__main__":
    run_gui()
