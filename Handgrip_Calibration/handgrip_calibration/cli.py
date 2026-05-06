"""Command-line interface for the Handgrip_Calibration package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config_schema import ConfigError, load_config
from .fitting import fit_session
from .lsl_io import preflight_streams
from .recorder import CalibrationRecorder
from .report import generate_report
from .segmentation import segment_accepted_holds
from .synthetic import generate_demo_session
from .xdf_import import import_xdf


def _cmd_validate_config(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(f"OK: config loaded. Protocol={cfg.protocol.name}, target_stream={cfg.streams['target'].name}, reference_stream={cfg.streams['reference'].name}")
    return 0


def _cmd_preflight(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    resolved = preflight_streams(cfg.streams)
    print("LSL preflight OK")
    for key, meta in resolved.items():
        print(f"- {key}: name={meta.name!r}, type={meta.stream_type!r}, channels={meta.channel_count}, nominal_srate={meta.nominal_srate}, labels={meta.channel_labels}")
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    recorder = CalibrationRecorder(cfg, session_id=args.session_id)
    paths = recorder.run_static_staircase()
    print(f"Session recorded: {paths.root}")
    return 0


def _cmd_segment(args: argparse.Namespace) -> int:
    cfg = load_config(args.config) if args.config else None
    dataset = segment_accepted_holds(args.session_dir, config=cfg)
    print(f"Segmented {len(dataset)} accepted holds -> {Path(args.session_dir) / 'calibration_dataset.csv'}")
    return 0


def _cmd_fit(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    dataset, result = fit_session(args.session_dir, cfg)
    print(f"Fit complete using {result.metrics.n_points} points")
    print(f"selected_model={result.selected_model_id} ({result.selected_model_family})")
    if result.force_N_a is not None and result.force_N_b is not None:
        print(f"affine-compatible force_N = {result.force_N_a:.12g} * raw + {result.force_N_b:.12g}")
    print(f"RMSE={result.metrics.rmse_N:.6g} N, max_abs={result.metrics.max_abs_error_N:.6g} N")
    cv_rmse = result.cv_metrics.get('cv_rmse_N')
    if cv_rmse is not None:
        print(f"CV_RMSE={float(cv_rmse):.6g} N")
    print(f"model_likelihood={result.selection_likelihood:.3f}")
    print(f"Wrote {Path(args.session_dir) / 'fit_result.json'}")
    print(f"Wrote {Path(args.session_dir) / 'fit_candidates.json'}")
    print(f"Wrote {Path(args.session_dir) / 'model_selection_report.json'}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    path = generate_report(args.session_dir)
    print(f"Report written: {path}")
    return 0


def _cmd_import_xdf(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    out = import_xdf(args.xdf_path, args.session_dir, cfg, session_id=args.session_id)
    print(f"Imported XDF into canonical session files: {out}")
    return 0


def _cmd_demo_data(args: argparse.Namespace) -> int:
    path = generate_demo_session(args.output, seed=args.seed)
    print(f"Demo session written: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handgrip-cal",
        description="Calibration recorder, segmentation, fitting, and reporting for the Handgrip dual-device stack.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-config", help="Load and validate a YAML config file.")
    p.add_argument("--config", default="conf/default.yaml")
    p.set_defaults(func=_cmd_validate_config)

    p = sub.add_parser("preflight", help="Resolve configured LSL streams and print their metadata.")
    p.add_argument("--config", default="conf/default.yaml")
    p.set_defaults(func=_cmd_preflight)

    p = sub.add_parser("record", help="Run the configured live static-staircase recording protocol.")
    p.add_argument("--config", default="conf/protocol_static_staircase.yaml")
    p.add_argument("--session-id", default=None)
    p.set_defaults(func=_cmd_record)

    p = sub.add_parser("segment", help="Segment accepted holds and write calibration_dataset.csv.")
    p.add_argument("session_dir")
    p.add_argument("--config", default="conf/default.yaml")
    p.set_defaults(func=_cmd_segment)

    p = sub.add_parser("fit", help="Segment accepted holds, fit candidate models, and select the calibration model.")
    p.add_argument("session_dir")
    p.add_argument("--config", default="conf/default.yaml")
    p.set_defaults(func=_cmd_fit)

    p = sub.add_parser("report", help="Generate Markdown/HTML reports and diagnostic plots.")
    p.add_argument("session_dir")
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("import-xdf", help="Convert an XDF recording into canonical target/reference CSV and events.ndjson files.")
    p.add_argument("xdf_path")
    p.add_argument("session_dir")
    p.add_argument("--config", default="conf/default.yaml")
    p.add_argument("--session-id", default=None)
    p.set_defaults(func=_cmd_import_xdf)

    p = sub.add_parser("demo-data", help="Generate a synthetic complete session for validation without hardware.")
    p.add_argument("--output", default="./demo_sessions")
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(func=_cmd_demo_data)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ConfigError, FileNotFoundError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
