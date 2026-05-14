"""
Replay data loading for CSV and XDF modes.

These functions load data from disk and return pure ``DualReplayData`` values.
The I/O boundary is kept thin: all validation and transformation after loading
is expressed as pure numpy/pandas operations.

Dead code removed vs. original
-------------------------------
* ``_candidate_columns()`` — was never exercised with actual fallbacks; every
  call site passed a single-element list.  Replaced by direct
  ``_pick_existing_column`` calls.
* Legacy fused-CSV replay — already removed prior to this refactor (confirmed
  by comment in original source).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from hydra.utils import to_absolute_path
from omegaconf import DictConfig

from lsl_viewer.types import DualReplayData, DualWindow, ReferenceWindow, TargetWindow

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def optional_path(value: str | None) -> Path | None:
    """Resolve a config path string to an absolute Path, or return None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(to_absolute_path(text))


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _pick_existing_column(columns: list[str], candidates: list[str], role: str) -> str:
    """Return the first candidate column that exists, or raise."""
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise RuntimeError(
        f"Could not find a column for {role}. "
        f"Candidates={candidates}; available={columns}"
    )


def _extract_numeric(df: pd.DataFrame, col: str) -> np.ndarray:
    return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=np.float64)


def _time_from_df(
    df: pd.DataFrame, preferred: list[str], expected_rate_hz: float
) -> np.ndarray:
    """
    Derive a timestamp array from a DataFrame.

    Prefers columns in *preferred* order.  Handles ``_ns`` and ``_us`` suffixes
    for unit conversion.  Falls back to a synthetic uniform grid.
    """
    cols = list(df.columns)
    for col in preferred:
        if col in cols:
            values = _extract_numeric(df, col)
            if col.endswith("_ns"):
                return values * 1e-9
            if col.endswith("_us"):
                return values * 1e-6
            return values
    return np.arange(len(df), dtype=np.float64) / float(expected_rate_hz)


# ---------------------------------------------------------------------------
# XDF helpers
# ---------------------------------------------------------------------------

def _first_scalar(value: Any) -> Any:
    """Recursively unwrap a nested list to its first scalar element."""
    if isinstance(value, list) and value:
        return _first_scalar(value[0])
    return value


def extract_xdf_labels(info: dict[str, Any]) -> list[str] | None:
    """Extract channel labels from an XDF stream info dict."""
    desc = info.get("desc", [{}])
    labels: list[str] = []
    if desc and isinstance(desc, list):
        channels_root = desc[0].get("channels", [{}])
        if channels_root and isinstance(channels_root, list):
            channel_items = channels_root[0].get("channel", [])
            for channel in channel_items:
                label = _first_scalar(channel.get("label"))
                if label is not None:
                    labels.append(str(label))
    return labels or None


def _extract_xdf_time_series(stream: dict[str, Any]) -> np.ndarray:
    ts = np.asarray(stream.get("time_series"), dtype=np.float64)
    if ts.ndim == 1:
        ts = ts[:, np.newaxis]
    if ts.ndim != 2:
        raise RuntimeError(f"Unsupported XDF time_series shape: {ts.shape}")
    return ts


def _extract_xdf_timestamps(stream: dict[str, Any]) -> np.ndarray:
    stamps = np.asarray(stream.get("time_stamps"), dtype=np.float64).reshape(-1)
    if stamps.size == 0:
        raise RuntimeError("XDF stream contains no timestamps")
    if stamps.size >= 2 and np.any(np.diff(stamps) < 0):
        raise RuntimeError("XDF timestamps are not monotonic increasing")
    return stamps


def _indices_from_labels(labels: list[str], required: list[str], role: str) -> list[int]:
    indices: list[int] = []
    for label in required:
        if label not in labels:
            raise RuntimeError(
                f"{role} XDF stream labels do not contain {label!r}. labels={labels}"
            )
        indices.append(labels.index(label))
    return indices


