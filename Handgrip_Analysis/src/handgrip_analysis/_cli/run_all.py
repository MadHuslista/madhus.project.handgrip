# @package handgrip_analysis._cli.run_all
# @brief Package-native CLI entrypoint for running all manifest stages.

"""Entry point for ha-run-all: runs all stages in a manifest via the package-native pipeline."""

from __future__ import annotations

from handgrip_analysis.cli import run_all_main


# @brief Execute the run-all CLI command.
# @param argv Optional argument vector. Uses process argv when None.
# @return None.
def main(argv: list[str] | None = None) -> None:
    raise SystemExit(run_all_main(argv))


if __name__ == "__main__":
    main()
