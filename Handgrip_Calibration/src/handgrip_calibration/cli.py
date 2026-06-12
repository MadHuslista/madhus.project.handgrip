"""Command-line interface for the Handgrip_Calibration package."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config_schema import ConfigError, load_config, resolve_session_dir
from .fitting import fit_session
from .logging_setup import configure_logging
from .lsl_io import preflight_streams
from .recorder import CalibrationRecorder
from .report import generate_report
from .segmentation import segment_accepted_holds
from .synthetic import generate_demo_session
from .validation import validate_session_against_model
from .xdf_import import import_xdf

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Subcommand handlers
# ──────────────────────────────────────────────────────────────────────────────


def _cmd_validate_config(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    log.info(
        "Config OK — protocol=%s, target_stream=%s, reference_stream=%s",
        cfg.protocol.name,
        cfg.streams["target"].name,
        cfg.streams["reference"].name,
    )
    return 0


def _cmd_preflight(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    resolved = preflight_streams(cfg.streams)
    log.info("LSL preflight OK")
    for key, meta in resolved.items():
        log.info(
            "  %s: name=%r, type=%r, channels=%d, srate=%.1f, labels=%s",
            key,
            meta.name,
            meta.stream_type,
            meta.channel_count,
            meta.nominal_srate,
            meta.channel_labels,
        )
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if args.dry_run:
        log.info(
            "[DRY-RUN] Would start %s session with protocol=%s",
            cfg.session.purpose,
            cfg.protocol.protocol_type,
        )
        return 0
    recorder = CalibrationRecorder(cfg, session_id=args.session_id, yes=args.yes)
    paths = recorder.run_protocol()
    log.info("Session recorded: %s", paths.root)
    return 0


def _cmd_segment(args: argparse.Namespace) -> int:
    cfg = load_config(args.config) if args.config else None
    session_dir = resolve_session_dir(args.session_dir)
    if args.dry_run:
        log.info("[DRY-RUN] Would segment accepted holds in %s", session_dir)
        return 0
    dataset = segment_accepted_holds(session_dir, config=cfg)
    log.info(
        "Segmented %d accepted holds -> %s",
        len(dataset),
        session_dir / "calibration_dataset.csv",
    )
    return 0


def _cmd_fit(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    session_dir = resolve_session_dir(args.session_dir)
    if args.dry_run:
        log.info("[DRY-RUN] Would fit models for session in %s", session_dir)
        return 0
    dataset, result = fit_session(session_dir, cfg)
    log.info(
        "Fit complete — %d points, model=%s", result.metrics.n_points, result.selected_model_id
    )
    log.info(
        "  family=%s, likelihood=%.3f", result.selected_model_family, result.selection_likelihood
    )
    if result.force_N_a is not None and result.force_N_b is not None:
        log.info(
            "  affine-compatible: force_N = %.12g * raw + %.12g",
            result.force_N_a,
            result.force_N_b,
        )
    log.info(
        "  RMSE=%.6g N, max_abs=%.6g N",
        result.metrics.rmse_N,
        result.metrics.max_abs_error_N,
    )
    cv_rmse = result.cv_metrics.get("cv_rmse_N")
    if cv_rmse is not None:
        log.info("  CV_RMSE=%.6g N", float(cv_rmse))
    log.info("  Wrote fit_result.json, fit_candidates.json, model_selection_report.json")
    return 0


def _cmd_validate_holdout(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    session_dir = resolve_session_dir(args.session_dir)
    result = validate_session_against_model(session_dir, args.model, cfg)
    metrics = result.get("metrics", {})
    log.info("Holdout validation complete: %s", session_dir / "holdout_validation.json")
    log.info("  selected_model=%s", result.get("selected_model_id"))
    log.info("  passes_holdout_gate=%s", result.get("passes_holdout_gate"))
    log.info(
        "  RMSE=%.4g N, max_abs=%.4g N, bias=%.4g N",
        metrics.get("rmse_N"),
        metrics.get("max_abs_error_N"),
        metrics.get("bias_N"),
    )
    log.info("  recommendation=%s", result.get("firmware_deployment_recommendation"))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    session_dir = resolve_session_dir(args.session_dir)
    if args.dry_run:
        log.info("[DRY-RUN] Would generate report for %s", session_dir)
        return 0
    path = generate_report(session_dir)
    log.info("Report written: %s", path)
    return 0


def _cmd_import_xdf(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    session_dir = resolve_session_dir(args.session_dir)
    out = import_xdf(args.xdf_path, session_dir, cfg, session_id=args.session_id)
    log.info("Imported XDF into canonical session files: %s", out)
    return 0


def _cmd_demo_data(args: argparse.Namespace) -> int:
    path = generate_demo_session(args.output, seed=args.seed)
    log.info("Demo session written: %s", path)
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────────────


def _add_common_flags(
    parser: argparse.ArgumentParser, *, dry_run: bool = False, yes: bool = False
) -> None:
    """Add shared operational flags to a subcommand parser."""
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Console log verbosity (default: INFO). File log is always DEBUG.",
    )
    if dry_run:
        parser.add_argument(
            "--dry-run",
            "-n",
            action="store_true",
            default=False,
            help="Preview what would happen without writing any files.",
        )
    if yes:
        parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            default=False,
            help="Skip interactive operator confirmation prompts (for CI/automation).",
        )


def build_parser() -> argparse.ArgumentParser:
    # @brief Build the top-level command-line parser and subcommands.
    #  @return Configured argparse parser instance.
    parser = argparse.ArgumentParser(
        prog="handgrip-cal",
        description=(
            "Calibration recorder, segmentation, fitting, and reporting "
            "for the Handgrip dual-device stack."
        ),
        epilog="""
