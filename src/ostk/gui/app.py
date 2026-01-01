"""PyWebView-based GUI for OSTK."""

import sys
from pathlib import Path

import webview

from .api import Api


def get_web_dir() -> Path:
    """Get the web assets directory."""
    # When running from source
    source_path = Path(__file__).parent / "web"
    if source_path.exists():
        return source_path

    # When running from PyInstaller bundle
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        return bundle_dir / "ostk" / "gui" / "web"

    return source_path


def get_icon_path() -> str:
    """Get the application icon path."""
    # When running from source
    source_path = Path(__file__).parent.parent.parent.parent / "assets" / "icons" / "ostk.png"
    if source_path.exists():
        return str(source_path)

    # When running from PyInstaller bundle
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        icon_path = bundle_dir / "assets" / "icons" / "ostk.png"
        if icon_path.exists():
            return str(icon_path)

    return ""


def run_gui() -> None:
    """Launch the PyWebView GUI."""
    api = Api()
    web_dir = get_web_dir()

    # Create window
    window = webview.create_window(
        title="OSTK - OpenSky ToolKit",
        url=str(web_dir / "index.html"),
        js_api=api,
        width=800,
        height=800,
        min_size=(700, 500),
    )

    # Set window reference for file dialogs
    api.set_window(window)

    # Start the webview
    webview.start(debug=False)


if __name__ == "__main__":
    run_gui()
