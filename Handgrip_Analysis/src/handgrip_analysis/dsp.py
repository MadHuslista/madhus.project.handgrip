# @package handgrip_analysis.dsp
# @brief Pure DSP functions for handgrip sensor signal analysis.

"""
DSP functions for handgrip sensor signal analysis.

All functions in this module are **pure** — they have no file I/O or
side effects and can be tested without mocking.

Named Constants
---------------
The following module-level constants replace anonymous inline literals.
They serve as fallback defaults when callers do not supply a
:class:`~handgrip_analysis.config.DSPConfig`.

.. list-table::
   :header-rows: 1

   * - Constant
     - Value
     - Meaning
   * - ``MAD_CONSISTENCY_CONSTANT``
     - 1.4826
     - Scales MAD to a consistent standard-deviation estimator (Gaussian)
   * - ``READY_TIME_THRESHOLD_MULTIPLIER``
     - 1.5
     - Multiplier applied to the tail median to set the std/slope thresholds
       used by :func:`suggest_ready_time`
   * - ``PSD_FLOOR_LINEAR``
     - 1e-30
     - Avoids ``log10(0)`` when converting PSD to dB
   * - ``TAIL_FRACTION``
     - 0.80
     - Fraction of the signal treated as the "settled tail" by
       :func:`suggest_ready_time`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml
from scipy import signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level named constants (fallback defaults; prefer DSPConfig values)
# ---------------------------------------------------------------------------

#: Scaling factor that converts MAD to a consistent σ estimator (Gaussian).
MAD_CONSISTENCY_CONSTANT: float = 1.4826

#: Multiplier applied to the tail median std/slope for ready-time thresholds.
READY_TIME_THRESHOLD_MULTIPLIER: float = 1.5

#: Linear PSD floor used before log10 conversion to prevent log(0).
PSD_FLOOR_LINEAR: float = 1e-30

#: Default fraction of signal length treated as the "settled tail".
TAIL_FRACTION: float = 0.80


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


##
# @brief Summary information for one dominant PSD peak.
# @param frequency_hz Peak frequency in Hz.
# @param psd Peak PSD value in linear units.
# @param prominence_db Peak prominence in dB over local background.
# @param alias_hint Optional mains-alias interpretation note.
@dataclass(slots=True)
class PeakInfo:
    frequency_hz: float
    psd: float
    prominence_db: float
    alias_hint: str | None = None


##
# @brief Sample-index boundaries for a detected transient event.
# @param start_idx Inclusive start index of the event window.
# @param peak_idx Index of the event peak sample.
# @param end_idx Inclusive end index of the event window.
@dataclass(slots=True)
class EventWindow:
    start_idx: int
    peak_idx: int
    end_idx: int


# ---------------------------------------------------------------------------
# Basic statistics
# ---------------------------------------------------------------------------


##
# @brief Compute an outlier-robust standard deviation estimate using MAD.
# @param x Input samples.
# @return Gaussian-consistent robust standard deviation estimate.
def robust_std(x: np.ndarray) -> float:
    """
    MAD-based outlier-robust standard deviation (consistent estimator).

    Uses :data:`MAD_CONSISTENCY_CONSTANT` (1.4826) to scale MAD so that the
    result is a consistent estimator of σ for Gaussian data.
    """
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    return float(MAD_CONSISTENCY_CONSTANT * mad)


##
# @brief Compute centered rolling mean, std, and slope time series.
# @param y Input signal samples.
# @param fs Sampling rate in Hz.
# @param window_s Rolling window duration in seconds.
# @return Tuple of arrays: (rolling mean, rolling std, rolling slope).
def rolling_mean_std_slope(
    y: np.ndarray,
    fs: float,
    window_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centred rolling mean, std, and linear slope over a time window."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    w = max(3, int(round(window_s * fs)))
    if w >= n:
        w = max(3, n // 2)
    if w % 2 == 0:
        w += 1
    half = w // 2
    means = np.full(n, np.nan)
    stds = np.full(n, np.nan)
    slopes = np.full(n, np.nan)
    x = np.arange(w, dtype=float) / fs
    x_center = x - x.mean()
    denom = np.dot(x_center, x_center)
    for i in range(half, n - half):
        seg = y[i - half : i + half + 1]
        means[i] = np.mean(seg)
        stds[i] = np.std(seg, ddof=1)
        seg_center = seg - seg.mean()
        slopes[i] = np.dot(x_center, seg_center) / denom
    log.debug("rolling_mean_std_slope: n=%d, window_s=%.2f, w=%d samples", n, window_s, w)
    return means, stds, slopes


##
# @brief Suggest earliest stable time using rolling-variability thresholds.
# @param time_s Time vector in seconds.
# @param stds Rolling standard deviation series.
# @param slopes Rolling slope series.
# @param tail_fraction Fraction used to estimate settled-tail thresholds.
# @param threshold_multiplier Multiplier applied to tail medians.
# @return Mapping containing suggested time and derived thresholds.
def suggest_ready_time(
    time_s: np.ndarray,
    stds: np.ndarray,
    slopes: np.ndarray,
    *,
    tail_fraction: float = TAIL_FRACTION,
    threshold_multiplier: float = READY_TIME_THRESHOLD_MULTIPLIER,
) -> dict[str, float | None]:
    """
    Suggest the earliest time at which the signal has stabilised.

    Parameters
    ----------
    time_s:
        Time vector (seconds, zero-based).
    stds:
        Rolling standard deviation array (same length as ``time_s``).
    slopes:
        Rolling linear slope array (same length as ``time_s``).
    tail_fraction:
        Fraction of the signal to treat as the "settled tail".
        Defaults to :data:`TAIL_FRACTION` (0.80).
        Set via ``EventDetectionConfig.tail_fraction``.
    threshold_multiplier:
        Multiplier applied to the tail median for threshold derivation.
        Defaults to :data:`READY_TIME_THRESHOLD_MULTIPLIER` (1.5).

    """
    valid = np.isfinite(stds) & np.isfinite(slopes)
    if not np.any(valid):
        log.warning("suggest_ready_time: no valid (finite) std/slope values")
        return {"suggested_ready_time_s": None, "std_threshold": None, "slope_threshold": None}
    tail_mask = valid.copy()
    tail_start = int(tail_fraction * len(time_s))
    tail_mask[:tail_start] = False
    if not np.any(tail_mask):
        tail_mask = valid
    tail_std = stds[tail_mask]
    tail_slope = np.abs(slopes[tail_mask])
    std_thr = float(np.nanmedian(tail_std) * threshold_multiplier)
    slope_thr = float(np.nanmedian(tail_slope) * threshold_multiplier)
    candidates = np.where(valid & (stds <= std_thr) & (np.abs(slopes) <= slope_thr))[0]
    suggested = None if candidates.size == 0 else float(time_s[candidates[0]])
    log.debug(
        "suggest_ready_time: std_thr=%.4g, slope_thr=%.4g, suggested=%s s",
        std_thr,
        slope_thr,
        f"{suggested:.2f}" if suggested is not None else "None",
    )
    return {
        "suggested_ready_time_s": suggested,
        "std_threshold": std_thr,
        "slope_threshold": slope_thr,
    }


# ---------------------------------------------------------------------------
# Spectral analysis
# ---------------------------------------------------------------------------


##
# @brief Compute Welch PSD with adaptive segment sizing.
# @param y Input signal.
# @param fs Sampling rate in Hz.
# @param max_nperseg Upper bound for segment length.
# @param min_nperseg Lower bound for segment length.
# @param window Welch window name.
# @return Tuple (frequency_hz, psd).
def welch_psd(
    y: np.ndarray,
    fs: float,
    *,
    max_nperseg: int = 2048,
    min_nperseg: int = 256,
    window: str = "hann",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute Welch PSD with adaptive segment length.

    Parameters
    ----------
    y:
        Input signal.
    fs:
        Sampling frequency in Hz.
    max_nperseg:
        Upper bound on the FFT segment length (samples).
        Defaults to 2048; override via ``WelchConfig.max_nperseg``.
    min_nperseg:
        Lower bound on the FFT segment length (samples).
        Defaults to 256; override via ``WelchConfig.min_nperseg``.
    window:
        Window function name.  Defaults to ``"hann"``; override via
        ``WelchConfig.window``.

    """
    y = np.asarray(y, dtype=float)
    if y.size < 8:
        log.warning("welch_psd: signal too short (%d samples) — returning empty", y.size)
        return np.array([]), np.array([])
    y = signal.detrend(y, type="linear")
    nperseg = min(max_nperseg, max(min_nperseg, y.size // 8))
    if nperseg >= y.size:
        nperseg = max(64, y.size // 2)
    noverlap = nperseg // 2
    f, pxx = signal.welch(y, fs=fs, window=window, nperseg=nperseg, noverlap=noverlap, scaling="density")
    log.debug("welch_psd: n=%d, nperseg=%d, freq_bins=%d", y.size, nperseg, f.size)
    return f, pxx


##
# @brief Infer whether a PSD peak may be a mains-frequency alias.
# @param fs Sampling rate in Hz.
# @param peak_hz Peak frequency in Hz.
# @return Alias hint string when likely, else None.
def alias_hint(fs: float, peak_hz: float) -> str | None:
    """Flag if a PSD peak is a plausible mains alias (50 or 60 Hz)."""
    if not np.isfinite(fs) or fs <= 0:
        return None
    hints = []
    for mains in (50.0, 60.0):
        alias = abs(mains - round(mains / fs) * fs)
        if abs(alias - peak_hz) <= 1.0:
            hints.append(f"possible {int(mains)} Hz alias at output rate")
    return "; ".join(hints) if hints else None


##
# @brief Extract the most prominent spectral peaks from a PSD curve.
# @param f Frequency vector in Hz.
# @param pxx PSD vector.
# @param fs Sampling rate in Hz for alias-hint logic.
# @param prominence_db Minimum required prominence in dB.
# @param max_peaks Maximum number of peaks to return.
# @return List of PeakInfo entries sorted by descending PSD.
def dominant_psd_peaks(
    f: np.ndarray,
    pxx: np.ndarray,
    fs: float,
    *,
    prominence_db: float = 3.0,
    max_peaks: int = 8,
) -> list[PeakInfo]:
    """
    Return the most prominent spectral peaks as :class:`PeakInfo` objects.

    Parameters
    ----------
    f:
        Frequency vector (Hz).
    pxx:
        Power spectral density vector (same length as ``f``).
    fs:
        Sampling frequency — used only for alias detection.
    prominence_db:
        Minimum peak prominence in dB.
        Defaults to 3.0; override via ``PsdPeaksConfig.prominence_db``.
    max_peaks:
        Maximum number of peaks to return (sorted by PSD, descending).
        Defaults to 8; override via ``PsdPeaksConfig.max_peaks``.

    """
    if f.size == 0 or pxx.size == 0:
        return []
    log_psd = 10.0 * np.log10(np.maximum(pxx, PSD_FLOOR_LINEAR))
    peaks, props = signal.find_peaks(log_psd, prominence=prominence_db)
    order = np.argsort(log_psd[peaks])[::-1]
    selected = peaks[order[:max_peaks]]
    info = []
    for idx in selected:
        prom = float(props["prominences"][np.where(peaks == idx)[0][0]])
        info.append(
            PeakInfo(
                frequency_hz=float(f[idx]),
                psd=float(pxx[idx]),
                prominence_db=prom,
                alias_hint=alias_hint(fs, float(f[idx])),
            )
        )
    log.debug("dominant_psd_peaks: found %d peaks", len(info))
    return info


##
# @brief Integrate PSD power within a frequency band.
# @param f Frequency vector in Hz.
# @param pxx PSD vector aligned to f.
# @param low_hz Lower integration bound in Hz.
# @param high_hz Upper integration bound in Hz.
# @return Band power estimate, or NaN when integration is not possible.
def bandpower(f: np.ndarray, pxx: np.ndarray, low_hz: float, high_hz: float) -> float:
    """Trapezoidal integration of PSD within [low_hz, high_hz]."""
    if f.size == 0:
        return float("nan")
    mask = (f >= low_hz) & (f <= high_hz)
    if np.count_nonzero(mask) < 2:
        return float("nan")
    return float(np.trapezoid(pxx[mask], f[mask]))


# ---------------------------------------------------------------------------
# Noise characterisation
# ---------------------------------------------------------------------------


##
# @brief Compute Allan deviation curve over averaging times.
# @param y Input signal.
# @param fs Sampling rate in Hz.
# @param taus Optional tau grid in seconds.
# @return Tuple of arrays (tau_s, allan_deviation).
def allan_deviation(
    y: np.ndarray,
    fs: float,
    taus: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute Allan deviation over log-spaced averaging times."""
    y = np.asarray(y, dtype=float)
    if y.size < 16:
        log.warning("allan_deviation: signal too short (%d samples)", y.size)
        return np.array([]), np.array([])
    if taus is None:
        max_m = max(4, y.size // 10)
        m_vals = np.unique(np.logspace(0, np.log10(max_m), num=20).astype(int))
    else:
        m_vals = np.unique(np.maximum(1, np.round(taus * fs).astype(int)))
    tau_out = []
    adev_out = []
    for m in m_vals:
        n_blocks = y.size // m
        if n_blocks < 3:
            continue
        trimmed = y[: n_blocks * m]
        block_means = trimmed.reshape(n_blocks, m).mean(axis=1)
        diff = np.diff(block_means)
        avar = 0.5 * np.mean(diff**2)
        tau_out.append(m / fs)
        adev_out.append(np.sqrt(avar))
    log.debug("allan_deviation: computed %d tau points", len(tau_out))
    return np.asarray(tau_out, dtype=float), np.asarray(adev_out, dtype=float)


##
# @brief Fit a first-order trend model to a signal.
# @param y Input signal.
# @param time_s Time vector in seconds.
# @return Tuple (slope, intercept).
def linear_trend(y: np.ndarray, time_s: np.ndarray) -> tuple[float, float]:
    """Fit a linear trend and return (slope, intercept)."""
    coeff = np.polyfit(time_s, y, 1)
    return float(coeff[0]), float(coeff[1])


# ---------------------------------------------------------------------------
# Event detection and metrics
# ---------------------------------------------------------------------------


##
# @brief Detect above-threshold transient events in a signal.
# @param y Input signal.
# @param fs Sampling rate in Hz.
# @param baseline_s Baseline duration for robust threshold estimation.
# @param threshold_sigma Sigma multiplier above baseline.
# @param min_duration_s Minimum accepted event duration.
# @param merge_gap_s Maximum off-gap duration merged into events.
# @param pad_s Symmetric padding added around accepted windows.
# @return List of detected EventWindow intervals.
def detect_events(
    y: np.ndarray,
    fs: float,
    baseline_s: float = 2.0,
    threshold_sigma: float = 5.0,
    min_duration_s: float = 0.20,
    merge_gap_s: float = 0.15,
    pad_s: float = 0.25,
) -> list[EventWindow]:
    """
    Detect above-threshold transient events using a robust baseline estimate.

    Parameters default to :class:`~handgrip_analysis.config.EventDetectionConfig`
    field values; callers should pass config values explicitly::

        events = detect_events(
            y, fs,
            baseline_s=dsp_cfg.event_detection.baseline_s,
            threshold_sigma=dsp_cfg.event_detection.threshold_sigma,
            min_duration_s=dsp_cfg.event_detection.min_duration_s,
            merge_gap_s=dsp_cfg.event_detection.merge_gap_s,
            pad_s=dsp_cfg.event_detection.pad_s,
        )
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 4:
        log.warning("detect_events: signal too short (%d samples)", n)
        return []

    baseline_n = max(2, int(baseline_s * fs))
    baseline_seg = y[:baseline_n]
    center = float(np.median(baseline_seg))
    spread = robust_std(baseline_seg)
    if spread == 0:
        spread = float(np.std(baseline_seg)) or 1.0
    threshold = center + threshold_sigma * spread

    above = y > threshold
    merge_n = max(1, int(merge_gap_s * fs))
    for gap_start in range(1, n - 1):
        if not above[gap_start]:
            gap_end = gap_start
            while gap_end < n and not above[gap_end]:
                gap_end += 1
            if 0 < gap_end - gap_start <= merge_n:
                above[gap_start:gap_end] = True

    min_len = max(1, int(min_duration_s * fs))
    pad = max(0, int(pad_s * fs))

    windows: list[EventWindow] = []
    groups: list[list[int]] = []
    current: list[int] = []
    for i, val in enumerate(above):
        if val:
            current.append(i)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    for group in groups:
        start = group[0]
        end = group[-1]
        if end - start + 1 < min_len:
            continue
        start = max(0, start - pad)
        end = min(len(y) - 1, end + pad)
        peak = int(start + np.argmax(y[start : end + 1]))
        windows.append(EventWindow(start_idx=start, peak_idx=peak, end_idx=end))
    log.info("detect_events: detected %d event(s)", len(windows))
    return windows


##
# @brief Compute per-event metrics table from detected windows.
# @param y Input signal.
# @param time_s Time vector in seconds.
# @param events Detected event windows.
# @return DataFrame with one row per event and derived dynamic metrics.
def event_metrics(
    y: np.ndarray,
    time_s: np.ndarray,
    events: list[EventWindow],
) -> pd.DataFrame:
    """Compute per-event feature metrics (one row per event)."""
    rows = []
    for i, ev in enumerate(events, start=1):
        seg_y = y[ev.start_idx : ev.end_idx + 1]
        seg_t = time_s[ev.start_idx : ev.end_idx + 1]
        peak_local = int(np.argmax(seg_y))
        peak_val = float(seg_y[peak_local])
        onset_val = float(seg_y[0])
        rise = peak_val - onset_val
        y10 = onset_val + 0.1 * rise
        y90 = onset_val + 0.9 * rise
        t10 = np.nan
        t90 = np.nan
        cross10 = np.where(seg_y >= y10)[0]
        cross90 = np.where(seg_y >= y90)[0]
        if cross10.size:
            t10 = float(seg_t[cross10[0]])
        if cross90.size:
            t90 = float(seg_t[cross90[0]])
        dy = np.gradient(seg_y, seg_t)
        # TAIL_FRACTION (0.80) defines the hold-stability plateau window boundary.
        tail_start = int(TAIL_FRACTION * len(seg_y))
        rows.append(
            {
                "event_index": i,
                "start_time_s": float(seg_t[0]),
                "peak_time_s": float(seg_t[peak_local]),
                "end_time_s": float(seg_t[-1]),
                "duration_s": float(seg_t[-1] - seg_t[0]),
                "peak_value": peak_val,
                "baseline_value": onset_val,
                "rise_10_90_s": float(t90 - t10) if np.isfinite(t10) and np.isfinite(t90) else np.nan,
                "max_dfdt": float(np.max(dy)),
                "hold_std_last_20pct": float(np.std(seg_y[tail_start:])),
            }
        )
    return pd.DataFrame(rows)


##
# @brief Summarize the dominant event using scalar benchmarking metrics.
# @param y Input signal.
# @param time_s Time vector in seconds.
# @param fs Sampling rate in Hz.
# @param baseline_s Baseline duration for event detection.
# @param threshold_sigma Sigma threshold for event detection.
# @param min_duration_s Minimum accepted event duration.
# @param merge_gap_s Gap duration used to merge nearby detections.
# @param pad_s Padding added around accepted detections.
# @return Flat dictionary of dominant-event summary metrics.
def best_event_metrics(
    y: np.ndarray,
    time_s: np.ndarray,
    fs: float,
    baseline_s: float = 2.0,
    threshold_sigma: float = 5.0,
    min_duration_s: float = 0.20,
    merge_gap_s: float = 0.15,
    pad_s: float = 0.25,
) -> dict[str, float]:
    """
    Summarise the dominant grip event in a capture.

    Selects the event with the largest baseline-to-peak excursion and returns a
    flat dict of scalar metrics.  Suitable for filter benchmarking (stage 6).

    Parameters default to :class:`~handgrip_analysis.config.EventDetectionConfig`
    field values; callers should pass config values explicitly.

    Keys: n_events, peak_value, peak_time_s, rise_10_90_s, max_dfdt,
    plateau_std_last20pct, event_start_s, event_end_s
    """
    _nan: dict[str, float] = {
        "n_events": 0.0,
        "peak_value": float("nan"),
        "peak_time_s": float("nan"),
        "rise_10_90_s": float("nan"),
        "max_dfdt": float("nan"),
        "plateau_std_last20pct": float("nan"),
        "event_start_s": float("nan"),
        "event_end_s": float("nan"),
    }
    events = detect_events(
        y,
        fs,
        baseline_s=baseline_s,
        threshold_sigma=threshold_sigma,
        min_duration_s=min_duration_s,
        merge_gap_s=merge_gap_s,
        pad_s=pad_s,
    )
    if not events:
        log.warning("best_event_metrics: no events detected")
        return _nan

    best = max(events, key=lambda ev: float(y[ev.peak_idx] - y[ev.start_idx]))
    seg_y = y[best.start_idx : best.end_idx + 1]
    seg_t = time_s[best.start_idx : best.end_idx + 1]

    peak_local = int(np.argmax(seg_y))
    peak_value = float(seg_y[peak_local])
    peak_time = float(seg_t[peak_local])
    baseline = float(seg_y[0])
    rise = peak_value - baseline

    y10 = baseline + 0.1 * rise
    y90 = baseline + 0.9 * rise
    c10 = np.where(seg_y >= y10)[0]
    c90 = np.where(seg_y >= y90)[0]
    rise_10_90 = float(seg_t[c90[0]] - seg_t[c10[0]]) if c10.size and c90.size else float("nan")

    dy = np.gradient(seg_y, seg_t)
    # TAIL_FRACTION (0.80) defines the plateau window boundary.
    tail = seg_y[int(TAIL_FRACTION * len(seg_y)) :]
    plateau_std = float(np.std(tail)) if len(tail) > 1 else float("nan")

    log.debug(
        "best_event_metrics: n_events=%d, peak=%.4g, rise_10_90=%.4f s",
        len(events),
        peak_value,
        rise_10_90 if np.isfinite(rise_10_90) else float("nan"),
    )
    return {
        "n_events": float(len(events)),
        "peak_value": peak_value,
        "peak_time_s": peak_time,
        "rise_10_90_s": rise_10_90,
        "max_dfdt": float(np.max(dy)),
        "plateau_std_last20pct": plateau_std,
        "event_start_s": float(seg_t[0]),
        "event_end_s": float(seg_t[-1]),
    }


# ---------------------------------------------------------------------------
# Production real-time filter application
# ---------------------------------------------------------------------------

PRODUCTION_REALTIME_FILTER_TYPES: frozenset[str] = frozenset(
    {
        "identity",
        "butterworth_lowpass_2nd",
        "biquad_lowpass",
        "lowpass_1pole",
        # Backward-compatible aliases.  These now execute with the same causal
        # per-sample semantics as LSL_Bridge, not with offline zero-phase
        # filtering.  New candidate files should prefer the canonical names
        # above so Stage 6 output can be dropped into LSL_Bridge config directly.
        "butter_lowpass",
        "one_pole_lowpass",
    }
)


class _ProductionFilterNode:
    def process(self, value: float, sample_time_s: float) -> float:  # pragma: no cover - protocol-like base
        raise NotImplementedError


@dataclass(slots=True)
class IdentityProcessor(_ProductionFilterNode):
    """Pass-through processor matching ``LSL_Bridge`` identity behavior."""

    def process(self, value: float, sample_time_s: float) -> float:
        _ = sample_time_s
        return value


@dataclass(slots=True)
class FirstOrderLowPass(_ProductionFilterNode):
    """1-pole RC IIR low-pass filter matching ``LSL_Bridge`` implementation."""

    cutoff_hz: float
    reset_on_gap_s: float = 1.0
    min_dt_s: float = 1e-6

    _tau: float = field(init=False)
    _last_time_s: float | None = field(init=False, default=None)
    _y: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.cutoff_hz <= 0.0:
            raise ValueError(f"cutoff_hz must be > 0. Received {self.cutoff_hz}")
        self._tau = 1.0 / (2.0 * np.pi * self.cutoff_hz)

    def process(self, value: float, sample_time_s: float) -> float:
        if self._y is None or self._last_time_s is None:
            self._y = value
            self._last_time_s = sample_time_s
            return value

        dt = max(self.min_dt_s, sample_time_s - self._last_time_s)
        if dt > self.reset_on_gap_s:
            log.warning(
                "Low-pass filter state reset after large gap: dt=%.6fs > %.6fs",
                dt,
                self.reset_on_gap_s,
            )
            self._y = value
            self._last_time_s = sample_time_s
            return value

        alpha = dt / (self._tau + dt)
        self._y = self._y + alpha * (value - self._y)
        self._last_time_s = sample_time_s
        return self._y


@dataclass(slots=True)
class SecondOrderBiquadLowPass(_ProductionFilterNode):
    """Second-order low-pass biquad matching ``LSL_Bridge`` implementation."""

    cutoff_hz: float
    sample_rate_hz: float
    q: float = 1.0 / np.sqrt(2.0)
    reset_on_gap_s: float = 1.0
    min_dt_s: float = 1e-6

    _b0: float = field(init=False)
    _b1: float = field(init=False)
    _b2: float = field(init=False)
    _a1: float = field(init=False)
    _a2: float = field(init=False)
    _last_time_s: float | None = field(init=False, default=None)
    _x1: float = field(init=False, default=0.0)
    _x2: float = field(init=False, default=0.0)
    _y1: float = field(init=False, default=0.0)
    _y2: float = field(init=False, default=0.0)
    _initialized: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if self.cutoff_hz <= 0.0:
            raise ValueError(f"cutoff_hz must be > 0. Received {self.cutoff_hz}")
        if self.sample_rate_hz <= 0.0:
            raise ValueError(f"sample_rate_hz must be > 0. Received {self.sample_rate_hz}")
        nyquist_hz = 0.5 * self.sample_rate_hz
        if self.cutoff_hz >= nyquist_hz:
            raise ValueError(
                "cutoff_hz must be strictly below Nyquist. "
                f"Received cutoff_hz={self.cutoff_hz} sample_rate_hz={self.sample_rate_hz}"
            )
        if self.q <= 0.0:
            raise ValueError(f"q must be > 0. Received {self.q}")

        omega = 2.0 * np.pi * self.cutoff_hz / self.sample_rate_hz
        cos_omega = np.cos(omega)
        sin_omega = np.sin(omega)
        alpha = sin_omega / (2.0 * self.q)

        b0 = (1.0 - cos_omega) / 2.0
        b1 = 1.0 - cos_omega
        b2 = (1.0 - cos_omega) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_omega
        a2 = 1.0 - alpha

        self._b0 = float(b0 / a0)
        self._b1 = float(b1 / a0)
        self._b2 = float(b2 / a0)
        self._a1 = float(a1 / a0)
        self._a2 = float(a2 / a0)

    def _reset_state(self, value: float, sample_time_s: float) -> float:
        self._last_time_s = sample_time_s
        self._x1 = value
        self._x2 = value
        self._y1 = value
        self._y2 = value
        self._initialized = True
        return value

    def process(self, value: float, sample_time_s: float) -> float:
        if not self._initialized or self._last_time_s is None:
            return self._reset_state(value, sample_time_s)

        dt = max(self.min_dt_s, sample_time_s - self._last_time_s)
        if dt > self.reset_on_gap_s:
            log.warning(
                "Second-order low-pass state reset after large gap: dt=%.6fs > %.6fs",
                dt,
                self.reset_on_gap_s,
            )
            return self._reset_state(value, sample_time_s)

        y = self._b0 * value + self._b1 * self._x1 + self._b2 * self._x2 - self._a1 * self._y1 - self._a2 * self._y2

        self._x2 = self._x1
        self._x1 = value
        self._y2 = self._y1
        self._y1 = y
        self._last_time_s = sample_time_s
        return y


def _canonical_filter_type(spec: Mapping[str, Any]) -> str:
    filter_type = str(spec.get("type", ""))
    if filter_type == "butter_lowpass":
        order = int(spec.get("order", 2))
        if order != 2:
            raise ValueError("Production-equivalent butter_lowpass alias only supports order=2")
        return "butterworth_lowpass_2nd"
    if filter_type == "one_pole_lowpass":
        return "lowpass_1pole"
    return filter_type


def is_production_realtime_filter_spec(spec: Mapping[str, Any]) -> bool:
    """Return ``True`` when *spec* maps to an LSL_Bridge real-time filter."""
    try:
        return _canonical_filter_type(spec) in {"identity", "butterworth_lowpass_2nd", "biquad_lowpass", "lowpass_1pole"}
    except Exception:  # noqa: BLE001 - validation helper should be defensive
        return False


def lsl_bridge_filter_config_from_spec(spec: Mapping[str, Any], sample_rate_hz: float) -> dict[str, Any]:
    """
    Convert one Handgrip_Analysis candidate into one LSL_Bridge filter stanza.

    This function is the source-code contract between Stage 6 and LSL_Bridge:
    any active Stage 6 candidate must be convertible here.  The returned mapping
    can be used directly under ``processing.filters`` in ``LSL_Bridge`` config.
    """
    name = str(spec.get("name", ""))
    canonical_type = _canonical_filter_type(spec)

    if canonical_type == "identity":
        out: dict[str, Any] = {"type": "identity"}
        if name:
            out["name"] = name
        return out

    if canonical_type in {"butterworth_lowpass_2nd", "biquad_lowpass"}:
        out = {
            "type": "butterworth_lowpass_2nd",
            "cutoff_hz": float(spec["cutoff_hz"]),
            "sample_rate_hz": float(spec.get("sample_rate_hz", sample_rate_hz)),
            "q": float(spec.get("q", 1.0 / np.sqrt(2.0))),
            "reset_on_gap_s": float(spec.get("reset_on_gap_s", 1.0)),
            "min_dt_s": float(spec.get("min_dt_s", 1e-6)),
        }
        if name:
            out["name"] = name
        return out

    if canonical_type == "lowpass_1pole":
        out = {
            "type": "lowpass_1pole",
            "cutoff_hz": float(spec["cutoff_hz"]),
            "reset_on_gap_s": float(spec.get("reset_on_gap_s", 1.0)),
            "min_dt_s": float(spec.get("min_dt_s", 1e-6)),
        }
        if name:
            out["name"] = name
        return out

    raise ValueError(
        f"Filter candidate {name or '<unnamed>'!r} has unsupported production type {spec.get('type')!r}. "
        "Stage 6 active candidates must map directly to LSL_Bridge real-time filters."
    )


def _build_production_filter_node(spec: Mapping[str, Any], fs: float) -> _ProductionFilterNode:
    cfg = lsl_bridge_filter_config_from_spec(spec, sample_rate_hz=fs)
    filter_type = str(cfg["type"])

    if filter_type == "identity":
        return IdentityProcessor()
    if filter_type == "butterworth_lowpass_2nd":
        return SecondOrderBiquadLowPass(
            cutoff_hz=float(cfg["cutoff_hz"]),
            sample_rate_hz=float(cfg["sample_rate_hz"]),
            q=float(cfg.get("q", 1.0 / np.sqrt(2.0))),
            reset_on_gap_s=float(cfg.get("reset_on_gap_s", 1.0)),
            min_dt_s=float(cfg.get("min_dt_s", 1e-6)),
        )
    if filter_type == "lowpass_1pole":
        return FirstOrderLowPass(
            cutoff_hz=float(cfg["cutoff_hz"]),
            reset_on_gap_s=float(cfg.get("reset_on_gap_s", 1.0)),
            min_dt_s=float(cfg.get("min_dt_s", 1e-6)),
        )
    raise ValueError(f"Unsupported production filter type: {filter_type!r}")


def _uniform_time_vector(n_samples: int, fs: float) -> np.ndarray:
    if fs <= 0.0:
        raise ValueError(f"fs must be > 0. Received {fs}")
    return np.arange(n_samples, dtype=float) / float(fs)


##
# @brief Apply one production-real-time filter specification to a signal.
# @param y Input signal samples.
# @param fs Sampling rate in Hz.
# @param spec Filter specification mapping.
# @param time_s Optional per-sample timestamps used to mirror LSL_Bridge runtime.
# @return Filtered signal samples.
def apply_filter_spec(
    y: np.ndarray,
    fs: float,
    spec: dict[str, Any],
    *,
    time_s: np.ndarray | None = None,
) -> np.ndarray:
    """
    Apply a production-real-time filter specification to signal *y*.

    Stage 6 intentionally uses the same causal per-sample filter semantics as
    ``LSL_Bridge``.  Offline zero-phase filters such as ``sosfiltfilt`` are not
    allowed in this path because they cannot run on the live production stream.

    Supported production-equivalent types
    -------------------------------------
    identity                    — pass-through
    butterworth_lowpass_2nd     — LSL_Bridge 2nd-order biquad low-pass
    biquad_lowpass              — alias for ``butterworth_lowpass_2nd``
    lowpass_1pole               — LSL_Bridge first-order low-pass

    Backward-compatible aliases
    ---------------------------
    butter_lowpass              — accepted only with ``order: 2``; executed as
                                  ``butterworth_lowpass_2nd``
    one_pole_lowpass            — executed as ``lowpass_1pole``
    """
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return y.copy()

    if time_s is None:
        time = _uniform_time_vector(len(y), fs)
    else:
        time = np.asarray(time_s, dtype=float)
        if len(time) != len(y):
            raise ValueError(f"time_s length ({len(time)}) must match signal length ({len(y)})")

    node = _build_production_filter_node(spec, fs)
    out = np.empty_like(y, dtype=float)
    for idx, (value, sample_time_s) in enumerate(zip(y, time, strict=True)):
        out[idx] = node.process(float(value), float(sample_time_s))
    return out


##
# @brief Load filter-candidate specifications from a YAML file.
# @param path Path to YAML file containing a `filters` list.
# @return List of filter specification mappings.
def load_filter_specs(path: str | Path) -> list[dict[str, Any]]:
    """
    Load production-real-time YAML filter candidates.

    The active ``filters`` list is treated as a deployable contract: every
    candidate must map directly to one LSL_Bridge real-time filter stanza.  This
    fails fast before Stage 6 can rank an offline-only or manually-translated
    filter as the final recommendation.
    """
    with Path(path).open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    specs = list(cfg.get("filters", []))
    invalid = [str(spec.get("name", "<unnamed>")) for spec in specs if not is_production_realtime_filter_spec(spec)]
    if invalid:
        raise ValueError(
            "Filter candidate file contains active filters that are not directly deployable in LSL_Bridge: "
            + ", ".join(invalid)
        )
    log.info("load_filter_specs: loaded %d production-real-time filter specs from %s", len(specs), path)
    return specs
