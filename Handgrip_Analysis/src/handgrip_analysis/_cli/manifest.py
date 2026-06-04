# @package handgrip_analysis._cli.manifest
# @brief Package-native CLI entrypoint for manifest-driven analysis.

"""Entry point for ha-run-manifest: runs manifest-driven analysis via the package-native pipeline."""

from __future__ import annotations

from handgrip_analysis.cli import stage_main


# @brief Execute the manifest CLI command.
# @param argv Optional argument vector. Uses process argv when None.
# @return None.
def main(argv: list[str] | None = None) -> None:
    raise SystemExit(stage_main(argv))


if __name__ == "__main__":
    main()
