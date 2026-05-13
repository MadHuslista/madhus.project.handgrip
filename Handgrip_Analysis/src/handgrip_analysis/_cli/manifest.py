"""Entry point for manifest-driven multi-trial analysis."""
from __future__ import annotations

import argparse
from pathlib import Path

from handgrip_analysis._logging import setup_logging
from handgrip_analysis.domain import StageConfig
from handgrip_analysis.pipeline import run_manifest_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run trial-aware handgrip analysis from a manifest.")
    parser.add_argument("--manifest", required=True, help="CSV manifest path")
    parser.add_argument("--stage", required=True, help="Stage to run, e.g. stage1")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--condition", default=None, help="Optional condition filter")
    parser.add_argument("--trial-type", default=None, help="Optional trial_type filter")
    parser.add_argument("--time-source", default="auto", choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--channel", default="raw")
    parser.add_argument("--filter-config", default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    setup_logging(level=args.log_level)
    cfg = StageConfig(
        stage=args.stage,
        time_source=args.time_source,
        channel=args.channel,
        channels=(args.channel,),
        filter_config=Path(args.filter_config) if args.filter_config else None,
    )
    run_manifest_analysis(
        manifest_path=args.manifest,
        stage=args.stage,
        outdir=args.outdir,
        cfg=cfg,
        condition=args.condition,
        trial_type=args.trial_type,
    )


if __name__ == "__main__":
    main()
