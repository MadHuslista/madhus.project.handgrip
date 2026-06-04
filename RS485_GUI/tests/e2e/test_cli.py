"""End-to-end CLI tests.

Verifies the entry point and importability without requiring NiceGUI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class TestCliEntryPoint:
    # <repo>/RS485_GUI/tests/e2e/test_cli.py
    cwd = Path(__file__).parent.parent.parent.absolute()

    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "rs485_gui", "--help"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": "src"},
            cwd=self.cwd,
        )
        assert result.returncode == 0, result.stderr
        assert "Usage" in result.stdout

    def test_package_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", "import rs485_gui; print(rs485_gui.__version__)"],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": "src"},
            cwd=self.cwd,
        )
        assert result.returncode == 0, result.stderr
        assert "0.1.0" in result.stdout

    def test_config_loader_loads_via_cli(self):
        """Verify config loads without NiceGUI (loader has no UI dependency)."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from rs485_gui.config.loader import load_app_config; "
                "cfg = load_app_config([]); "
                "print(cfg.ui.port)",
            ],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": "src"},
            cwd=self.cwd,
        )
        assert result.returncode == 0, result.stderr
        assert "8088" in result.stdout
