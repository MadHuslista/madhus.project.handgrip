# @package handgrip_analysis.io
# @brief Capture loading and sampling helper utilities.

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

TimeSource = Literal["auto", "device", "lsl", "host"]
ChannelName = Literal["raw", "current_units", "filtered"]

RAW_COLUMN = "target_raw_count"
CURRENT_UNITS_COLUMN = "target_current_units"
FILTERED_COLUMN = "target_filtered_units"
CHANNEL_COLUMN_MAP: dict[str, str] = {
    "raw": RAW_COLUMN,
    "current_units": CURRENT_UNITS_COLUMN,
    "filtered": FILTERED_COLUMN,
}


@dataclass(slots=True)
# @brief Container for a loaded capture and derived sampling metadata.
# @param path Source CSV path.
# @param df Loaded capture DataFrame.
# @param time_s Normalized monotonic time vector in seconds.
# @param fs_estimate_hz Estimated sampling frequency in Hz.
# @param time_source Name of the selected time column.
class CaptureData:
    path: Path
    df: pd.DataFrame
    time_s: np.ndarray
    fs_estimate_hz: float
    time_source: str

    # @brief Return one signal channel from the capture.
    # @param self Instance pointer.
    # @param channel Channel selector (`raw`, `current_units`, or `filtered`).
    # @return Requested channel as a float numpy array.
    # @throws KeyError Raised when requested channel is unavailable.
    def series(self, channel: ChannelName) -> np.ndarray:
        column = CHANNEL_COLUMN_MAP.get(channel)
        if column is None:
            raise KeyError(f"Unsupported channel: {channel}")
        if column not in self.df.columns:
            raise KeyError(f"CSV has no {column} column")
        return self.df[column].to_numpy(dtype=float)


REQUIRED_COLUMNS = {RAW_COLUMN}
TIME_PRIORITY = {
    "device": ["device_clock_us"],
    "lsl": ["lsl_timestamp_s"],
    "host": ["host_unix_time_ns"],
    "auto": ["device_clock_us", "lsl_timestamp_s", "host_unix_time_ns"],
}


# @brief Convert a selected time column into zero-based seconds.
# @param df Input capture DataFrame.
# @param source_col Time column name to normalize.
# @return Normalized time vector in seconds.
def _normalize_time(df: pd.DataFrame, source_col: str) -> np.ndarray:
    if source_col == "device_clock_us":
        t = df[source_col].to_numpy(dtype=float) / 1e6
    elif source_col == "host_unix_time_ns":
        t = df[source_col].to_numpy(dtype=float) / 1e9
    else:
        t = df[source_col].to_numpy(dtype=float)
    t = t - t[0]
    return t


# @brief Check whether a time vector is sufficiently monotonic.
# @param t Time vector in seconds.
# @return True when time is strictly increasing (or too short to assess).
def _is_monotonic_enough(t: np.ndarray) -> bool:
    if t.size < 3:
        return True
    dt = np.diff(t)
    return bool(np.all(dt > 0))


# @brief Estimate sampling frequency from median positive time delta.
# @param time_s Time vector in seconds.
# @return Estimated sampling frequency in Hz (NaN when unavailable).
def estimate_fs(time_s: np.ndarray) -> float:
    """Estimate sampling frequency as 1 / median(dt)."""
    if time_s.size < 2:
        log.warning("estimate_fs: fewer than 2 samples — returning NaN")
        return float("nan")
    dt = np.diff(time_s)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    if dt.size == 0:
        log.warning("estimate_fs: no valid positive dt values — returning NaN")
        return float("nan")
    return 1.0 / float(np.median(dt))


# @brief Load a CSV capture and select the best monotonic time source.
# @param path Capture CSV path.
# @param time_source Preferred time-source selection policy.
# @return CaptureData with normalized time and sampling metadata.
# @throws ValueError Raised when required signal/time columns are invalid.
def load_capture(path: str | Path, time_source: TimeSource = "auto") -> CaptureData:
    """
    Load a CSV sensor capture and select the best monotonic time column.

    Expected signal columns follow the current TargetCsvSink naming standard.
    Required: target_raw_count
    Optional: target_current_units, target_filtered_units

    The *time_source* parameter controls which column(s) are tried:
    - ``"auto"``   — try device_clock_us → lsl_timestamp_s → host_unix_time_ns
    - ``"device"`` — require device_clock_us
    - ``"lsl"``    — require lsl_timestamp_s
    - ``"host"``   — require host_unix_time_ns
    """
    path = Path(path)
    log.info("load_capture: reading %s (time_source=%r)", path, time_source)
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required signal columns in {path}: {sorted(missing)}. Expected at least {RAW_COLUMN}."
        )

    selected_col = None
    for col in TIME_PRIORITY[time_source]:
        if col in df.columns:
            t = _normalize_time(df, col)
            if _is_monotonic_enough(t):
                selected_col = col
                log.debug("load_capture: selected time column %r", col)
                break
            log.warning("load_capture: column %r is not monotonic — skipping", col)
    if selected_col is None:
        raise ValueError(f"Could not select a monotonic time source from {TIME_PRIORITY[time_source]} for {path}")

    time_s = _normalize_time(df, selected_col)
    fs = estimate_fs(time_s)
    log.info(
        "load_capture: loaded %d samples, fs=%.1f Hz, duration=%.2f s",
        len(time_s),
        fs,
        float(time_s[-1] - time_s[0]),
    )
    return CaptureData(path=path, df=df, time_s=time_s, fs_estimate_hz=fs, time_source=selected_col)


# @brief Compute descriptive sampling statistics for a time vector.
# @param time_s Time vector in seconds.
# @return Dictionary with sample count, duration, dt, and frequency stats.
def sampling_summary(time_s: np.ndarray) -> dict[str, float]:
    """Return a dict of sampling statistics for a time vector."""
    if time_s.size < 2:
        return {
            "n_samples": int(time_s.size),
            "duration_s": 0.0,
            "fs_median_hz": float("nan"),
            "dt_median_s": float("nan"),
            "dt_mean_s": float("nan"),
            "dt_std_s": float("nan"),
            "dt_min_s": float("nan"),
            "dt_max_s": float("nan"),
        }
    dt = np.diff(time_s)
    good = dt[np.isfinite(dt) & (dt > 0)]
    return {
        "n_samples": int(time_s.size),
        "duration_s": float(time_s[-1] - time_s[0]),
        "fs_median_hz": float(1.0 / np.median(good)),
        "dt_median_s": float(np.median(good)),
        "dt_mean_s": float(np.mean(good)),
        "dt_std_s": float(np.std(good)),
        "dt_min_s": float(np.min(good)),
        "dt_max_s": float(np.max(good)),
    }


# @brief Ensure a directory exists and return it as a Path.
# @param path Directory path to create.
# @return Path object pointing to the ensured directory.
def ensure_dir(path: str | Path) -> Path:
    """Create *path* (and parents) if it does not exist; return a Path object."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    log.debug("ensure_dir: %s", path)
    return path
