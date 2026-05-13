"""Stage 6 — filter-family review over repeated rest/dynamic trials."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..aggregation import aggregate_condition_results
from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import apply_filter_spec, bandpower, best_event_metrics, load_filter_specs, welch_psd
from ..io import load_capture, sampling_summary
from .common import base_metrics, flatten_sampling

log = logging.getLogger(__name__)


def _filter_specs(cfg: StageConfig) -> list[dict]:
    if cfg.filter_config is None:
        raise ValueError("Stage 6 requires filter_config=<path>")
    return load_filter_specs(cfg.filter_config)


def _is_rest_trial(spec: TrialSpec) -> bool:
    text = " ".join([spec.stage, spec.condition, spec.trial_type]).lower()
    return "rest" in text or "noise" in text or "static" in text


def _is_dynamic_trial(spec: TrialSpec) -> bool:
    return not _is_rest_trial(spec)


def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    """Evaluate every candidate filter on one rest or dynamic trial.

    The scalar ``metrics`` field stores compact raw-trial metrics.  The full
    per-filter assessment is stored in the ``filter_metrics`` table so the
    stage-level summarizer can rank filters across repeated trials.
    """
    cap = load_capture(spec.path, time_source=cfg.time_source)
    y = cap.series(spec.channel or cfg.channel)  # type: ignore[arg-type]
    fs = cap.fs_estimate_hz
    trial_kind = "rest" if _is_rest_trial(spec) else "dynamic"
    specs = _filter_specs(cfg)
    hf_lo, hf_hi = cfg.hf_noise_band_hz

    raw_event = best_event_metrics(
        y,
        cap.time_s,
        fs,
        baseline_s=cfg.baseline_s,
        threshold_sigma=cfg.threshold_sigma,
        min_duration_s=cfg.min_duration_s,
        merge_gap_s=cfg.merge_gap_s,
        pad_s=cfg.pad_s,
    ) if trial_kind == "dynamic" else {}
    raw_std = float(pd.Series(y).std())
    f_raw, p_raw = welch_psd(y, fs)
    raw_hf = bandpower(f_raw, p_raw, hf_lo, hf_hi)

    rows: list[dict[str, object]] = []
    for filter_spec in specs:
        name = str(filter_spec["name"])
        y_f = apply_filter_spec(y, fs, filter_spec)
        row: dict[str, object] = {
            "filter": name,
            "stage": spec.stage,
            "condition": spec.condition,
            "trial_type": spec.trial_type,
            "trial_id": spec.trial_id,
            "session_id": spec.session_id,
            "trial_kind": trial_kind,
        }
        if trial_kind == "rest":
            f_f, p_f = welch_psd(y_f, fs)
            hf = bandpower(f_f, p_f, hf_lo, hf_hi)
            row.update(
                {
                    "rest_std": float(pd.Series(y_f).std()),
                    "rest_std_norm": float(pd.Series(y_f).std()) / max(raw_std, 1e-12),
                    "rest_hf_bandpower": hf,
                    "rest_hf_bandpower_norm": hf / max(raw_hf, 1e-30) if np.isfinite(raw_hf) else float("nan"),
                }
            )
        else:
            filt_event = best_event_metrics(
                y_f,
                cap.time_s,
                fs,
                baseline_s=cfg.baseline_s,
                threshold_sigma=cfg.threshold_sigma,
                min_duration_s=cfg.min_duration_s,
                merge_gap_s=cfg.merge_gap_s,
                pad_s=cfg.pad_s,
            )
            raw_peak = float(raw_event.get("peak_value", float("nan")))
            raw_rise = float(raw_event.get("rise_10_90_s", float("nan")))
            raw_dfdt = float(raw_event.get("max_dfdt", float("nan")))
            row.update(
                {
                    "n_events": filt_event["n_events"],
                    "peak_error": filt_event["peak_value"] - raw_peak,
                    "peak_relative_error": abs(filt_event["peak_value"] - raw_peak) / max(abs(raw_peak), 1.0),
                    "peak_time_shift_s": filt_event["peak_time_s"] - float(raw_event.get("peak_time_s", float("nan"))),
                    "rise_shift_s": filt_event["rise_10_90_s"] - raw_rise,
                    "rise_relative_error": abs(filt_event["rise_10_90_s"] - raw_rise) / max(abs(raw_rise), 1e-6),
                    "max_dfdt_ratio": filt_event["max_dfdt"] / raw_dfdt if raw_dfdt else float("nan"),
                    "dfdt_deviation": abs(1.0 - (filt_event["max_dfdt"] / raw_dfdt)) if raw_dfdt else float("nan"),
                }
            )
        rows.append(row)

    filter_df = pd.DataFrame(rows)
    metrics = {
        **base_metrics(spec),
        "trial_kind": trial_kind,
        "time_source_used": cap.time_source,
        **flatten_sampling("sampling", sampling_summary(cap.time_s)),
        "raw_std": raw_std,
        "raw_hf_bandpower": raw_hf,
        "raw_peak_value": float(raw_event.get("peak_value", float("nan"))) if raw_event else float("nan"),
        "raw_rise_10_90_s": float(raw_event.get("rise_10_90_s", float("nan"))) if raw_event else float("nan"),
        "n_filter_candidates": float(len(specs)),
    }
    return TrialResult(spec=spec, metrics=metrics, tables={"filter_metrics": filter_df})


def _score_filter_rows(df: pd.DataFrame, cfg: StageConfig) -> pd.DataFrame:
    rows = []
    for filter_name, group in df.groupby("filter", dropna=False):
        row: dict[str, object] = {"filter": filter_name, "n_trials": int(group[["session_id", "trial_id"]].drop_duplicates().shape[0])}
        for col in [
            "rest_std_norm",
            "rest_hf_bandpower_norm",
            "peak_relative_error",
            "rise_relative_error",
            "peak_time_shift_s",
            "dfdt_deviation",
        ]:
            if col in group.columns:
                values = group[col].dropna().astype(float)
                row[f"{col}__median"] = float(values.median()) if not values.empty else float("nan")
                row[f"{col}__mean"] = float(values.mean()) if not values.empty else float("nan")
        w = cfg.filter_weights
        rest_std = float(row.get("rest_std_norm__median", np.nan))
        peak = float(row.get("peak_relative_error__median", np.nan))
        rise = float(row.get("rise_relative_error__median", np.nan))
        time_shift = abs(float(row.get("peak_time_shift_s__median", np.nan))) / 0.1
        dfdt = float(row.get("dfdt_deviation__median", np.nan))
        # Missing dynamic/rest sides are neutralized rather than forced to zero;
        # this keeps partial manifests usable while making missing metrics NaN in
        # the detailed table.
        terms = {
            "rest_std_norm": rest_std,
            "mean_peak_relative_error": peak,
            "mean_rise_relative_error": rise,
            "mean_peak_time_shift_norm": time_shift,
            "mean_dfdt_deviation": dfdt,
        }
        score = 0.0
        weight_sum = 0.0
        for key, value in terms.items():
            if np.isfinite(value):
                weight = float(w.get(key, 0.0))
                score += weight * value
                weight_sum += weight
        row["composite_score"] = score / weight_sum if weight_sum else float("nan")
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty and "composite_score" in out.columns:
        out = out.sort_values("composite_score", ascending=True).reset_index(drop=True)
    return out


def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    """Summarize raw trial metrics and attach filter ranking tables.

    The returned summaries follow the same condition-level contract as other
    stages.  A filter ranking table is attached to each summary's ``metrics``
    table under a conventional column family via the pipeline writer.
    """
    summaries = aggregate_condition_results(
        results,
        confidence_level=cfg.confidence_level,
        n_resamples=cfg.bootstrap_resamples,
        random_seed=cfg.random_seed,
    )
    all_filter_rows = [result.tables.get("filter_metrics") for result in results if "filter_metrics" in result.tables]
    if all_filter_rows:
        filter_df = pd.concat(all_filter_rows, ignore_index=True)
        ranking = _score_filter_rows(filter_df, cfg)
        # Attach the ranking table to the first summary through metrics. The
        # pipeline also writes the full table by collecting TrialResult.tables.
        if summaries:
            first = summaries[0]
            summaries[0] = ConditionSummary(
                stage=first.stage,
                condition=first.condition,
                n_trials=first.n_trials,
                metrics=ranking,
                aggregate={**first.aggregate, "top_ranked_filter": str(ranking.iloc[0]["filter"]) if not ranking.empty else None},
                uncertainty=first.uncertainty,
            )
    return summaries
