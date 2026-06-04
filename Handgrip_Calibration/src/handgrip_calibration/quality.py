"""Quality metrics for live recording and offline hold validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd


class RateMonitor:
    # @brief Rolling sample-rate estimator using recent timestamps.
    """Rolling rate estimator based on sample timestamps."""

    def __init__(self, window_s: float = 10.0) -> None:
        # @brief Initialize the rolling-rate monitor.
        #  @param self RateMonitor instance.
        #  @param window_s Time window in seconds for rate estimation.
        #  @return None.
        self.window_s = float(window_s)
        self._timestamps: list[float] = []
        self.rate_hz: float = 0.0

    def add(self, timestamp_s: float) -> None:
        # @brief Add a sample timestamp and update the estimated rate.
        #  @param self RateMonitor instance.
        #  @param timestamp_s Sample timestamp in seconds.
        #  @return None.
        self._timestamps.append(float(timestamp_s))
        cutoff = timestamp_s - self.window_s
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.pop(0)
        if len(self._timestamps) >= 2:
            duration = self._timestamps[-1] - self._timestamps[0]
            self.rate_hz = (len(self._timestamps) - 1) / duration if duration > 0 else 0.0


@dataclass(frozen=True)
class WindowQuality:
    """Quality summary for one stable/hold window."""

    n_samples: int
    duration_s: float
    sample_rate_hz: float
    max_gap_s: float
    monotonic: bool
    value_mean: float
    value_median: float
    value_std: float
    slope_per_s: float


def _as_float_array(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)]


def compute_window_quality(df: pd.DataFrame, *, time_col: str, value_col: str) -> WindowQuality:
    # @brief Compute timing and value stability metrics for a window.
    #  @param df DataFrame slice representing a hold window.
    #  @param time_col Timestamp column name.
    #  @param value_col Signal value column name.
    #  @return Structured quality metrics for the window.
    """Compute timing/stability metrics for a dataframe window."""

    if df.empty:
        return WindowQuality(0, 0.0, 0.0, 0.0, True, np.nan, np.nan, np.nan, np.nan)
    t = _as_float_array(df[time_col])
    y = _as_float_array(df[value_col])
    n = min(len(t), len(y))
    t = t[:n]
    y = y[:n]
    if n == 0:
        return WindowQuality(0, 0.0, 0.0, 0.0, True, np.nan, np.nan, np.nan, np.nan)
    dt = np.diff(t)
    duration = float(t[-1] - t[0]) if n >= 2 else 0.0
    rate = float((n - 1) / duration) if n >= 2 and duration > 0 else 0.0
    max_gap = float(np.max(dt)) if len(dt) else 0.0
    monotonic = bool(np.all(dt > 0)) if len(dt) else True
    if n >= 2 and np.ptp(t) > 0:
        # Linear trend slope is used as a stability/drift indicator. It is not a
        # calibration model; it only tells us whether a supposed static hold was
        # actually changing during the accepted interval.
        slope = float(np.polyfit(t - t[0], y, deg=1)[0])
    else:
        slope = 0.0
    return WindowQuality(
        n_samples=int(n),
        duration_s=duration,
        sample_rate_hz=rate,
        max_gap_s=max_gap,
        monotonic=monotonic,
        value_mean=float(np.mean(y)),
        value_median=float(np.median(y)),
        value_std=float(np.std(y, ddof=1)) if n > 1 else 0.0,
        slope_per_s=slope,
    )


def detect_sequence_gaps(seq: Iterable[float | int]) -> list[tuple[int, int, int]]:
    # @brief Detect discontinuities in an integer-like sequence.
    #  @param seq Sequence of sample indices.
    #  @return Tuples of row index, previous value, and current value for each gap.
    """Detect gaps in a monotonically increasing integer sequence.

    Returns `(row_index, previous, current)` tuples for each discontinuity.
    Sequence columns are optional in the current stream schema, but this function
    is ready for future firmware/IPC extensions that expose sequence numbers.
    """

    arr = pd.Series(seq).dropna().astype(int).to_numpy()
    gaps: list[tuple[int, int, int]] = []
    for i in range(1, len(arr)):
        if arr[i] != arr[i - 1] + 1:
            gaps.append((i, int(arr[i - 1]), int(arr[i])))
    return gaps


def interpolate_reference_to_target(
    *,
    target_times: np.ndarray,
    reference_times: np.ndarray,
    reference_values: np.ndarray,
) -> np.ndarray:
    # @brief Interpolate reference values at target timestamps without extrapolation.
    #  @param target_times Target stream timestamps.
    #  @param reference_times Reference stream timestamps.
    #  @param reference_values Reference signal values.
    #  @return Interpolated reference values aligned to target times.
    """Interpolate reference force values at target timestamps.

    Extrapolation is intentionally not allowed. Samples outside the reference
    time range become NaN so the segmentation layer can avoid fitting on invented
    reference values.
    """

    if len(reference_times) < 2 or len(target_times) == 0:
        return np.full_like(target_times, np.nan, dtype=float)
    values = np.interp(target_times, reference_times, reference_values)
    values[target_times < reference_times[0]] = np.nan
    values[target_times > reference_times[-1]] = np.nan
    return values
