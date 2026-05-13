"""Stage 5 — interference comparison with condition replicates."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import bandpower, dominant_psd_peaks, robust_std, welch_psd
from ..io import load_capture, sampling_summary
from .common import base_metrics, flatten_sampling, summarize_default


def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = cap.series(channel)  # type: ignore[arg-type]
    f, pxx = welch_psd(y, cap.fs_estimate_hz)
    peaks = dominant_psd_peaks(f, pxx, cap.fs_estimate_hz)
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


def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return summarize_default(results, cfg)
