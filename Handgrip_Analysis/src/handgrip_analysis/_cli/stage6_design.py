"""Entry point: ha-stage6-design."""
from __future__ import annotations
import runpy, sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "stage6_filter_design.py"

def main() -> None:
    sys.argv[0] = str(_SCRIPT)
    runpy.run_path(str(_SCRIPT), run_name="__main__")
