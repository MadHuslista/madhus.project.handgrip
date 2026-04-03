from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

TimeSource = Literal["auto", "device", "lsl", "host"]
ChannelName = Literal["raw", "filtered", "value_raw", "value_filtered"]


@dataclass(slots=True)
class CaptureData:
    path: Path
    df: pd.DataFrame
    time_s: np.ndarray
    fs_estimate_hz: float
    time_source: str

    def series(self, channel: ChannelName) -> np.ndarray:
        if channel in {"raw", "value_raw"}:
            return self.df["value_raw"].to_numpy(dtype=float)
        if channel in {"filtered", "value_filtered"}:
            if "value_filtered" not in self.df.columns:
                raise KeyError("CSV has no value_filtered column")
            return self.df["value_filtered"].to_numpy(dtype=float)
        raise KeyError(f"Unsupported channel: {channel}")


REQUIRED_COLUMNS = {"value_raw"}
TIME_PRIORITY = {
    "device": ["device_clock_us"],
    "lsl": ["lsl_timestamp_s"],
    "host": ["host_unix_time_ns"],
    "auto": ["device_clock_us", "lsl_timestamp_s", "host_unix_time_ns"],
}


def _normalize_time(df: pd.DataFrame, source_col: str) -> np.ndarray:
    if source_col == "device_clock_us":
        t = df[source_col].to_numpy(dtype=float) / 1e6
    elif source_col == "host_unix_time_ns":
        t = df[source_col].to_numpy(dtype=float) / 1e9
    else:
        t = df[source_col].to_numpy(dtype=float)
    t = t - t[0]
    return t


def _is_monotonic_enough(t: np.ndarray) -> bool:
    if t.size < 3:
        return True
    dt = np.diff(t)
    return np.all(dt > 0)


def estimate_fs(time_s: np.ndarray) -> float:
    if time_s.size < 2:
        return float("nan")
    dt = np.diff(time_s)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    if dt.size == 0:
        return float("nan")
    return 1.0 / float(np.median(dt))


def load_capture(path: str | Path, time_source: TimeSource = "auto") -> CaptureData:
    path = Path(path)
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")

    selected_col = None
    for col in TIME_PRIORITY[time_source]:
        if col in df.columns:
            t = _normalize_time(df, col)
            if _is_monotonic_enough(t):
                selected_col = col
                break
    if selected_col is None:
        raise ValueError(
            f"Could not select a monotonic time source from {TIME_PRIORITY[time_source]} for {path}"
        )

    time_s = _normalize_time(df, selected_col)
    fs = estimate_fs(time_s)
    return CaptureData(path=path, df=df, time_s=time_s, fs_estimate_hz=fs, time_source=selected_col)


def sampling_summary(time_s: np.ndarray) -> dict[str, float]:
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


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
