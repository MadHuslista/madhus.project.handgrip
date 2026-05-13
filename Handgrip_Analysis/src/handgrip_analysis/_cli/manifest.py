"""Backward-compatible entry point for manifest-driven analysis."""
from __future__ import annotations

from handgrip_analysis.cli import stage_main


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(stage_main(argv))


if __name__ == "__main__":
    main()
