"""OSTK GUI module using PyWebView."""


def run_gui() -> None:
    """Run the OSTK GUI application.

    This is a lazy wrapper to avoid importing pywebview until actually needed.
    """
    from .app import run_gui as _run_gui
    _run_gui()


__all__ = ["run_gui"]
