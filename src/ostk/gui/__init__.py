"""OSTK GUI module using Flet."""


def run_gui(native_mode: bool | None = None) -> None:
    """Run the OSTK GUI application.

    This is a lazy wrapper to avoid importing flet until actually needed.
    """
    from .app import run_gui as _run_gui
    _run_gui(native_mode)


__all__ = ["run_gui"]
