# @package handgrip_analysis.stages.stage1_warmup
# @brief Stage 1 startup warm-up and stabilization analyzer.

"""Stage 1 — startup warm-up / zero stabilisation."""
from __future__ import annotations

import numpy as np

from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import rolling_mean_std_slope, suggest_ready_time
from ..io import load_capture, sampling_summary
from .common import base_metrics, flatten_sampling, summarize_default


# @brief Compute mean over finite values only.
# @param values Input numeric array.
# @return Finite mean or NaN.
def _finite_mean(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if finite.size else float("nan")


# @brief Analyze one Stage 1 warm-up trial.
# @param spec Trial specification.
# @param cfg Stage configuration.
# @return TrialResult with warm-up metrics.
def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = cap.series(channel)  # type: ignore[arg-type]
    means, stds, slopes = rolling_mean_std_slope(y, cap.fs_estimate_hz, cfg.warmup_window_s)
    ready = suggest_ready_time(cap.time_s, stds, slopes)
    n_tail = max(10, len(means) // 10)
    metrics = {
        **base_metrics(spec),
        "channel_used": channel,
        "time_source_used": cap.time_source,
        **flatten_sampling("sampling", sampling_summary(cap.time_s)),
        "warmup_window_s": float(cfg.warmup_window_s),
        "suggested_ready_time_s": ready["suggested_ready_time_s"],
        "std_threshold": ready["std_threshold"],
        "slope_threshold": ready["slope_threshold"],
        "final_mean": _finite_mean(means[-n_tail:]),
        "final_std": _finite_mean(stds[-n_tail:]),
        "final_abs_slope": _finite_mean(np.abs(slopes[-n_tail:])),
    }
    return TrialResult(spec=spec, metrics=metrics)


# @brief Summarize Stage 1 trial results by condition.
# @param results Trial result list.
# @param cfg Stage configuration.
# @return Condition summary list.
def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return summarize_default(results, cfg)
