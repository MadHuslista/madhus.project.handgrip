"""Entry point for ha-stage1: runs Stage 1 (startup warm-up) analysis via the package-native pipeline."""
from __future__ import annotations

import sys

from handgrip_analysis.cli import stage_main


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not any(arg == "--stage" or arg.startswith("--stage=") or arg.startswith("stage=") for arg in args):
        args.insert(0, "stage=stage1")
    raise SystemExit(stage_main(args))


if __name__ == "__main__":
    main()
