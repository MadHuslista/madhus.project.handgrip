# @package handgrip_calibration.protocol_analysis
#  @brief Post-hoc summaries for the calibration protocol suite.
"""Post-hoc summaries for the calibration protocol suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .export import read_ndjson


def load_manifest(path: str | Path) -> dict[str, Any]:
    # @brief Load a session manifest from disk.
    #  @param path Manifest file path.
    #  @return Parsed manifest dictionary, or an empty dictionary if missing.
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def event_time(event: dict[str, Any]) -> float:
    # @brief Extract event time with LSL-time preference.
    #  @param event Marker event record.
    #  @return Event timestamp in seconds.
    if event.get("lsl_time") is not None:
        return float(event["lsl_time"])
    return float(event.get("host_time_unix", np.nan))


def read_frames(session_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    # @brief Load target/reference frames and marker events for a session.
    #  @param session_dir Session directory.
    #  @return Tuple of target frame, reference frame, and event records.
    session_dir = Path(session_dir)
    target = (
        pd.read_csv(session_dir / "target.csv")
        if (session_dir / "target.csv").exists()
        else pd.DataFrame()
    )
    reference = (
        pd.read_csv(session_dir / "reference.csv")
        if (session_dir / "reference.csv").exists()
        else pd.DataFrame()
    )
    events = read_ndjson(session_dir / "events.ndjson")
    for df in (target, reference):
        if "timestamp_lsl" in df.columns and not df.empty:
            df.sort_values("timestamp_lsl", inplace=True)
    return target, reference, events


def _value_column(df: pd.DataFrame, preferred: list[str]) -> str | None:
    for col in preferred:
        if col in df.columns:
            return col
    for col in df.columns:
        if col.startswith("channel_"):
            return col
    return None


def _window(df: pd.DataFrame, start: float, end: float) -> pd.DataFrame:
    if (
        df.empty
        or "timestamp_lsl" not in df.columns
        or not np.isfinite(start)
        or not np.isfinite(end)
    ):
        return pd.DataFrame()
    return df[(df["timestamp_lsl"] >= start) & (df["timestamp_lsl"] <= end)].copy()


def _stream_row(name: str, df: pd.DataFrame, preferred: list[str]) -> dict[str, Any]:
    if df.empty or "timestamp_lsl" not in df.columns:
        return {"stream": name, "n_samples": 0}
    t = df["timestamp_lsl"].to_numpy(dtype=float)
    duration = float(t[-1] - t[0]) if len(t) > 1 else 0.0
    gaps = np.diff(t) if len(t) > 1 else np.array([], dtype=float)
    col = _value_column(df, preferred)
    values = df[col].to_numpy(dtype=float) if col else np.array([], dtype=float)
    row = {
        "stream": name,
        "n_samples": int(len(df)),
        "duration_s": duration,
        "sample_rate_hz": float((len(df) - 1) / duration)
        if duration > 0 and len(df) > 1
        else np.nan,
        "max_gap_s": float(np.nanmax(gaps)) if len(gaps) else np.nan,
        "value_col": col,
    }
    if len(values):
        row.update(
            {
                "mean": float(np.nanmean(values)),
                "std": float(np.nanstd(values, ddof=1))
                if np.count_nonzero(np.isfinite(values)) > 1
                else 0.0,
                "min": float(np.nanmin(values)),
                "max": float(np.nanmax(values)),
            }
        )
    return row


def stream_health_table(session_dir: str | Path) -> pd.DataFrame:
    # @brief Build per-stream health metrics for a session.
    #  @param session_dir Session directory.
    #  @return DataFrame containing stream-level sampling and value statistics.
    target, reference, _ = read_frames(session_dir)
    return pd.DataFrame(
        [
            _stream_row("target", target, ["raw", "target_raw_count", "target_current_units"]),
            _stream_row("reference", reference, ["raw", "reference_force_N"]),
        ]
    )


def event_count_table(session_dir: str | Path) -> pd.DataFrame:
    # @brief Count event occurrences in a session marker log.
    #  @param session_dir Session directory.
    #  @return DataFrame of event names and counts.
    _, _, events = read_frames(session_dir)
    if not events:
        return pd.DataFrame()
    frame = pd.DataFrame(events)
    return (
        frame.groupby("event", dropna=False).size().reset_index(name="count").sort_values("event")
    )


def hold_quality_summary(dataset: pd.DataFrame) -> dict[str, Any]:
    # @brief Summarize hold-quality metrics from a calibration dataset.
    #  @param dataset Calibration hold dataset.
    #  @return Summary dictionary of accepted-hold and quality statistics.
    if dataset.empty:
        return {}
    out: dict[str, Any] = {
        "accepted_holds": int(len(dataset)),
        "quality_pass_holds": int(
            dataset.get("accepted_by_quality", pd.Series(dtype=bool)).fillna(False).sum()
        )
        if "accepted_by_quality" in dataset
        else None,
    }
    for col in [
        "reference_force_std_N",
        "reference_slope_N_s",
        "reference_sample_rate_hz",
        "target_sample_rate_hz",
        "target_seq_gap_count",
    ]:
        if col in dataset.columns:
            vals = pd.to_numeric(dataset[col], errors="coerce")
            out[f"{col}_median"] = float(vals.median()) if vals.notna().any() else np.nan
            out[f"{col}_max"] = float(vals.max()) if vals.notna().any() else np.nan
    return out


def hysteresis_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    # @brief Compare ascending and descending hold behavior by force level.
    #  @param dataset Calibration hold dataset.
    #  @return DataFrame with directional deltas for each force level.
    if (
        dataset.empty
        or "direction" not in dataset.columns
        or "target_force_nominal_N" not in dataset.columns
    ):
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for force, group in dataset.groupby("target_force_nominal_N"):
        asc = group[group["direction"].astype(str) == "ascending"]
        desc = group[group["direction"].astype(str) == "descending"]
        if asc.empty or desc.empty:
            continue
        row = {"force_N": force, "n_ascending": len(asc), "n_descending": len(desc)}
        if "target_raw_median" in group.columns:
            row["target_raw_delta_desc_minus_asc"] = float(
                desc["target_raw_median"].median() - asc["target_raw_median"].median()
            )
        if "reference_force_median_N" in group.columns:
            row["reference_force_delta_desc_minus_asc_N"] = float(
                desc["reference_force_median_N"].median() - asc["reference_force_median_N"].median()
            )
        rows.append(row)
    return pd.DataFrame(rows)


def creep_zero_return_summary(session_dir: str | Path) -> pd.DataFrame:
    # @brief Summarize creep and zero-return phases from marker windows.
    #  @param session_dir Session directory.
    #  @return DataFrame with phase durations and force trend metrics.
    _target, reference, events = read_frames(session_dir)
    if reference.empty or not events:
        return pd.DataFrame()
    ref_col = _value_column(reference, ["raw", "reference_force_N"])
    if ref_col is None:
        return pd.DataFrame()
    start_events = [
        (idx, e)
        for idx, e in enumerate(events)
        if e.get("event") in {"creep_start", "zero_return_start"}
    ]
    rows: list[dict[str, Any]] = []
    for idx, start in start_events:
        start_name = str(start.get("event"))
        end_name = "creep_end" if start_name == "creep_start" else "zero_return_end"
        end = next((e for e in events[idx + 1 :] if e.get("event") == end_name), None)
        if end is None:
            continue
        t0 = event_time(start)
        t1 = event_time(end)
        w = _window(reference, t0, t1)
        if w.empty:
            continue
        rel_t = w["timestamp_lsl"].to_numpy(dtype=float) - float(w["timestamp_lsl"].iloc[0])
        y = w[ref_col].to_numpy(dtype=float)
        slope = (
            float(np.polyfit(rel_t, y, deg=1)[0])
            if len(w) >= 2 and np.nanmax(rel_t) > 0
            else np.nan
        )
        first = _window(reference, t0, min(t1, t0 + 5.0))
        last = _window(reference, max(t0, t1 - 5.0), t1)
        rows.append(
            {
                "phase": "creep" if start_name == "creep_start" else "zero_return",
                "target_force_N": start.get("target_force_N"),
                "duration_s": float(t1 - t0),
                "n_reference_samples": int(len(w)),
                "reference_start_mean_N": float(first[ref_col].mean())
                if not first.empty
                else np.nan,
                "reference_end_mean_N": float(last[ref_col].mean()) if not last.empty else np.nan,
                "delta_end_minus_start_N": float(last[ref_col].mean() - first[ref_col].mean())
                if not first.empty and not last.empty
                else np.nan,
                "slope_N_per_s": slope,
            }
        )
    return pd.DataFrame(rows)


def dynamic_summary(session_dir: str | Path) -> pd.DataFrame:
    # @brief Summarize dynamic ramp and squeeze trial durations.
    #  @param session_dir Session directory.
    #  @return DataFrame with dynamic trial metadata and durations.
    _, _, events = read_frames(session_dir)
    if not events:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for start_name, end_name, label in [
        ("ramp_start", "ramp_end", "ramp"),
        ("squeeze_start", "squeeze_end", "squeeze"),
    ]:
        starts = [(idx, e) for idx, e in enumerate(events) if e.get("event") == start_name]
        for idx, start in starts:
            end = next((e for e in events[idx + 1 :] if e.get("event") == end_name), None)
            if end is None:
                continue
            payload = start.get("payload", {}) or {}
            rows.append(
                {
                    "trial_type": label,
                    "label": payload.get("label", label),
                    "index": payload.get("index"),
                    "duration_s": event_time(end) - event_time(start),
                    "peak_force_N": payload.get("peak_force_N"),
                    "speed_N_per_s": payload.get("speed_N_per_s"),
                }
            )
    return pd.DataFrame(rows)
