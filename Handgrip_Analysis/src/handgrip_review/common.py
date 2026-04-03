from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import numpy as np
import pandas as pd
import yaml
from scipy import signal


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_capture(path: str | Path) -> tuple[np.ndarray, np.ndarray, float, pd.DataFrame]:
    df = pd.read_csv(path)
    t = (df['device_clock_us'].to_numpy(dtype=float) - float(df['device_clock_us'].iloc[0])) / 1e6
    y = df['value_raw'].to_numpy(dtype=float)
    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    fs = 1.0 / float(np.median(dt))
    return t, y, fs, df


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    with Path(path).open('w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def welch_psd(y: np.ndarray, fs: float, nperseg: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    y = signal.detrend(np.asarray(y, dtype=float), type='linear')
    nperseg = min(nperseg, len(y))
    if nperseg < 64:
        return np.array([]), np.array([])
    noverlap = nperseg // 2
    f, pxx = signal.welch(y, fs=fs, window='hann', nperseg=nperseg, noverlap=noverlap, scaling='density')
    return f, pxx


def bandpower(f: np.ndarray, pxx: np.ndarray, low_hz: float, high_hz: float) -> float:
    mask = (f >= low_hz) & (f <= high_hz)
    if np.count_nonzero(mask) < 2:
        return float('nan')
    return float(np.trapezoid(pxx[mask], f[mask]))


def dominant_psd_peaks(f: np.ndarray, pxx: np.ndarray, max_peaks: int = 8) -> pd.DataFrame:
    if f.size == 0:
        return pd.DataFrame(columns=['frequency_hz', 'psd', 'prominence_db'])
    log_psd = 10.0 * np.log10(np.maximum(pxx, 1e-30))
    peaks, props = signal.find_peaks(log_psd, prominence=3.0)
    rows = []
    for idx, prom in zip(peaks, props['prominences']):
        rows.append({'frequency_hz': float(f[idx]), 'psd': float(pxx[idx]), 'prominence_db': float(prom)})
    rows = sorted(rows, key=lambda r: r['prominence_db'], reverse=True)[:max_peaks]
    return pd.DataFrame(rows)


def robust_std(x: np.ndarray) -> float:
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    return float(1.4826 * mad)


def detect_events(y: np.ndarray, fs: float, threshold_sigma: float = 5.0) -> list[tuple[int, int, int]]:
    n0 = min(len(y), max(8, int(round(2.0 * fs))))
    base = y[:n0]
    center = np.median(base)
    spread = max(robust_std(base), float(np.std(base)) * 0.5, 1e-12)
    threshold = center + threshold_sigma * spread
    active = y > threshold
    idx = np.flatnonzero(active)
    if idx.size == 0:
        return []
    groups = [[int(idx[0])]]
    max_gap = max(1, int(round(0.15 * fs)))
    for i in idx[1:]:
        if int(i) - groups[-1][-1] <= max_gap:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    events: list[tuple[int, int, int]] = []
    min_len = max(1, int(round(0.20 * fs)))
    pad = max(1, int(round(0.25 * fs)))
    for g in groups:
        s, e = g[0], g[-1]
        if e - s + 1 < min_len:
            continue
        s = max(0, s - pad)
        e = min(len(y) - 1, e + pad)
        p = int(s + np.argmax(y[s:e+1]))
        events.append((s, p, e))
    return events


def best_event_metrics(y: np.ndarray, t: np.ndarray, fs: float) -> dict[str, float]:
    events = detect_events(y, fs)
    if not events:
        return {
            'n_events': 0,
            'peak_value': float('nan'),
            'peak_time_s': float('nan'),
            'rise_10_90_s': float('nan'),
            'max_dfdt': float('nan'),
            'plateau_std_last20pct': float('nan'),
            'event_start_s': float('nan'),
            'event_end_s': float('nan'),
        }
    # most relevant event = largest baseline-to-peak excursion
    best = max(events, key=lambda ev: float(y[ev[1]] - y[ev[0]]))
    s, p, e = best
    seg_y = y[s:e+1]
    seg_t = t[s:e+1]
    peak_idx = int(np.argmax(seg_y))
    peak_value = float(seg_y[peak_idx])
    peak_time = float(seg_t[peak_idx])
    baseline = float(seg_y[0])
    rise = peak_value - baseline
    y10 = baseline + 0.1 * rise
    y90 = baseline + 0.9 * rise
    c10 = np.where(seg_y >= y10)[0]
    c90 = np.where(seg_y >= y90)[0]
    rise_10_90 = float(seg_t[c90[0]] - seg_t[c10[0]]) if c10.size and c90.size else float('nan')
    dt = np.median(np.diff(seg_t)) if len(seg_t) > 2 else (1.0 / fs)
    dy = np.gradient(seg_y, dt)
    tail = seg_y[int(0.8 * len(seg_y)):]
    return {
        'n_events': float(len(events)),
        'peak_value': peak_value,
        'peak_time_s': peak_time,
        'rise_10_90_s': rise_10_90,
        'max_dfdt': float(np.max(dy)),
        'plateau_std_last20pct': float(np.std(tail)) if len(tail) > 1 else float('nan'),
        'event_start_s': float(seg_t[0]),
        'event_end_s': float(seg_t[-1]),
    }


def apply_filter(y: np.ndarray, fs: float, spec: dict[str, Any]) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    ftype = spec['type']
    if ftype == 'identity':
        return y.copy()
    if ftype == 'butter_lowpass':
        sos = signal.butter(int(spec.get('order', 2)), float(spec['cutoff_hz']), btype='low', fs=fs, output='sos')
        return signal.sosfiltfilt(sos, y)
    if ftype == 'butter_highpass':
        sos = signal.butter(int(spec.get('order', 2)), float(spec['cutoff_hz']), btype='high', fs=fs, output='sos')
        return signal.sosfiltfilt(sos, y)
    if ftype == 'butter_bandpass':
        sos = signal.butter(int(spec.get('order', 2)), [float(spec['low_hz']), float(spec['high_hz'])], btype='bandpass', fs=fs, output='sos')
        return signal.sosfiltfilt(sos, y)
    if ftype == 'notch':
        b, a = signal.iirnotch(float(spec['freq_hz']), float(spec.get('q', 20.0)), fs)
        return signal.filtfilt(b, a, y)
    if ftype == 'chain':
        out = y.copy()
        for step in spec.get('steps', []):
            out = apply_filter(out, fs, step)
        return out
    raise ValueError(f'Unsupported filter type: {ftype}')


def load_filter_specs(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open('r', encoding='utf-8') as f:
        payload = yaml.safe_load(f)
    return list(payload.get('filters', []))
