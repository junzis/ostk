#!/usr/bin/env python
"""Standalone entry point for OSTK GUI - used for packaging."""

import flet as ft


def main(page: ft.Page) -> None:
    """Main entry point for the Flet application."""
    # Import here to ensure proper module resolution when packaged
    from ostk.gui.app import main as app_main

    app_main(page)


if __name__ == "__main__":
    ft.app(main)
