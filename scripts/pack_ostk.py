#!/usr/bin/env python
"""Package OSTK as a standalone executable using PyInstaller.

Usage:
    uv run python scripts/pack_ostk.py

This creates a standalone executable in the dist/ directory.
Uses PyInstaller with exclusions for optimal bundle size.

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
    """Build the OSTK executable using PyInstaller."""
    project_root = get_project_root()
    system = platform.system()

    print("=" * 60)
    print("Building OSTK with PyInstaller")
    print("=" * 60)
    print(f"Platform: {system} {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")
    print()

    # Check pyinstaller is available
    pyinstaller_cmd = shutil.which("pyinstaller")
    if not pyinstaller_cmd:
        # Try in virtual environment
        if system == "Windows":
            pyinstaller_cmd = project_root / ".venv" / "Scripts" / "pyinstaller.exe"
        else:
            pyinstaller_cmd = project_root / ".venv" / "bin" / "pyinstaller"

        if not Path(pyinstaller_cmd).exists():
            print(
                "Error: pyinstaller not found. Install with: uv add pyinstaller --group dev"
            )
            sys.exit(1)
        pyinstaller_cmd = str(pyinstaller_cmd)

    # Spec file
    spec_file = project_root / "ostk.spec"

    if not spec_file.exists():
        print(f"Error: {spec_file} not found")
        sys.exit(1)

    # Build command
    command = [
        pyinstaller_cmd,
        str(spec_file),
        "--noconfirm",  # Overwrite without asking
    ]

    # Change to project root
    os.chdir(project_root)

    print(f"Spec file: {spec_file}")
    print()

    # Run pyinstaller
    result = subprocess.run(command)

    if result.returncode == 0:
        # Show final size
        if system == "Darwin":
            output_path = project_root / "dist" / "ostk.app"
        elif system == "Windows":
            output_path = project_root / "dist" / "ostk.exe"
        else:
            output_path = project_root / "dist" / "ostk"

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
                print("To run: ./dist/ostk")
            elif system == "Darwin":
                print("To run: open dist/ostk.app")
            else:
                print(r"To run: dist\ostk.exe")
            print("=" * 60)
    else:
        print()
        print("Build failed. Check output above for errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
