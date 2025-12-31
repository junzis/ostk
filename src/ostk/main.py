#!/usr/bin/env python
"""Standalone entry point for OSTK GUI - used for packaging."""

if __name__ == "__main__":
    # MUST be first - prevents child processes from spawning new GUI windows
    import multiprocessing
    multiprocessing.freeze_support()

    import flet as ft
    from ostk.gui.app import main as app_main, _before_main

    ft.run(app_main, before_main=_before_main)
