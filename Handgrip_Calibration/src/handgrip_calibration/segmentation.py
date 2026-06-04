"""Offline segmentation of accepted static calibration holds."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .config_schema import AppConfig, StreamConfig
from .export import read_ndjson
from .quality import compute_window_quality, detect_sequence_gaps, interpolate_reference_to_target
from .relaxation import (
    compute_hold_relaxation_metrics,
    direction_balanced_tail_median_dataset,
    direction_sign_matches,
    finite_median,
    shape_correlation,
    tail_frame,
)

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
    """Use LSL time when available, otherwise host UNIX time."""

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


def _manifest_stream_config(manifest: dict[str, Any], stream_key: str) -> dict[str, Any]:
    streams = manifest.get("streams", {}) if isinstance(manifest, dict) else {}
    stream = streams.get(stream_key, {}) if isinstance(streams, dict) else {}
    return stream if isinstance(stream, dict) else {}


def _candidate_to_column(candidate: str | int, df: pd.DataFrame) -> str | None:
    if isinstance(candidate, int):
        col = f"channel_{candidate}"
        return col if col in df.columns else None
    text = str(candidate)
    if text in df.columns:
        return text
    if text.isdigit():
        col = f"channel_{int(text)}"
        return col if col in df.columns else None
    return None


def _resolve_signal_column(
    df: pd.DataFrame,
    *,
    stream_key: str,
    canonical: str,
    preferred: str,
    config: AppConfig | None,
    manifest: dict[str, Any],
    critical: bool,
) -> str | None:
    """Resolve a canonical signal to an actual CSV column.

    Resolution order:
    1. exact preferred column, e.g. ``raw``;
    2. config stream channel_map candidates, e.g. ``[target_raw_count, 2]``;
    3. manifest stream channel_map candidates;
    4. exact canonical column.

    Calibration-critical signals fail loudly.  This prevents the historic bug
    where ``channel_0`` (sequence counter) was silently used as force/raw data.
    """

    candidates: list[str | int] = []
    candidates.append(preferred)
    stream_cfg: StreamConfig | None = None
    if config is not None:
        stream_cfg = config.streams.get(stream_key)
    if stream_cfg is not None:
        candidates.extend(stream_cfg.channel_map.get(canonical, []))
        if preferred != canonical:
            candidates.extend(stream_cfg.channel_map.get(preferred, []))
    manifest_stream = _manifest_stream_config(manifest, stream_key)
    manifest_map = manifest_stream.get("channel_map", {})
    if isinstance(manifest_map, dict):
        raw_candidates = manifest_map.get(canonical, [])
        if not isinstance(raw_candidates, list):
            raw_candidates = [raw_candidates]
        candidates.extend(raw_candidates)
    candidates.append(canonical)

    seen: set[str] = set()
    for candidate in candidates:
        key = repr(candidate)
        if key in seen:
            continue
        seen.add(key)
        col = _candidate_to_column(candidate, df)
        if col is not None:
            return col

    if not critical:
        return None
    available = ", ".join(str(c) for c in df.columns)
    raise SegmentationError(
        f"Could not resolve critical {stream_key}.{canonical!r} signal. "
        f"Tried candidates={candidates!r}. Available columns: {available}"
    )


def load_session_frames(
    session_dir: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
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


def _tail_quality(df: pd.DataFrame, *, value_col: str) -> tuple[float, float, int]:
    if df.empty or value_col not in df.columns:
        return float("nan"), float("nan"), 0
    values = df[value_col].to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan"), 0
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return float(np.median(values)), std, int(len(values))


def _append_artifact_outputs(
    session_dir: Path, hold_dataset: pd.DataFrame, artifact_dataset: pd.DataFrame, summary: pd.DataFrame
) -> None:
    hold_path = session_dir / "calibration_hold_dataset_raw.csv"
    summary_path = session_dir / "calibration_artifact_summary.csv"
    hold_dataset.to_csv(hold_path, index=False)
    summary.to_csv(summary_path, index=False)
    log.info("Wrote raw hold dataset before artifact correction -> %s", hold_path)
    log.info("Wrote calibration artifact summary -> %s", summary_path)
    if not artifact_dataset.empty:
        included = int(artifact_dataset.get("accepted_by_quality", pd.Series(dtype=bool)).sum())
    else:
        included = 0
    excluded = 0
    if not summary.empty and "artifact_status" in summary.columns:
        excluded = int(summary["artifact_status"].astype(str).str.startswith("excluded").sum())
    log.info(
        "Calibration artifact correction produced %d fit points from %d raw holds; excluded levels=%d",
        included,
        len(hold_dataset),
        excluded,
    )


def segment_accepted_holds(
    session_dir: str | Path, config: AppConfig | None = None
) -> pd.DataFrame:
    """Build one calibration-dataset row per accepted static hold or corrected level.

    When ``calibration_artifact.enabled`` is true, raw accepted holds are still
    written to ``calibration_hold_dataset_raw.csv``.  The returned and persisted
    ``calibration_dataset.csv`` contains direction-balanced tail-median fit
    points.  This keeps the compensation removable and auditable.
    """

    session_dir = Path(session_dir)
    target, reference, events, manifest = load_session_frames(session_dir)
    fit_cfg = config.fit if config is not None else None
    quality_cfg = config.quality if config is not None else None
    artifact_cfg = config.calibration_artifact if config is not None else None

    target_signal = fit_cfg.target_signal if fit_cfg else "raw"
    reference_signal = fit_cfg.reference_signal if fit_cfg else "raw"
    reference_scale = fit_cfg.reference_scale if fit_cfg else 1.0
    reference_offset = fit_cfg.reference_offset if fit_cfg else 0.0

    target_col = _resolve_signal_column(
        target,
        stream_key="target",
        canonical="raw",
        preferred=target_signal,
        config=config,
        manifest=manifest,
        critical=True,
    )
    ref_col = _resolve_signal_column(
        reference,
        stream_key="reference",
        canonical="raw",
        preferred=reference_signal,
        config=config,
        manifest=manifest,
        critical=True,
    )
    target_seq_col = _resolve_signal_column(
        target,
        stream_key="target",
        canonical="seq",
        preferred="seq",
        config=config,
        manifest=manifest,
        critical=False,
    )
    reference = reference.copy()
    reference["reference_force_N"] = (
        reference[ref_col].astype(float) * reference_scale + reference_offset
    )

    log.info(
        "Resolved calibration columns: target.%s -> %s; reference.%s -> %s",
        target_signal,
        target_col,
        reference_signal,
        ref_col,
    )

    accepted = _accepted_trial_ids(events)
    indexed = _index_events(events)
    if not accepted:
        raise SegmentationError("No accepted static holds found in events.ndjson")

    tail_s = 2.0
    if artifact_cfg is not None:
        tail_s = artifact_cfg.window.tail_s

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
        tw_tail = tail_frame(tw, time_col="timestamp_lsl", t_end=t1, tail_s=tail_s)
        rw_tail = tail_frame(rw, time_col="timestamp_lsl", t_end=t1, tail_s=tail_s)

        tq = compute_window_quality(tw, time_col="timestamp_lsl", value_col=target_col)
        rq = compute_window_quality(rw, time_col="timestamp_lsl", value_col="reference_force_N")
        target_tail_median, target_tail_std, target_tail_n = _tail_quality(tw_tail, value_col=target_col)
        ref_tail_median, ref_tail_std, ref_tail_n = _tail_quality(rw_tail, value_col="reference_force_N")
        target_relax = compute_hold_relaxation_metrics(
            tw, time_col="timestamp_lsl", value_col=target_col
        )
        ref_relax = compute_hold_relaxation_metrics(
            rw, time_col="timestamp_lsl", value_col="reference_force_N"
        )
        corr = shape_correlation(
            tw,
            rw,
            time_col="timestamp_lsl",
            target_col=target_col,
            reference_col="reference_force_N",
        )
        interp = interpolate_reference_to_target(
            target_times=tw["timestamp_lsl"].to_numpy(dtype=float),
            reference_times=reference["timestamp_lsl"].to_numpy(dtype=float),
            reference_values=reference["reference_force_N"].to_numpy(dtype=float),
        )
        valid_interp = interp[np.isfinite(interp)]
        seq_gaps = detect_sequence_gaps(tw[target_seq_col]) if target_seq_col else []
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
        direction = start_payload.get("direction")
        ref_sign_match = direction_sign_matches(direction, ref_relax.delta_end_minus_start)
        target_sign_match = direction_sign_matches(direction, target_relax.delta_end_minus_start)
        rows.append(
            {
                "trial_id": trial_id,
                "target_force_nominal_N": start_event.get("target_force_N"),
                "direction": direction,
                "repeat_index": start_payload.get("repeat_index"),
                "level_index": start_payload.get("level_index"),
                "t_start_lsl": t0,
                "t_end_lsl": t1,
                "duration_s": t1 - t0,
                "target_signal": target_col,
                "target_raw_mean": tq.value_mean,
                "target_raw_median": tq.value_median,
                "target_raw_std": tq.value_std,
                "target_raw_tail_median": target_tail_median,
                "target_raw_tail_std": target_tail_std,
                "target_tail_n_samples": target_tail_n,
                "target_n_samples": tq.n_samples,
                "target_sample_rate_hz": tq.sample_rate_hz,
                "target_max_gap_s": tq.max_gap_s,
                "target_seq_gap_count": len(seq_gaps),
                "reference_signal": ref_col,
                "reference_force_mean_N": rq.value_mean,
                "reference_force_median_N": rq.value_median,
                "reference_force_std_N": rq.value_std,
                "reference_force_tail_median_N": ref_tail_median,
                "reference_force_tail_std_N": ref_tail_std,
                "reference_tail_n_samples": ref_tail_n,
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
                "shape_corr_target_reference": corr,
                "reference_direction_sign_match": ref_sign_match,
                "target_direction_sign_match": target_sign_match,
                **target_relax.to_dict("target_relaxation"),
                **ref_relax.to_dict("reference_relaxation"),
                "accepted_by_operator": True,
                "accepted_by_quality": not rejection_reasons,
                "quality_rejection_reason": ";".join(rejection_reasons),
                "calibration_artifact_applied": False,
            }
        )

    if not rows:
        raise SegmentationError(
            "Accepted markers were found, but no valid hold windows could be segmented"
        )
    hold_dataset = pd.DataFrame(rows)

    if artifact_cfg is not None and artifact_cfg.enabled:
        log.info(
            "Calibration artifact compensation enabled: mode=%s, window=%s tail_s=%.3f, "
            "require_both_directions=%s, outlier=%s max_mad_z=%.3f",
            artifact_cfg.mode,
            artifact_cfg.window.source,
            artifact_cfg.window.tail_s,
            artifact_cfg.grouping.require_both_directions,
            artifact_cfg.grouping.outlier_method,
            artifact_cfg.grouping.max_mad_z,
        )
        artifact_dataset, summary = direction_balanced_tail_median_dataset(
            hold_dataset,
            target_col="target_raw_tail_median",
            reference_col="reference_force_tail_median_N",
            require_both_directions=artifact_cfg.grouping.require_both_directions,
            max_mad_z=artifact_cfg.grouping.max_mad_z,
        )
        if artifact_dataset.empty:
            raise SegmentationError(
                "Calibration artifact compensation produced no fit points. "
                "Disable calibration_artifact.enabled or inspect calibration_artifact_summary.csv."
            )
        _append_artifact_outputs(session_dir, hold_dataset, artifact_dataset, summary)
        dataset = artifact_dataset
    else:
        dataset = hold_dataset

    dataset.to_csv(session_dir / "calibration_dataset.csv", index=False)
    log.info(
        "Segmented %d accepted holds -> %s", len(dataset), session_dir / "calibration_dataset.csv"
    )
    if "shape_corr_target_reference" in hold_dataset.columns:
        median_corr = finite_median(hold_dataset["shape_corr_target_reference"])
        ref_delta = finite_median(hold_dataset["reference_relaxation_delta_end_minus_start"])
        log.info(
            "Relaxation diagnostics: median target/reference shape corr=%.3f; "
            "median reference end-start delta=%.4f N",
            median_corr,
            ref_delta,
        )
    return dataset
