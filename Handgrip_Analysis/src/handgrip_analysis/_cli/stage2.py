# @package handgrip_analysis._cli.stage2
# @brief Package-native CLI entrypoint for Stage 2 analysis.

"""Entry point for ha-stage2: runs Stage 2 (static noise) analysis via the package-native pipeline."""
from __future__ import annotations

import sys

from handgrip_analysis.cli import stage_main


# @brief Execute the Stage 2 CLI command.
# @param argv Optional argument vector. Uses process argv when None.
# @return None.
def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not any(arg == "--stage" or arg.startswith("--stage=") or arg.startswith("stage=") for arg in args):
        args.insert(0, "stage=stage2")
    raise SystemExit(stage_main(args))


if __name__ == "__main__":
    main()