Examples:
  # Validate a config file
  handgrip-cal validate-config --config conf/default.yaml

  # Check LSL stream availability
  handgrip-cal preflight --config conf/default.yaml

  # Record a live session (with automation bypass)
  handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml --yes

  # Preview recording without touching hardware
  handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml --dry-run

  # Segment and fit a recorded session
  handgrip-cal segment ./session_dir
  handgrip-cal fit ./session_dir --config conf/default.yaml

  # Validate a holdout session against an existing model
  handgrip-cal validate-holdout ./holdout_dir --model ./cal_dir/fit_result.json

  # Generate a complete report
  handgrip-cal report ./session_dir

  # Generate synthetic demo data (no hardware required)
  handgrip-cal demo-data --output ./demo_sessions

Exit codes:
  0  Success
  2  Configuration error / command failed
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate-config
    p = sub.add_parser("validate-config", help="Load and validate a YAML config file.")
    p.add_argument("--config", default="conf/default.yaml")
    _add_common_flags(p)
    p.set_defaults(func=_cmd_validate_config)

    # preflight
    p = sub.add_parser(
        "preflight",
        help="Resolve configured LSL streams and print their metadata.",
    )
    p.add_argument("--config", default="conf/default.yaml")
    _add_common_flags(p)
    p.set_defaults(func=_cmd_preflight)

    # record
    p = sub.add_parser(
        "record",
        help="Run the configured live recording protocol.",
    )
    p.add_argument("--config", default="conf/protocol_static_reversible_staircase_v3.yaml")
    p.add_argument("--session-id", default=None)
    _add_common_flags(p, dry_run=True, yes=True)
    p.set_defaults(func=_cmd_record)

    # segment
    p = sub.add_parser(
        "segment",
        help="Segment accepted holds and write calibration_dataset.csv.",
    )
    p.add_argument("session_dir")
    p.add_argument("--config", default="conf/default.yaml")
    _add_common_flags(p, dry_run=True)
    p.set_defaults(func=_cmd_segment)

    # fit
    p = sub.add_parser(
        "fit",
        help="Segment accepted holds, fit candidate models, and select the calibration model.",
    )
    p.add_argument("session_dir")
    p.add_argument("--config", default="conf/default.yaml")
    _add_common_flags(p, dry_run=True)
    p.set_defaults(func=_cmd_fit)

    # validate-holdout
    p = sub.add_parser(
        "validate-holdout",
        help=(
            "Validate an independent holdout session against an existing "
            "fit_result.json without refitting."
        ),
    )
    p.add_argument("session_dir")
    p.add_argument(
        "--model",
        required=True,
        help="Path to the fit_result.json produced by the primary calibration session.",
    )
    p.add_argument("--config", default="conf/protocol_holdout_verification.yaml")
    _add_common_flags(p)
    p.set_defaults(func=_cmd_validate_holdout)

    # report
    p = sub.add_parser(
        "report",
        help="Generate Markdown/HTML reports and diagnostic plots.",
    )
    p.add_argument("session_dir")
    _add_common_flags(p, dry_run=True)
    p.set_defaults(func=_cmd_report)

    # import-xdf
    p = sub.add_parser(
        "import-xdf",
        help=(
            "Convert an XDF recording into canonical target/reference CSV and events.ndjson files."
        ),
    )
    p.add_argument("xdf_path")
    p.add_argument("session_dir")
    p.add_argument("--config", default="conf/default.yaml")
    p.add_argument("--session-id", default=None)
    _add_common_flags(p)
    p.set_defaults(func=_cmd_import_xdf)

    # demo-data
    p = sub.add_parser(
        "demo-data",
        help="Generate a synthetic complete session for validation without hardware.",
    )
    p.add_argument("--output", default="./demo_sessions")
    p.add_argument("--seed", type=int, default=42)
    _add_common_flags(p)
    p.set_defaults(func=_cmd_demo_data)

    return parser


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    # @brief CLI entry point for command dispatch.
    #  @param argv Optional argument vector; when None uses process argv.
    #  @return Process exit code.
    parser = build_parser()
    args = parser.parse_args(argv)

    # Initialise logging before any command runs.
    # --log-level is added to every subcommand by _add_common_flags().
    log_level = getattr(args, "log_level", "INFO")
    configure_logging(level=log_level)

    try:
        return int(args.func(args))
    except (ConfigError, FileNotFoundError, TimeoutError, RuntimeError, ValueError) as exc:
        log.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