def _select_xdf_stream(
    streams: list[dict[str, Any]],
    name: str,
    stype: str,
    source_id: str | None,
) -> dict[str, Any]:
    matches = [
        s for s in streams
        if (
            _first_scalar(s.get("info", {}).get("name")) == name
            and _first_scalar(s.get("info", {}).get("type")) == stype
            and (
                source_id is None
                or _first_scalar(s.get("info", {}).get("source_id")) == source_id
            )
        )
    ]
    if not matches:
        raise RuntimeError(
            f"No XDF stream matched name={name!r} stype={stype!r} source_id={source_id!r}"
        )
    if len(matches) > 1:
        log.warning("Multiple XDF streams matched for %s; using the first one.", name)
    return matches[0]


# ---------------------------------------------------------------------------
# Common timebase normalisation
# ---------------------------------------------------------------------------

def normalize_common_timebases(
    target_ts: np.ndarray, reference_ts: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Shift both timestamp arrays so the earlier start is t=0."""
    starts: list[float] = []
    if target_ts.size:
        starts.append(float(target_ts[0]))
    if reference_ts.size:
        starts.append(float(reference_ts[0]))
    t0 = min(starts) if starts else 0.0
    return target_ts - t0, reference_ts - t0


# ---------------------------------------------------------------------------
# Window extraction from pre-loaded replay data
# ---------------------------------------------------------------------------

def window_from_replay(
    data: DualReplayData, elapsed_s: float, window_seconds: float
) -> DualWindow | None:
    """Slice a DualWindow from replay data at the given playback position."""
    start_s = max(0.0, float(elapsed_s) - float(window_seconds))
    target_mask = (data.target_timestamps_s >= start_s) & (
        data.target_timestamps_s <= elapsed_s
    )
    reference_mask = (data.reference_timestamps_s >= start_s) & (
        data.reference_timestamps_s <= elapsed_s
    )
    target = None
    reference = None
    if np.any(target_mask):
        target = TargetWindow(
            timestamps_s=data.target_timestamps_s[target_mask],
            device_clock_us=data.target_device_clock_us[target_mask],
            raw=data.target_raw[target_mask],
            filtered=data.target_filtered[target_mask],
        )
    if np.any(reference_mask):
        reference = ReferenceWindow(
            timestamps_s=data.reference_timestamps_s[reference_mask],
            rs485_clock=data.reference_clock_s[reference_mask],
            raw=data.reference_raw[reference_mask],
        )
    if target is None and reference is None:
        return None
    return DualWindow(target=target, reference=reference)


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def load_csv_replay(cfg: DictConfig) -> DualReplayData:
    """
    Load dual native CSV replay files produced by LSL_Bridge v2.

    Expects two separate CSVs — one for the target (handgrip) stream and one
    for the reference (RS485) stream — as set in ``reference.target_csv_path``
    and ``reference.reference_csv_path``.

    Legacy fused-CSV replay was removed in the calibration-schema upgrade.
    """
    target_path = optional_path(cfg.reference.target_csv_path)
    reference_path = optional_path(cfg.reference.reference_csv_path)
    if target_path is None or reference_path is None:
        raise RuntimeError(
            "mode=csv_replay requires reference.target_csv_path "
            "and reference.reference_csv_path"
        )

    target_df = pd.read_csv(target_path)
    reference_df = pd.read_csv(reference_path)
    if target_df.empty or reference_df.empty:
        raise RuntimeError("CSV replay source is empty")

    target_cols = list(target_df.columns)
    reference_cols = list(reference_df.columns)

    target_clock = _pick_existing_column(
        target_cols, [str(cfg.channels.target.clock_label)], "target clock"
    )
    target_raw = _pick_existing_column(
        target_cols, [str(cfg.channels.target.raw_label)], "target raw"
    )
    target_filtered = _pick_existing_column(
        target_cols, [str(cfg.channels.target.filtered_label)], "target filtered"
    )
    ref_clock = _pick_existing_column(
        reference_cols, [str(cfg.channels.reference.clock_label)], "reference clock"
    )
    ref_raw = _pick_existing_column(
        reference_cols, [str(cfg.channels.reference.raw_label)], "reference force"
    )

    target_ts = _time_from_df(
        target_df, ["lsl_timestamp_s"], cfg.viewer.expected_target_rate_hz
    )
    reference_ts = _time_from_df(
        reference_df, ["lsl_timestamp_s"], cfg.streams.reference.expected_rate_hz
    )
    target_ts, reference_ts = normalize_common_timebases(target_ts, reference_ts)

    log.info(
        "CSV replay loaded: target=%s (%d rows) reference=%s (%d rows)",
        target_path.name,
        len(target_df),
        reference_path.name,
        len(reference_df),
    )

    return DualReplayData(
        target_timestamps_s=target_ts,
        target_device_clock_us=_extract_numeric(target_df, target_clock),
        target_raw=_extract_numeric(target_df, target_raw),
        target_filtered=_extract_numeric(target_df, target_filtered),
        reference_timestamps_s=reference_ts,
        reference_clock_s=_extract_numeric(reference_df, ref_clock),
        reference_raw=_extract_numeric(reference_df, ref_raw),
        source_name=f"{target_path.name} + {reference_path.name}",
        source_type="csv_replay_dual_native_v2",
        target_labels=[target_clock, target_raw, target_filtered],
        reference_labels=[ref_clock, ref_raw],
    )


def load_xdf_replay(cfg: DictConfig) -> DualReplayData:
    """Load a dual-stream XDF file for replay."""
    xdf_path = optional_path(cfg.reference.xdf_path)
    if xdf_path is None:
        raise RuntimeError("mode=xdf_replay requires reference.xdf_path")

    try:
        import pyxdf  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "mode=xdf_replay requires pyxdf. "
            "Install it with: pip install lsl-viewer[xdf]"
        ) from exc

    streams, header = pyxdf.load_xdf(str(xdf_path), dejitter_timestamps=False)
    log.info(
        "XDF replay loaded: %s | header keys=%s | streams=%d",
        xdf_path,
        list(header.keys()),
        len(streams),
    )

    target_stream = _select_xdf_stream(
        streams,
        str(cfg.streams.target.name),
        str(cfg.streams.target.stype),
        None if cfg.streams.target.source_id is None else str(cfg.streams.target.source_id),
    )
    reference_stream = _select_xdf_stream(
        streams,
        str(cfg.streams.reference.name),
        str(cfg.streams.reference.stype),
        None
        if cfg.streams.reference.source_id is None
        else str(cfg.streams.reference.source_id),
    )

    target_labels = extract_xdf_labels(target_stream.get("info", {})) or [
        str(cfg.channels.target.clock_label),
        str(cfg.channels.target.raw_label),
        str(cfg.channels.target.filtered_label),
    ]
    reference_labels = extract_xdf_labels(reference_stream.get("info", {})) or [
        str(cfg.channels.reference.clock_label),
        str(cfg.channels.reference.raw_label),
    ]

    target_matrix = _extract_xdf_time_series(target_stream)
    reference_matrix = _extract_xdf_time_series(reference_stream)
    target_ts = _extract_xdf_timestamps(target_stream)
    reference_ts = _extract_xdf_timestamps(reference_stream)
    target_ts, reference_ts = normalize_common_timebases(target_ts, reference_ts)

    target_idx = _indices_from_labels(
        target_labels,
        [
            str(cfg.channels.target.clock_label),
            str(cfg.channels.target.raw_label),
            str(cfg.channels.target.filtered_label),
        ],
        "Target",
    )
    reference_idx = _indices_from_labels(
        reference_labels,
        [
            str(cfg.channels.reference.clock_label),
            str(cfg.channels.reference.raw_label),
        ],
        "Reference",
    )

    return DualReplayData(
        target_timestamps_s=target_ts,
        target_device_clock_us=target_matrix[:, target_idx[0]],
        target_raw=target_matrix[:, target_idx[1]],
        target_filtered=target_matrix[:, target_idx[2]],
        reference_timestamps_s=reference_ts,
        reference_clock_s=reference_matrix[:, reference_idx[0]],
        reference_raw=reference_matrix[:, reference_idx[1]],
        source_name=xdf_path.name,
        source_type="xdf_replay_dual_native",
        target_labels=[target_labels[i] for i in target_idx],
        reference_labels=[reference_labels[i] for i in reference_idx],
    )
