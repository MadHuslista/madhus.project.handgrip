"""Stage 2 — stationary rest noise characterisation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DSPConfig
from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import allan_deviation, bandpower, dominant_psd_peaks, robust_std, welch_psd
from ..io import FILTERED_COLUMN, load_capture, sampling_summary
from .common import base_metrics, flatten_sampling, summarize_default


def _get_dsp_cfg(cfg: StageConfig) -> DSPConfig:
    """Extract or build DSPConfig from StageConfig."""
    if hasattr(cfg, "dsp") and isinstance(cfg.dsp, DSPConfig):
        return cfg.dsp
    return DSPConfig()


def _bandpower_metrics(f: np.ndarray, pxx: np.ndarray, bands: tuple[tuple[float, float], ...]) -> dict[str, float]:
    out: dict[str, float] = {}
    for lo, hi in bands[:4]:
        key = f"bandpower_{str(lo).replace('.', 'p')}_{str(hi).replace('.', 'p')}_hz"
        out[key] = bandpower(f, pxx, lo, hi)
    return out


def _channel_metrics(y: np.ndarray, fs: float, cfg: StageConfig, prefix: str) -> tuple[dict[str, float], dict[str, pd.DataFrame]]:
    dsp = _get_dsp_cfg(cfg)
    f, pxx = welch_psd(
        y, fs,
        max_nperseg=dsp.welch.max_nperseg,
        min_nperseg=dsp.welch.min_nperseg,
        window=dsp.welch.window,
    )
    tau, adev = allan_deviation(y, fs)
    peaks = dominant_psd_peaks(
        f, pxx, fs,
        prominence_db=dsp.psd_peaks.prominence_db,
        max_peaks=dsp.psd_peaks.max_peaks,
    )
    metrics = {
        f"{prefix}_mean": float(np.mean(y)),
        f"{prefix}_std": float(np.std(y, ddof=1)),
        f"{prefix}_robust_std": robust_std(y),
        f"{prefix}_rms": float(np.sqrt(np.mean(np.square(y)))),
        f"{prefix}_peak_to_peak": float(np.max(y) - np.min(y)),
    }
    metrics.update({f"{prefix}_{k}": v for k, v in _bandpower_metrics(f, pxx, cfg.bandpower_bands).items()})
    if peaks:
        metrics[f"{prefix}_top_peak_hz"] = float(peaks[0].frequency_hz)
        metrics[f"{prefix}_top_peak_prominence_db"] = float(peaks[0].prominence_db)
    else:
        metrics[f"{prefix}_top_peak_hz"] = float("nan")
        metrics[f"{prefix}_top_peak_prominence_db"] = float("nan")
    tables = {
        f"{prefix}_psd": pd.DataFrame({"frequency_hz": f, "psd": pxx}),
        f"{prefix}_allan": pd.DataFrame({"tau_s": tau, "allan_deviation": adev}),
        f"{prefix}_psd_peaks": pd.DataFrame(
            [
                {
                    "frequency_hz": p.frequency_hz,
                    "psd": p.psd,
                    "prominence_db": p.prominence_db,
                    "alias_hint": p.alias_hint or "",
                }
                for p in peaks
            ]
        ),
    }
    return metrics, tables


def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channels = cfg.channels or (spec.channel or cfg.channel,)
    metrics = {
        **base_metrics(spec),
        "time_source_used": cap.time_source,
        **flatten_sampling("sampling", sampling_summary(cap.time_s)),
    }
    tables: dict[str, pd.DataFrame] = {}
    for channel in channels:
        if channel == "filtered" and FILTERED_COLUMN not in cap.df.columns:
            continue
        y = cap.series(channel)  # type: ignore[arg-type]
        ch_metrics, ch_tables = _channel_metrics(y, cap.fs_estimate_hz, cfg, channel)
        metrics.update(ch_metrics)
        tables.update(ch_tables)
    return TrialResult(spec=spec, metrics=metrics, tables=tables)


def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return summarize_default(results, cfg)
