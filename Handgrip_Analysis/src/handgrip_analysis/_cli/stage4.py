# @package handgrip_analysis._cli.stage4
# @brief Package-native CLI entrypoint for Stage 4 analysis.

"""Entry point for ha-stage4: runs Stage 4 (grip dynamics) analysis via the package-native pipeline."""
from __future__ import annotations

import sys

from handgrip_analysis.cli import stage_main


# @brief Execute the Stage 4 CLI command.
# @param argv Optional argument vector. Uses process argv when None.
# @return None.
def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not any(arg == "--stage" or arg.startswith("--stage=") or arg.startswith("stage=") for arg in args):
        args.insert(0, "stage=stage4")
    raise SystemExit(stage_main(args))


if __name__ == "__main__":
    main()
