#!/usr/bin/env python3
"""
Run pytest across all submodule packages independently.

This script enables each submodule to use its own pytest configuration
while still allowing a single command to test everything from the repo root.

Usage:
    python pytest_all.py              # Run all tests with verbose output
    python pytest_all.py -v           # Verbose mode
    python pytest_all.py --cov        # Include coverage reports
    python pytest_all.py -x           # Stop on first failure
    python pytest_all.py --help       # See all options
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SUBMODULES = [
    "RS485_GUI",
    "LSL_Bridge",
    "Handgrip_Calibration",
    "Handgrip_Analysis",
    "LSL_Viewer",
]


def run_tests_for_submodule(submodule: str, args: list[str], python_exe: str) -> int:
    """
    Run pytest for a single submodule with its own pyproject.toml config.
    
    Args:
        submodule: Name of the submodule directory
        args: Additional arguments to pass to pytest
        python_exe: Path to Python executable to use (from venv)
    
    Returns:
        Exit code from pytest

    """
    submodule_path = Path(__file__).parent / submodule
    pyproject = submodule_path / "pyproject.toml"

    if not pyproject.exists():
        print(f"⚠️  Skipping {submodule}: no pyproject.toml found")
        return 0

    tests_dir = submodule_path / "tests"
    if not tests_dir.exists():
        print(f"⚠️  Skipping {submodule}: no tests directory found")
        return 0

    print(f"\n{'=' * 70}")
    print(f"Running tests for {submodule}")
    print(f"{'=' * 70}")

    cmd = [
        python_exe,
        "-m",
        "pytest",
        "-c",
        str(pyproject),
        "-v",
        *args,
    ]

    result = subprocess.run(cmd, check=False, cwd=submodule_path)
    return result.returncode


def main() -> int:
    """Run tests for all submodules and report overall status."""
    # Find the venv Python executable
    repo_root = Path(__file__).parent
    venv_python = repo_root / ".venv" / "bin" / "python"

    if not venv_python.exists():
        print(f"Error: Could not find virtual environment at {venv_python}")
        print("Please ensure the venv is set up at <repo_root>/.venv")
        return 1

    # Filter out --help and similar flags to pass to subcommand
    args = [arg for arg in sys.argv[1:] if arg not in ["-h", "--help"]]

    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return 0

    exit_codes = []
    for submodule in SUBMODULES:
        exit_code = run_tests_for_submodule(submodule, args, str(venv_python))
        exit_codes.append((submodule, exit_code))

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")

    all_passed = True
    for submodule, exit_code in exit_codes:
        status = "✅ PASSED" if exit_code == 0 else "❌ FAILED"
        print(f"{submodule:30} {status}")
        if exit_code != 0:
            all_passed = False

    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    print("\n❌ Some tests failed. Review output above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
