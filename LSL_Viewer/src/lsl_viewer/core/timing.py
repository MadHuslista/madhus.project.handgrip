# @file
# @brief Timing and clock-validation utilities.
##
# All functions here are pure: they accept numpy arrays and return arrays or
# dicts. No side effects, no I/O, no logging. This makes them trivially
# unit-testable without mocking.
from __future__ import annotations

import numpy as np


def lsl_interval_ms(
    timestamps_s: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    # @brief Compute per-sample LSL inter-arrival intervals in milliseconds.
    # @param timestamps_s 1-D array of LSL timestamps in seconds.
    # @return Indices, interval values, estimated rate, and mean interval.
    ts = np.asarray(timestamps_s, dtype=np.float64)
    finite = np.isfinite(ts)
    if np.count_nonzero(finite) < 2:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            float("nan"),
            float("nan"),
        )
    idx = np.flatnonzero(finite)
    diffs_ms = np.diff(ts[idx]) * 1000.0
    valid = np.isfinite(diffs_ms) & (diffs_ms > 0)
    if not np.any(valid):
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            float("nan"),
            float("nan"),
        )
    out_idx = idx[1:][valid]
    out_dt = diffs_ms[valid]
    mean_dt_ms = float(np.nanmean(out_dt))
    rate_hz = 1000.0 / mean_dt_ms if mean_dt_ms > 0 else float("nan")
    return out_idx, out_dt, rate_hz, mean_dt_ms


def clock_interval_ms(
    clock_values: np.ndarray,
    scale_to_ms: float,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    # @brief Compute per-sample intervals from a device clock channel.
    # @param clock_values 1-D array of device clock values.
    # @param scale_to_ms Multiplication factor to convert to milliseconds.
    # @return Same four-tuple as lsl_interval_ms().
    values = np.asarray(clock_values, dtype=np.float64)
    finite = np.isfinite(values)
    if np.count_nonzero(finite) < 2:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            float("nan"),
            float("nan"),
        )
    idx = np.flatnonzero(finite)
    diffs = np.diff(values[idx]) * scale_to_ms
    valid = np.isfinite(diffs) & (diffs > 0)
    if not np.any(valid):
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            float("nan"),
            float("nan"),
        )
    out_idx = idx[1:][valid]
    out_dt = diffs[valid]
    mean_dt_ms = float(np.nanmean(out_dt))
    rate_hz = 1000.0 / mean_dt_ms if mean_dt_ms > 0 else float("nan")
    return out_idx, out_dt, rate_hz, mean_dt_ms


def clock_validation_metrics(
    lsl_timestamps_s: np.ndarray,
    clock_values: np.ndarray,
    *,
    clock_scale_to_s: float,
) -> dict[str, float]:
    # @brief Compare LSL sample timestamps against a diagnostic clock channel.
    # @param lsl_timestamps_s LSL wall-clock timestamps in seconds.
    # @param clock_values Device or board clock channel values.
    # @param clock_scale_to_s Scale factor converting clock_values to seconds.
    # @return Metrics dict with rate and drift comparisons.
    _nan_result: dict[str, float] = {
        "lsl_rate_hz": float("nan"),
        "clock_rate_hz": float("nan"),
        "median_dt_error_ms": float("nan"),
        "clock_vs_lsl_span_error_ms": float("nan"),
        "median_clock_minus_lsl_s": float("nan"),
    }

    ts = np.asarray(lsl_timestamps_s, dtype=np.float64)
    clock_s = np.asarray(clock_values, dtype=np.float64) * float(clock_scale_to_s)
    mask = np.isfinite(ts) & np.isfinite(clock_s)
    if np.count_nonzero(mask) < 2:
        return _nan_result

    ts = ts[mask]
    clock_s = clock_s[mask]
    order = np.argsort(ts)
    ts = ts[order]
    clock_s = clock_s[order]

    dt_lsl = np.diff(ts)
    dt_clock = np.diff(clock_s)
    valid_dt = np.isfinite(dt_lsl) & np.isfinite(dt_clock) & (dt_lsl > 0) & (dt_clock > 0)
    if not np.any(valid_dt):
        return _nan_result

    median_lsl_dt = float(np.nanmedian(dt_lsl[valid_dt]))
    median_clock_dt = float(np.nanmedian(dt_clock[valid_dt]))
    lsl_rate_hz = 1.0 / median_lsl_dt if median_lsl_dt > 0 else float("nan")
    clock_rate_hz = 1.0 / median_clock_dt if median_clock_dt > 0 else float("nan")
    median_dt_error_ms = (median_clock_dt - median_lsl_dt) * 1000.0
    span_error_ms = ((clock_s[-1] - clock_s[0]) - (ts[-1] - ts[0])) * 1000.0
    median_clock_minus_lsl_s = float(np.nanmedian(clock_s - ts))

    return {
        "lsl_rate_hz": lsl_rate_hz,
        "clock_rate_hz": clock_rate_hz,
        "median_dt_error_ms": median_dt_error_ms,
        "clock_vs_lsl_span_error_ms": span_error_ms,
        "median_clock_minus_lsl_s": median_clock_minus_lsl_s,
    }
