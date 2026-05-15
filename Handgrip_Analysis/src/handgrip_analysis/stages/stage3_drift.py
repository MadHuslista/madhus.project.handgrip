# @package handgrip_analysis.stages.stage3_drift
# @brief Stage 3 loaded drift and creep analyzer.

"""Stage 3 — loaded drift / creep analysis."""
from __future__ import annotations

import numpy as np

from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import linear_trend
from ..io import load_capture, sampling_summary
from .common import base_metrics, flatten_sampling, summarize_default


# @brief Analyze one Stage 3 drift/creep trial.
# @param spec Trial specification.
# @param cfg Stage configuration.
# @return TrialResult with drift metrics.
def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = cap.series(channel)  # type: ignore[arg-type]
    slope, intercept = linear_trend(y, cap.time_s)
    trend = slope * cap.time_s + intercept
    detrended = y - trend

    n_pre = min(len(y), max(1, int(round(cfg.pre_window_s * cap.fs_estimate_hz))))
    n_post = min(len(y), max(1, int(round(cfg.post_window_s * cap.fs_estimate_hz))))
    pre_mean = float(np.mean(y[:n_pre]))
    post_mean = float(np.mean(y[-n_post:]))
    metrics = {
        **base_metrics(spec),
        "channel_used": channel,
        "time_source_used": cap.time_source,
        **flatten_sampling("sampling", sampling_summary(cap.time_s)),
        "pre_window_s": float(cfg.pre_window_s),
        "post_window_s": float(cfg.post_window_s),
        "drift_slope_per_s": float(slope),
        "drift_slope_per_min": float(slope * 60.0),
        "trend_intercept": float(intercept),
        "pre_window_mean": pre_mean,
        "post_window_mean": post_mean,
        "return_to_zero_error": post_mean - pre_mean,
        "detrended_std": float(np.std(detrended, ddof=1)),
    }
    return TrialResult(spec=spec, metrics=metrics)


# @brief Summarize Stage 3 trial results by condition.
# @param results Trial result list.
# @param cfg Stage configuration.
# @return Condition summary list.
def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return summarize_default(results, cfg)
