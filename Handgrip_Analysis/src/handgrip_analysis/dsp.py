from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import signal


@dataclass(slots=True)
class PeakInfo:
    frequency_hz: float
    psd: float
    prominence_db: float
    alias_hint: str | None = None


@dataclass(slots=True)
class EventWindow:
    start_idx: int
    peak_idx: int
    end_idx: int


def robust_std(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    return float(1.4826 * mad)


def rolling_mean_std_slope(y: np.ndarray, fs: float, window_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    return means, stds, slopes


def suggest_ready_time(time_s: np.ndarray, stds: np.ndarray, slopes: np.ndarray) -> dict[str, float | None]:
    valid = np.isfinite(stds) & np.isfinite(slopes)
    if not np.any(valid):
        return {"suggested_ready_time_s": None, "std_threshold": None, "slope_threshold": None}
    tail_mask = valid.copy()
    tail_start = int(0.8 * len(time_s))
    tail_mask[:tail_start] = False
    if not np.any(tail_mask):
        tail_mask = valid
    tail_std = stds[tail_mask]
    tail_slope = np.abs(slopes[tail_mask])
    std_thr = float(np.nanmedian(tail_std) * 1.5)
    slope_thr = float(np.nanmedian(tail_slope) * 1.5)
    candidates = np.where(valid & (stds <= std_thr) & (np.abs(slopes) <= slope_thr))[0]
    suggested = None if candidates.size == 0 else float(time_s[candidates[0]])
    return {
        "suggested_ready_time_s": suggested,
        "std_threshold": std_thr,
        "slope_threshold": slope_thr,
    }


def welch_psd(y: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=float)
    if y.size < 8:
        return np.array([]), np.array([])
    y = signal.detrend(y, type="linear")
    nperseg = min(2048, max(256, y.size // 8))
    if nperseg >= y.size:
        nperseg = max(64, y.size // 2)
    noverlap = nperseg // 2
    f, pxx = signal.welch(y, fs=fs, window="hann", nperseg=nperseg, noverlap=noverlap, scaling="density")
    return f, pxx


def alias_hint(fs: float, peak_hz: float) -> str | None:
    if not np.isfinite(fs) or fs <= 0:
        return None
    hints = []
    for mains in (50.0, 60.0):
        alias = abs(mains - round(mains / fs) * fs)
        if abs(alias - peak_hz) <= 1.0:
            hints.append(f"possible {int(mains)} Hz alias at output rate")
    return "; ".join(hints) if hints else None


def dominant_psd_peaks(f: np.ndarray, pxx: np.ndarray, fs: float, max_peaks: int = 8) -> list[PeakInfo]:
    if f.size == 0 or pxx.size == 0:
        return []
    log_psd = 10.0 * np.log10(np.maximum(pxx, 1e-30))
    peaks, props = signal.find_peaks(log_psd, prominence=3.0)
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
    return info


def allan_deviation(y: np.ndarray, fs: float, taus: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=float)
    if y.size < 16:
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
    return np.asarray(tau_out, dtype=float), np.asarray(adev_out, dtype=float)


def linear_trend(y: np.ndarray, time_s: np.ndarray) -> tuple[float, float]:
    coeff = np.polyfit(time_s, y, 1)
    return float(coeff[0]), float(coeff[1])


def bandpower(f: np.ndarray, pxx: np.ndarray, low_hz: float, high_hz: float) -> float:
    if f.size == 0:
        return float("nan")
    mask = (f >= low_hz) & (f <= high_hz)
    if np.count_nonzero(mask) < 2:
        return float("nan")
    return float(np.trapezoid(pxx[mask], f[mask]))


def detect_events(
    y: np.ndarray,
    fs: float,
    baseline_s: float = 2.0,
    threshold_sigma: float = 5.0,
    min_duration_s: float = 0.20,
    merge_gap_s: float = 0.15,
) -> list[EventWindow]:
    y = np.asarray(y, dtype=float)
    if y.size < 8:
        return []
    n_base = min(len(y), max(8, int(round(baseline_s * fs))))
    base = y[:n_base]
    center = np.median(base)
    spread = max(robust_std(base), np.std(base) * 0.5, 1e-12)
    threshold = center + threshold_sigma * spread
    active = y > threshold
    if not np.any(active):
        return []
    idx = np.flatnonzero(active)
    groups = [[int(idx[0])]]
    max_gap = max(1, int(round(merge_gap_s * fs)))
    for i in idx[1:]:
        if i - groups[-1][-1] <= max_gap:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    min_len = max(1, int(round(min_duration_s * fs)))
    windows: list[EventWindow] = []
    for group in groups:
        start = group[0]
        end = group[-1]
        if end - start + 1 < min_len:
            continue
        pad = max(1, int(round(0.25 * fs)))
        start = max(0, start - pad)
        end = min(len(y) - 1, end + pad)
        peak = int(start + np.argmax(y[start : end + 1]))
        windows.append(EventWindow(start_idx=start, peak_idx=peak, end_idx=end))
    return windows


def event_metrics(y: np.ndarray, time_s: np.ndarray, events: list[EventWindow]) -> pd.DataFrame:
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
                "hold_std_last_20pct": float(np.std(seg_y[int(0.8 * len(seg_y)) :])),
            }
        )
    return pd.DataFrame(rows)


def apply_filter_spec(y: np.ndarray, fs: float, spec: dict[str, Any]) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    filter_type = spec["type"]
    if filter_type == "identity":
        return y.copy()
    if filter_type == "moving_average":
        w = int(spec["window_samples"])
        if w <= 1:
            return y.copy()
        kernel = np.ones(w, dtype=float) / w
        return np.convolve(y, kernel, mode="same")
    if filter_type == "median":
        k = int(spec["kernel_size"])
        if k % 2 == 0:
            k += 1
        return signal.medfilt(y, kernel_size=k)
    if filter_type == "butter_lowpass":
        order = int(spec.get("order", 2))
        cutoff_hz = float(spec["cutoff_hz"])
        sos = signal.butter(order, cutoff_hz, btype="low", fs=fs, output="sos")
        return signal.sosfiltfilt(sos, y)
    if filter_type == "one_pole_lowpass":
        cutoff_hz = float(spec["cutoff_hz"])
        tau = 1.0 / (2.0 * np.pi * cutoff_hz)
        dt = 1.0 / fs
        alpha = dt / (tau + dt)
        out = np.empty_like(y)
        out[0] = y[0]
        for i in range(1, len(y)):
            out[i] = out[i - 1] + alpha * (y[i] - out[i - 1])
        return out
    if filter_type == "notch":
        freq_hz = float(spec["freq_hz"])
        q = float(spec.get("q", 20.0))
        b, a = signal.iirnotch(freq_hz, q, fs=fs)
        return signal.filtfilt(b, a, y)
    if filter_type == "chain":
        out = y.copy()
        for step in spec.get("steps", []):
            out = apply_filter_spec(out, fs, step)
        return out
    raise ValueError(f"Unsupported filter type: {filter_type}")


def load_filter_specs(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return list(cfg.get("filters", []))
