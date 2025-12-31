#!/usr/bin/env python
"""Package OSTK as a standalone executable using Flet pack (PyInstaller).

Usage:
    uv run python scripts/pack_ostk.py

This creates a standalone executable in the dist/ directory.
Uses PyInstaller for optimal compression and single-file output.

For cross-platform releases, use GitHub Actions (see .github/workflows/build-release.yml)
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def main():
    """Build the OSTK executable using flet pack."""
    project_root = get_project_root()
    system = platform.system()

    print("=" * 60)
    print("Building OSTK with Flet Pack (PyInstaller)")
    print("=" * 60)
    print(f"Platform: {system} {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")
    print()

    # Check flet CLI is available
    flet_cmd = shutil.which("flet")
    if not flet_cmd:
        # Try in virtual environment
        if system == "Windows":
            flet_cmd = project_root / ".venv" / "Scripts" / "flet.exe"
        else:
            flet_cmd = project_root / ".venv" / "bin" / "flet"

        if not Path(flet_cmd).exists():
            print("Error: flet CLI not found. Install with: uv add flet-cli")
            sys.exit(1)
        flet_cmd = str(flet_cmd)

    # Entry point
    entry_point = project_root / "src" / "ostk" / "main.py"

    # Build command using flet pack
    command = [
        flet_cmd,
        "pack",
        str(entry_point),
        "--name", "OSTK",
        "--add-data", f"{project_root / 'src' / 'ostk' / 'agent' / 'agent.md'}:ostk/agent",
        "--add-data", f"{project_root / 'assets' / 'fonts'}:assets/fonts",
        "-y",  # Non-interactive mode
    ]

    # Add icon if available
    icon_dir = project_root / "assets" / "icons"
    if system == "Windows" and (icon_dir / "ostk.ico").exists():
        command.extend(["--icon", str(icon_dir / "ostk.ico")])
    elif system == "Darwin" and (icon_dir / "ostk.icns").exists():
        command.extend(["--icon", str(icon_dir / "ostk.icns")])
    elif (icon_dir / "ostk.png").exists():
        command.extend(["--icon", str(icon_dir / "ostk.png")])

    # Change to project root
    os.chdir(project_root)

    print(f"Entry point: {entry_point}")
    print()

    # Run flet pack
    result = subprocess.run(command)

    if result.returncode == 0:
        # Show final size
        if system == "Darwin":
            output_path = project_root / "dist" / "OSTK.app"
        elif system == "Windows":
            output_path = project_root / "dist" / "OSTK.exe"
        else:
            output_path = project_root / "dist" / "OSTK"

        if output_path.exists():
            if output_path.is_file():
                size_mb = output_path.stat().st_size / (1024 * 1024)
            else:
                # For .app bundles, calculate total size
                size_mb = sum(
                    f.stat().st_size for f in output_path.rglob("*") if f.is_file()
                ) / (1024 * 1024)

            print()
            print("=" * 60)
            print("Build successful!")
            print(f"Output: {output_path}")
            print(f"Size: {size_mb:.1f} MB")
            print()
            if system == "Linux":
                print("To run: ./dist/OSTK")
            elif system == "Darwin":
                print("To run: open dist/OSTK.app")
            else:
                print(r"To run: dist\OSTK.exe")
            print("=" * 60)
    else:
        print()
        print("Build failed. Check output above for errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
