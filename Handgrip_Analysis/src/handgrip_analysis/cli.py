"""
Package-native command-line interface for handgrip-analysis.

The CLI intentionally keeps side effects at the boundary:

1. Parse and normalize arguments.
2. Build a typed :class:`StageConfig`.
3. Ask :mod:`handgrip_analysis.pipeline` to validate, plan, execute, and write.

It accepts conventional flags and the project-friendly ``key=value`` style used
by Hydra, without depending on Hydra for the Phase 2 package entry points.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from ._logging import setup_logging
from .domain import HandgripAnalysisError, StageConfig
from .manifest import load_manifest
from .pipeline import run_manifest_analysis

log = logging.getLogger(__name__)

_STAGE_ALIASES = {
    "1": "stage1",
    "2": "stage2",
    "3": "stage3",
    "4": "stage4",
    "5": "stage5",
    "6": "stage6",
    "stage6_design": "stage6",
    "stage6_review": "stage6",
}


def normalize_stage(stage: str) -> str:
    """Normalize stage aliases to registry names."""
    text = str(stage).strip()
    if not text:
        raise ValueError("stage must not be empty")
    lowered = text.lower()
    if lowered in _STAGE_ALIASES:
        return _STAGE_ALIASES[lowered]
    if lowered.startswith("stage"):
        return lowered
    if lowered.isdigit():
        return f"stage{lowered}"
    return lowered


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    lowered = text.lower()
    if lowered in {"null", "none"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if text.startswith("[") and text.endswith("]"):
        try:
            return yaml.safe_load(text)
        except Exception:
            inner = text[1:-1].strip()
            return [] if not inner else [_parse_scalar(part) for part in inner.split(",")]
    try:
        if any(ch in text for ch in (".", "e", "E")):
            return float(text)
        return int(text)
    except ValueError:
        return text


def _set_nested(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    cursor = target
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        nested = cursor.setdefault(part, {})
        if not isinstance(nested, dict):
            nested = {}
            cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = value


def parse_key_value_args(items: Iterable[str]) -> dict[str, Any]:
    """Parse Hydra-style ``key=value`` overrides into a nested mapping."""
    parsed: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"Expected key=value override, got {item!r}")
        key, raw_value = item.split("=", 1)
        if not key:
            raise argparse.ArgumentTypeError(f"Expected non-empty key in override {item!r}")
        _set_nested(parsed, key, _parse_scalar(raw_value))
    return parsed


def _pop_value(name: str, namespace: argparse.Namespace, overrides: dict[str, Any], default: Any = None) -> Any:
    value = getattr(namespace, name, None)
    if value is not None:
        return value
    return overrides.get(name, default)


def _nested_get(mapping: Mapping[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    cursor: Any = mapping
    for part in path:
        if not isinstance(cursor, Mapping) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor


def _stage_config_from_cli(stage: str, args: argparse.Namespace, overrides: dict[str, Any]) -> StageConfig:
    """Build typed stage config after all CLI input has been normalized."""
    stage_overrides = dict(overrides.get("analysis", {}) if isinstance(overrides.get("analysis"), Mapping) else {})
    # Support the Phase 1 config additions too.
    aggregation = overrides.get("aggregation", {}) if isinstance(overrides.get("aggregation"), Mapping) else {}
    trials = overrides.get("trials", {}) if isinstance(overrides.get("trials"), Mapping) else {}
    global_stage_block = overrides.get(stage, {}) if isinstance(overrides.get(stage), Mapping) else {}

    merged: dict[str, Any] = {}
    merged.update(stage_overrides)
    merged.update(global_stage_block)

    for src_key, dst_key in [
        ("confidence_level", "confidence_level"),
        ("bootstrap_resamples", "bootstrap_resamples"),
        ("random_seed", "random_seed"),
    ]:
        if src_key in aggregation:
            merged[dst_key] = aggregation[src_key]
    for src_key, dst_key in [
        ("min_trials_allowed", "min_trials_allowed"),
        ("min_trials_recommended", "min_trials_recommended"),
    ]:
        if src_key in trials:
            merged[dst_key] = trials[src_key]

    # Conventional flags take highest precedence.
    if args.time_source is not None:
        merged["time_source"] = args.time_source
    if args.channel is not None:
        merged["channel"] = args.channel
        merged.setdefault("channels", (args.channel,))
    if args.channels is not None:
        merged["channels"] = tuple(ch.strip() for ch in args.channels.split(",") if ch.strip())
    if args.filter_config is not None:
        merged["filter_config"] = args.filter_config
    elif "filter_config" in overrides:
        merged["filter_config"] = overrides["filter_config"]
    elif stage == "stage6" and "filter_config" not in merged:
        default_filter = Path("conf/filters/candidates.yaml")
        if default_filter.exists():
            merged["filter_config"] = str(default_filter)

    if getattr(args, "lsl_bridge_root", None) is not None:
        merged["lsl_bridge_root"] = args.lsl_bridge_root
    elif "lsl_bridge_root" in overrides:
        merged["lsl_bridge_root"] = overrides["lsl_bridge_root"]
    if getattr(args, "lsl_bridge_config", None) is not None:
        merged["lsl_bridge_config"] = args.lsl_bridge_config
    elif "lsl_bridge_config" in overrides:
        merged["lsl_bridge_config"] = overrides["lsl_bridge_config"]
    if getattr(args, "stage_context_manifest", None) is not None:
        merged["stage_context_manifest"] = args.stage_context_manifest
    elif "stage_context_manifest" in overrides:
        merged["stage_context_manifest"] = overrides["stage_context_manifest"]

    if "composite_weights" in merged and "filter_weights" not in merged:
        merged["filter_weights"] = merged.pop("composite_weights")

    return StageConfig.from_mapping(stage=stage, data=merged)


def build_stage_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ha-stage",
        description="Run one manifest-driven handgrip analysis stage.",
        epilog=(
            "Examples:\n"
            "  ha-stage stage=stage2 manifest=data/calibration_manifest.csv outdir=data/analysis_results/stage2\n"
            "  ha-stage --stage stage4 --manifest data/calibration_manifest.csv --outdir data/analysis_results/stage4 --condition fast_max\n"
            "  ha-stage stage=stage6 manifest=data/calibration_manifest.csv outdir=data/analysis_results/stage6 filter_config=conf/filters/candidates.yaml"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("overrides", nargs="*", help="Optional key=value overrides, e.g. stage=stage2 manifest=... outdir=...")
    parser.add_argument("--stage", default=None, help="Stage to run, e.g. stage1 ... stage6")
    parser.add_argument("--manifest", default=None, help="Trial manifest CSV path")
    parser.add_argument("--outdir", default=None, help="Output directory")
    parser.add_argument("--condition", default=None, help="Optional condition filter")
    parser.add_argument("--trial-type", dest="trial_type", default=None, help="Optional trial_type filter")
    parser.add_argument("--time-source", dest="time_source", default=None, choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--channel", default=None)
    parser.add_argument("--channels", default=None, help="Comma-separated channel list for stages that support multiple channels")
    parser.add_argument("--filter-config", dest="filter_config", default=None)
    parser.add_argument("--lsl-bridge-root", dest="lsl_bridge_root", default=None)
    parser.add_argument("--lsl-bridge-config", dest="lsl_bridge_config", default=None)
    parser.add_argument("--stage-context-manifest", dest="stage_context_manifest", default=None)
    parser.add_argument("--log-level", default=None)
    return parser


def stage_main(argv: list[str] | None = None) -> int:
    parser = build_stage_parser()
    args = parser.parse_args(argv)
    overrides = parse_key_value_args(args.overrides)

    stage = _pop_value("stage", args, overrides)
    manifest = _pop_value("manifest", args, overrides)
    outdir = _pop_value("outdir", args, overrides)
    condition = _pop_value("condition", args, overrides)
    trial_type = _pop_value("trial_type", args, overrides)
    log_level = _pop_value("log_level", args, overrides, _nested_get(overrides, ("logging", "level"), "INFO"))

    missing = [name for name, value in {"stage": stage, "manifest": manifest, "outdir": outdir}.items() if value in (None, "")]
    if missing:
        parser.error("Missing required argument(s): " + ", ".join(missing))

    stage = normalize_stage(str(stage))
    setup_logging(level=str(log_level))
    try:
        cfg = _stage_config_from_cli(stage, args, overrides)
        paths = run_manifest_analysis(
            manifest_path=manifest,
            stage=stage,
            outdir=outdir,
            cfg=cfg,
            condition=condition,
            trial_type=trial_type,
        )
    except HandgripAnalysisError as exc:
        log.error("ha-stage failed: %s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
        log.exception("ha-stage failed unexpectedly: %s", exc)
        return 1

    log.info("ha-stage complete: wrote %d artifact(s) under %s", len(paths), outdir)
    return 0


def build_run_all_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ha-run-all",
        description="Run all stages represented in a trial manifest through the package-native pipeline.",
    )
    parser.add_argument("overrides", nargs="*", help="Optional key=value overrides, e.g. manifest=... base_outdir=...")
    parser.add_argument("--manifest", default=None, help="Trial manifest CSV path")
    parser.add_argument("--base-outdir", dest="base_outdir", default=None, help="Base output directory")
    parser.add_argument("--stages", default=None, help="Comma-separated stages to run; default: all stages present in manifest")
    parser.add_argument("--time-source", dest="time_source", default=None, choices=["auto", "device", "lsl", "host"])
    parser.add_argument("--channel", default=None)
    parser.add_argument("--channels", default=None)
    parser.add_argument("--filter-config", dest="filter_config", default=None)
    parser.add_argument("--lsl-bridge-root", dest="lsl_bridge_root", default=None)
    parser.add_argument("--lsl-bridge-config", dest="lsl_bridge_config", default=None)
    parser.add_argument("--stage-context-manifest", dest="stage_context_manifest", default=None)
    parser.add_argument("--log-level", default=None)
    return parser


def _stages_from_manifest(manifest: str | Path) -> list[str]:
    trials = load_manifest(manifest)
    stages = sorted({normalize_stage(t.stage) for t in trials})
    return stages


def run_all_main(argv: list[str] | None = None) -> int:
    parser = build_run_all_parser()
    args = parser.parse_args(argv)
    overrides = parse_key_value_args(args.overrides)

    manifest = _pop_value("manifest", args, overrides, _nested_get(overrides, ("trials", "manifest")))
    base_outdir = _pop_value("base_outdir", args, overrides, "data/analysis_results")
    stages_raw = _pop_value("stages", args, overrides)
    log_level = _pop_value("log_level", args, overrides, _nested_get(overrides, ("logging", "level"), "INFO"))

    if manifest in (None, ""):
        parser.error("Missing required argument: manifest")

    setup_logging(level=str(log_level))
    try:
        if stages_raw:
            stages = [normalize_stage(part.strip()) for part in str(stages_raw).split(",") if part.strip()]
        else:
            stages = _stages_from_manifest(manifest)

        completed: dict[str, dict[str, str]] = {}
        for stage in stages:
            stage_outdir = Path(base_outdir) / stage
            cfg = _stage_config_from_cli(stage, args, overrides)
            paths = run_manifest_analysis(
                manifest_path=manifest,
                stage=stage,
                outdir=stage_outdir,
                cfg=cfg,
            )
            completed[stage] = {k: str(v) for k, v in paths.items()}
    except HandgripAnalysisError as exc:
        log.error("ha-run-all failed: %s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
        log.exception("ha-run-all failed unexpectedly: %s", exc)
        return 1

    log.info("ha-run-all complete: ran %d stage(s)", len(completed))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Default CLI entry, equivalent to ``ha-stage``."""
    return stage_main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
