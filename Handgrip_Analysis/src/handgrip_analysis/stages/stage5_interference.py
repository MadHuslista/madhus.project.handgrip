# @package handgrip_analysis.stages.stage5_interference
# @brief Stage 5 interference comparison analyzer.

"""Stage 5 — interference comparison with condition replicates."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DSPConfig
from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import bandpower, dominant_psd_peaks, robust_std, welch_psd
from ..io import load_capture, sampling_summary
from .common import base_metrics, flatten_sampling, summarize_default


# @brief Extract DSP configuration from StageConfig or use defaults.
# @param cfg Stage configuration.
# @return DSPConfig instance.
def _get_dsp_cfg(cfg: StageConfig) -> DSPConfig:
    if hasattr(cfg, "dsp") and isinstance(cfg.dsp, DSPConfig):
        return cfg.dsp
    return DSPConfig()


# @brief Analyze one Stage 5 interference trial.
# @param spec Trial specification.
# @param cfg Stage configuration.
# @return TrialResult with interference metrics and spectral tables.
def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    dsp = _get_dsp_cfg(cfg)
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = cap.series(channel)  # type: ignore[arg-type]
    f, pxx = welch_psd(
        y, cap.fs_estimate_hz,
        max_nperseg=dsp.welch.max_nperseg,
        min_nperseg=dsp.welch.min_nperseg,
        window=dsp.welch.window,
    )
    peaks = dominant_psd_peaks(
        f, pxx, cap.fs_estimate_hz,
        prominence_db=dsp.psd_peaks.prominence_db,
        max_peaks=dsp.psd_peaks.max_peaks,
    )
    bp = {}
    for lo, hi in cfg.bandpower_bands[:4]:
        key = f"bandpower_{str(lo).replace('.', 'p')}_{str(hi).replace('.', 'p')}_hz"
        bp[key] = bandpower(f, pxx, lo, hi)
    metrics = {
        **base_metrics(spec),
        "channel_used": channel,
        "time_source_used": cap.time_source,
        **flatten_sampling("sampling", sampling_summary(cap.time_s)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y, ddof=1)),
        "robust_std": robust_std(y),
        "rms": float(np.sqrt(np.mean(np.square(y)))),
        "peak_to_peak": float(np.max(y) - np.min(y)),
        "top_peak_hz": float(peaks[0].frequency_hz) if peaks else float("nan"),
        "top_peak_prominence_db": float(peaks[0].prominence_db) if peaks else float("nan"),
        **bp,
    }
    tables = {
        "psd": pd.DataFrame({"frequency_hz": f, "psd": pxx}),
        "psd_peaks": pd.DataFrame(
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
    return TrialResult(spec=spec, metrics=metrics, tables=tables)


# @brief Summarize Stage 5 trial results by condition.
# @param results Trial result list.
# @param cfg Stage configuration.
# @return Condition summary list.
def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return summarize_default(results, cfg)
