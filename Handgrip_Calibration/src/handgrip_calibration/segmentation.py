"""Offline segmentation of accepted static calibration holds."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .config_schema import AppConfig
from .export import read_ndjson
from .quality import compute_window_quality, detect_sequence_gaps, interpolate_reference_to_target

log = logging.getLogger(__name__)


class SegmentationError(RuntimeError):
    """Raised when a session cannot be segmented into calibration holds."""


def _load_manifest(session_dir: Path) -> dict[str, Any]:
    path = session_dir / "session_manifest.yaml"
    if not path.exists():
        raise SegmentationError(f"Missing session manifest: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _event_time(event: dict[str, Any]) -> float:
    """Use LSL time when available, otherwise host UNIX time.

    Live CSV recording uses LSL timestamps. Synthetic/demo data and some manual
    workflows may use host_time_unix. Using this helper consistently keeps the
    segmenter tolerant to both cases.
    """

    if event.get("lsl_time") is not None:
        return float(event["lsl_time"])
    return float(event["host_time_unix"])


def _index_events(events: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    for event in events:
        trial_id = event.get("trial_id")
        event_name = event.get("event")
        if not trial_id or not event_name:
            continue
        indexed.setdefault(str(trial_id), {})[str(event_name)] = event
    return indexed


def _accepted_trial_ids(events: list[dict[str, Any]]) -> set[str]:
    accepted: set[str] = set()
    rejected: set[str] = set()
    for event in events:
        trial_id = event.get("trial_id")
        if not trial_id:
            continue
        if event.get("event") == "trial_accept":
            accepted.add(str(trial_id))
        elif event.get("event") == "trial_reject":
            rejected.add(str(trial_id))
    return accepted - rejected


def _canonical_value(df: pd.DataFrame, preferred: str, fallback: str = "raw") -> str:
    if preferred in df.columns:
        return preferred
    if fallback in df.columns:
        return fallback
    candidates = [c for c in df.columns if c.startswith("channel_")]
    if candidates:
        return candidates[0]
    raise SegmentationError(f"Could not find signal column {preferred!r} or fallback {fallback!r}")


def load_session_frames(
    session_dir: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    # @brief Load target/reference frames, events, and manifest for a session.
    #  @param session_dir Session directory path.
    #  @return Tuple of target frame, reference frame, events list, and manifest dictionary.
    """Load target/reference CSVs, events, and manifest from a session directory."""

    session_dir = Path(session_dir)
    target_csv = session_dir / "target.csv"
    reference_csv = session_dir / "reference.csv"
    if not target_csv.exists() or not reference_csv.exists():
        raise SegmentationError(f"Missing target/reference CSV files under {session_dir}")
    target = pd.read_csv(target_csv)
    reference = pd.read_csv(reference_csv)
    events = read_ndjson(session_dir / "events.ndjson")
    manifest = _load_manifest(session_dir)
    for name, df in [("target", target), ("reference", reference)]:
        if "timestamp_lsl" not in df.columns:
            raise SegmentationError(f"{name}.csv must contain timestamp_lsl")
        df.sort_values("timestamp_lsl", inplace=True)
        df.drop_duplicates(subset=["timestamp_lsl"], inplace=True)
    return target, reference, events, manifest


def segment_accepted_holds(
    session_dir: str | Path, config: AppConfig | None = None
) -> pd.DataFrame:
    # @brief Build calibration rows from accepted static hold windows.
    #  @param session_dir Session directory path.
    #  @param config Optional application config for fit/quality thresholds.
    #  @return DataFrame with one row per segmented accepted hold.
    """Build one calibration-dataset row per accepted static hold."""

    session_dir = Path(session_dir)
    target, reference, events, manifest = load_session_frames(session_dir)
    fit_cfg = config.fit if config is not None else None
    quality_cfg = config.quality if config is not None else None

    target_signal = fit_cfg.target_signal if fit_cfg else "raw"
    reference_signal = fit_cfg.reference_signal if fit_cfg else "raw"
    reference_scale = fit_cfg.reference_scale if fit_cfg else 1.0
    reference_offset = fit_cfg.reference_offset if fit_cfg else 0.0

    target_col = _canonical_value(target, target_signal)
    ref_col = _canonical_value(reference, reference_signal)
    reference = reference.copy()
    reference["reference_force_N"] = (
        reference[ref_col].astype(float) * reference_scale + reference_offset
    )

    accepted = _accepted_trial_ids(events)
    indexed = _index_events(events)
    if not accepted:
        raise SegmentationError("No accepted static holds found in events.ndjson")

    rows: list[dict[str, Any]] = []
    for trial_id in sorted(accepted):
        trial_events = indexed.get(trial_id, {})
        if "hold_start" not in trial_events or "hold_end" not in trial_events:
            continue
        start_event = (
            trial_events["stable_window_start"]
            if "stable_window_start" in trial_events
            else trial_events["hold_start"]
        )
        end_event = trial_events["hold_end"]
        t0 = _event_time(start_event)
        t1 = _event_time(end_event)
        if t1 <= t0:
            continue
        tw = target[(target["timestamp_lsl"] >= t0) & (target["timestamp_lsl"] <= t1)].copy()
        rw = reference[
            (reference["timestamp_lsl"] >= t0) & (reference["timestamp_lsl"] <= t1)
        ].copy()
        tq = compute_window_quality(tw, time_col="timestamp_lsl", value_col=target_col)
        rq = compute_window_quality(rw, time_col="timestamp_lsl", value_col="reference_force_N")
        interp = interpolate_reference_to_target(
            target_times=tw["timestamp_lsl"].to_numpy(dtype=float),
            reference_times=reference["timestamp_lsl"].to_numpy(dtype=float),
            reference_values=reference["reference_force_N"].to_numpy(dtype=float),
        )
        valid_interp = interp[np.isfinite(interp)]
        seq_gaps = detect_sequence_gaps(tw["seq"]) if "seq" in tw.columns else []
        rejection_reasons: list[str] = []
        if quality_cfg is not None:
            if tq.n_samples < quality_cfg.min_hold_target_samples:
                rejection_reasons.append("too_few_target_samples")
            if rq.n_samples < quality_cfg.min_hold_reference_samples:
                rejection_reasons.append("too_few_reference_samples")
            if rq.max_gap_s > quality_cfg.reference_max_gap_s:
                rejection_reasons.append("reference_gap_exceeds_threshold")
            if abs(rq.slope_per_s) > quality_cfg.max_hold_reference_slope_N_per_s:
                rejection_reasons.append("reference_slope_exceeds_threshold")
            if rq.value_std > quality_cfg.max_hold_reference_std_N:
                rejection_reasons.append("reference_std_exceeds_threshold")
            if seq_gaps:
                rejection_reasons.append("target_sequence_gap")
        start_payload = trial_events.get("hold_start", {}).get("payload", {}) or {}
        rows.append(
            {
                "trial_id": trial_id,
                "target_force_nominal_N": start_event.get("target_force_N"),
                "direction": start_payload.get("direction"),
                "repeat_index": start_payload.get("repeat_index"),
                "level_index": start_payload.get("level_index"),
                "t_start_lsl": t0,
                "t_end_lsl": t1,
                "duration_s": t1 - t0,
                "target_signal": target_col,
                "target_raw_mean": tq.value_mean,
                "target_raw_median": tq.value_median,
                "target_raw_std": tq.value_std,
                "target_n_samples": tq.n_samples,
                "target_sample_rate_hz": tq.sample_rate_hz,
                "target_max_gap_s": tq.max_gap_s,
                "target_seq_gap_count": len(seq_gaps),
                "reference_signal": ref_col,
                "reference_force_mean_N": rq.value_mean,
                "reference_force_median_N": rq.value_median,
                "reference_force_std_N": rq.value_std,
                "reference_n_samples": rq.n_samples,
                "reference_sample_rate_hz": rq.sample_rate_hz,
                "reference_max_gap_s": rq.max_gap_s,
                "reference_slope_N_s": rq.slope_per_s,
                "reference_interpolated_to_target_mean_N": float(np.nanmean(valid_interp))
                if len(valid_interp)
                else np.nan,
                "reference_interpolated_to_target_median_N": float(np.nanmedian(valid_interp))
                if len(valid_interp)
                else np.nan,
                "accepted_by_operator": True,
                "accepted_by_quality": not rejection_reasons,
                "quality_rejection_reason": ";".join(rejection_reasons),
            }
        )

    if not rows:
        raise SegmentationError(
            "Accepted markers were found, but no valid hold windows could be segmented"
        )
    dataset = pd.DataFrame(rows)
    dataset.to_csv(session_dir / "calibration_dataset.csv", index=False)
    log.info(
        "Segmented %d accepted holds -> %s", len(dataset), session_dir / "calibration_dataset.csv"
    )
    return dataset
