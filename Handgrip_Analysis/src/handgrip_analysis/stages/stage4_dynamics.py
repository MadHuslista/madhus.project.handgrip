"""Stage 4 — grip dynamics and event metrics."""
from __future__ import annotations

import pandas as pd

from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import detect_events, event_metrics, welch_psd
from ..io import load_capture, sampling_summary
from .common import base_metrics, flatten_sampling, summarize_default


def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    cap = load_capture(spec.path, time_source=cfg.time_source)
    channel = spec.channel or cfg.channel
    y = cap.series(channel)  # type: ignore[arg-type]
    events = detect_events(
        y,
        cap.fs_estimate_hz,
        baseline_s=cfg.baseline_s,
        threshold_sigma=cfg.threshold_sigma,
        min_duration_s=cfg.min_duration_s,
        merge_gap_s=cfg.merge_gap_s,
        pad_s=cfg.pad_s,
    )
    events_df = event_metrics(y, cap.time_s, events)
    if not events_df.empty:
        events_df.insert(0, "trial_id", spec.trial_id)
        events_df.insert(0, "session_id", spec.session_id)
        events_df.insert(0, "condition", spec.condition)
    metrics = {
        **base_metrics(spec),
        "channel_used": channel,
        "time_source_used": cap.time_source,
        **flatten_sampling("sampling", sampling_summary(cap.time_s)),
        "n_events": float(len(events)),
        "peak_value_max": float(events_df["peak_value"].max()) if not events_df.empty else float("nan"),
        "peak_value_median": float(events_df["peak_value"].median()) if not events_df.empty else float("nan"),
        "rise_10_90_s_median": float(events_df["rise_10_90_s"].median()) if not events_df.empty else float("nan"),
        "max_dfdt_max": float(events_df["max_dfdt"].max()) if not events_df.empty else float("nan"),
        "hold_std_last_20pct_median": float(events_df["hold_std_last_20pct"].median()) if not events_df.empty else float("nan"),
    }

    tables: dict[str, pd.DataFrame] = {"event_metrics": events_df}
    if events:
        hold_rows = []
        for i, ev in enumerate(events, start=1):
            seg_y = y[ev.start_idx : ev.end_idx + 1]
            if len(seg_y) > int(2 * cap.fs_estimate_hz):
                hold_slice = seg_y[int(0.5 * len(seg_y)) :]
                f, pxx = welch_psd(hold_slice, cap.fs_estimate_hz)
                for freq, psd in zip(f, pxx, strict=False):
                    hold_rows.append({"event_index": i, "frequency_hz": float(freq), "psd": float(psd)})
        tables["hold_psd"] = pd.DataFrame(hold_rows)
    return TrialResult(spec=spec, metrics=metrics, tables=tables)


def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return summarize_default(results, cfg)
