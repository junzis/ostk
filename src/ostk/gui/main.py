#!/usr/bin/env python
"""Standalone entry point for OSTK GUI - used for packaging."""

if __name__ == "__main__":
    # MUST be first - prevents child processes from spawning new GUI windows
    import multiprocessing
    multiprocessing.freeze_support()

    from ostk.gui.app import run_gui
    run_gui()
