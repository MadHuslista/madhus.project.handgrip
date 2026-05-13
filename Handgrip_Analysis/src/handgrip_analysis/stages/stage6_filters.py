"""Stage 6 — combined filter review + design over repeated rest/dynamic trials."""

from __future__ import annotations

import logging
import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..aggregation import aggregate_condition_results
from ..config import DSPConfig
from ..config.schema import Stage6ScoringConfig
from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec
from ..dsp import (
    PSD_FLOOR_LINEAR,
    apply_filter_spec,
    bandpower,
    best_event_metrics,
    load_filter_specs,
    welch_psd,
)
from ..io import load_capture, sampling_summary
from .common import base_metrics, flatten_sampling

log = logging.getLogger(__name__)


def _get_dsp_cfg(cfg: StageConfig) -> DSPConfig:
    if hasattr(cfg, "dsp") and isinstance(cfg.dsp, DSPConfig):
        return cfg.dsp
    return DSPConfig()


def _get_scoring_cfg(cfg: StageConfig) -> Stage6ScoringConfig:
    """Extract Stage6ScoringConfig from StageConfig, or use defaults."""
    if hasattr(cfg, "stage6_scoring") and isinstance(cfg.stage6_scoring, Stage6ScoringConfig):
        return cfg.stage6_scoring
    return Stage6ScoringConfig()


def _filter_specs(cfg: StageConfig) -> list[dict[str, Any]]:
    if cfg.filter_config is None:
        raise ValueError("Stage 6 requires filter_config=<path>")
    return load_filter_specs(cfg.filter_config)


def _spec_map(cfg: StageConfig) -> dict[str, dict[str, Any]]:
    return {str(spec["name"]): spec for spec in _filter_specs(cfg)}


def _is_rest_trial(spec: TrialSpec) -> bool:
    text = " ".join([spec.stage, spec.condition, spec.trial_type]).lower()
    return "rest" in text or "noise" in text or "static" in text


def _is_dynamic_trial(spec: TrialSpec) -> bool:
    return not _is_rest_trial(spec)


def _dynamic_preference(spec: TrialSpec) -> tuple[int, str]:
    text = " ".join([spec.condition, spec.trial_type]).lower()
    if "ramp_hold" in text or ("ramp" in text and "hold" in text):
        return (0, text)
    if "sustained_hold" in text or "hold" in text:
        return (1, text)
    if "fast_max" in text or "fast" in text:
        return (2, text)
    return (3, text)


def choose_representative_dynamic_trial(results: list[TrialResult]) -> TrialResult | None:
    dynamic_results = [result for result in results if str(result.metrics.get("trial_kind", "")).lower() == "dynamic"]
    if not dynamic_results:
        return None
    dynamic_results.sort(
        key=lambda result: (_dynamic_preference(result.spec), result.spec.session_id, result.spec.trial_id)
    )
    return dynamic_results[0]


def analyze_trial(spec: TrialSpec, cfg: StageConfig) -> TrialResult:
    """
    Evaluate every candidate filter on one rest or dynamic trial.

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

    raw_event = (
        best_event_metrics(
            y,
            cap.time_s,
            fs,
            baseline_s=cfg.baseline_s,
            threshold_sigma=cfg.threshold_sigma,
            min_duration_s=cfg.min_duration_s,
            merge_gap_s=cfg.merge_gap_s,
            pad_s=cfg.pad_s,
        )
        if trial_kind == "dynamic"
        else {}
    )
    dsp = _get_dsp_cfg(cfg)
    raw_std = float(pd.Series(y).std())
    f_raw, p_raw = welch_psd(
        y, fs,
        max_nperseg=dsp.welch.max_nperseg,
        min_nperseg=dsp.welch.min_nperseg,
        window=dsp.welch.window,
    )
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
            f_f, p_f = welch_psd(
                y_f, fs,
                max_nperseg=dsp.welch.max_nperseg,
                min_nperseg=dsp.welch.min_nperseg,
                window=dsp.welch.window,
            )
            hf = bandpower(f_f, p_f, hf_lo, hf_hi)
            row.update(
                {
                    "rest_std": float(pd.Series(y_f).std()),
                    "rest_std_norm": float(pd.Series(y_f).std()) / max(raw_std, 1e-12),
                    "rest_hf_bandpower": hf,
                    "rest_hf_bandpower_norm": hf / max(raw_hf, PSD_FLOOR_LINEAR) if np.isfinite(raw_hf) else float("nan"),
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


REVIEW_METRIC_COLUMNS = [
    "rest_std_norm",
    "rest_hf_bandpower_norm",
    "peak_relative_error",
    "rise_relative_error",
    "peak_time_shift_s",
    "dfdt_deviation",
]


def _score_filter_rows(df: pd.DataFrame, cfg: StageConfig) -> pd.DataFrame:
    rows = []
    for filter_name, group in df.groupby("filter", dropna=False):
        row: dict[str, object] = {
            "filter": filter_name,
            "n_trials": int(group[["session_id", "trial_id"]].drop_duplicates().shape[0]),
        }
        for col in REVIEW_METRIC_COLUMNS:
            if col in group.columns:
                values = pd.to_numeric(group[col], errors="coerce").dropna().astype(float)
                row[f"{col}__median"] = float(values.median()) if not values.empty else float("nan")
                row[f"{col}__mean"] = float(values.mean()) if not values.empty else float("nan")
        w = cfg.filter_weights
        rest_std = float(row.get("rest_std_norm__median", np.nan))
        peak = float(row.get("peak_relative_error__median", np.nan))
        rise = float(row.get("rise_relative_error__median", np.nan))
        time_shift = abs(float(row.get("peak_time_shift_s__median", np.nan))) / 0.1
        dfdt = float(row.get("dfdt_deviation__median", np.nan))
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
        out.insert(0, "review_rank", np.arange(1, len(out) + 1))
    return out


def _design_weighted_score(row: Mapping[str, Any]) -> float:
    """
    Representative-trial fidelity score; lower is better.

    The design pass intentionally emphasizes waveform preservation more than the
    multi-trial review pass. It is used to rank filters on a representative
    dynamic trial after the broad review has already measured robustness.
    """
    values = {
        "peak_relative_error": float(row.get("peak_relative_error", np.nan)),
        "rise_relative_error": float(row.get("rise_relative_error", np.nan)),
        "peak_time_shift_norm": abs(float(row.get("peak_time_shift_s", np.nan))) / 0.1,
        "dfdt_deviation": float(row.get("dfdt_deviation", np.nan)),
    }
    weights = {
        "peak_relative_error": 0.45,
        "rise_relative_error": 0.20,
        "peak_time_shift_norm": 0.15,
        "dfdt_deviation": 0.20,
    }
    score = 0.0
    weight_sum = 0.0
    for key, value in values.items():
        if np.isfinite(value):
            score += weights[key] * value
            weight_sum += weights[key]
    return score / weight_sum if weight_sum else float("nan")


def build_stage6_design_assessment(results: list[TrialResult], cfg: StageConfig) -> pd.DataFrame:
    representative = choose_representative_dynamic_trial(results)
    if representative is None:
        return pd.DataFrame()

    filter_df = representative.tables.get("filter_metrics", pd.DataFrame()).copy()
    if filter_df.empty:
        return pd.DataFrame()

    filter_df["design_score"] = filter_df.apply(_design_weighted_score, axis=1)
    filter_df.insert(0, "representative_session_id", representative.spec.session_id)
    filter_df.insert(1, "representative_trial_id", representative.spec.trial_id)
    filter_df.insert(2, "representative_condition", representative.spec.condition)
    filter_df = filter_df.sort_values("design_score", ascending=True).reset_index(drop=True)
    filter_df.insert(0, "design_rank", np.arange(1, len(filter_df) + 1))
    return filter_df


def _normalized(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    finite = values[np.isfinite(values)]
    if finite.empty:
        return pd.Series([np.nan] * len(values), index=values.index)
    lo = float(finite.min())
    hi = float(finite.max())
    if math.isclose(lo, hi):
        return pd.Series([0.0 if np.isfinite(v) else np.nan for v in values], index=values.index)
    return (values - lo) / (hi - lo)


def build_stage6_decision_table(review_ranking: pd.DataFrame, design_assessment: pd.DataFrame) -> pd.DataFrame:
    if review_ranking.empty and design_assessment.empty:
        return pd.DataFrame()
    review_cols = [
        c
        for c in review_ranking.columns
        if c in {"filter", "review_rank", "composite_score", "n_trials"} or c.endswith("__median")
    ]
    design_cols = [
        c
        for c in design_assessment.columns
        if c
        in {
            "filter",
            "design_rank",
            "design_score",
            "representative_session_id",
            "representative_trial_id",
            "representative_condition",
            "peak_relative_error",
            "rise_relative_error",
            "peak_time_shift_s",
            "dfdt_deviation",
            "max_dfdt_ratio",
        }
    ]
    merged = pd.merge(
        review_ranking[review_cols] if review_cols else pd.DataFrame({"filter": []}),
        design_assessment[design_cols] if design_cols else pd.DataFrame({"filter": []}),
        on="filter",
        how="outer",
    )
    merged["review_score_norm"] = (
        _normalized(merged.get("composite_score", pd.Series(dtype=float))) if "composite_score" in merged else np.nan
    )
    merged["design_score_norm"] = (
        _normalized(merged.get("design_score", pd.Series(dtype=float))) if "design_score" in merged else np.nan
    )
    review_component = pd.to_numeric(merged.get("review_score_norm"), errors="coerce")
    design_component = pd.to_numeric(merged.get("design_score_norm"), errors="coerce")
    scoring = Stage6ScoringConfig()  # default weights; caller can pass via cfg if needed
    merged["combined_score"] = (
        scoring.review_weight * review_component.fillna(0.0)
        + scoring.design_weight * design_component.fillna(0.0)
    )
    # Penalize rows missing one side of the decision.
    merged.loc[review_component.isna() | design_component.isna(), "combined_score"] += 0.25
    merged = merged.sort_values(
        ["combined_score", "review_rank", "design_rank"], ascending=[True, True, True]
    ).reset_index(drop=True)
    merged.insert(0, "final_rank", np.arange(1, len(merged) + 1))
    return merged


def summarize_trials(results: list[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
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
        if summaries:
            first = summaries[0]
            summaries[0] = ConditionSummary(
                stage=first.stage,
                condition=first.condition,
                n_trials=first.n_trials,
                metrics=ranking,
                aggregate={
                    **first.aggregate,
                    "top_ranked_filter": str(ranking.iloc[0]["filter"]) if not ranking.empty else None,
                },
                uncertainty=first.uncertainty,
            )
    return summaries


def stage6_artifact_tables(results: list[TrialResult], cfg: StageConfig) -> dict[str, pd.DataFrame]:
    """Return Stage 6 artifact tables for both review and design passes."""
    filter_tables = [result.tables.get("filter_metrics") for result in results if "filter_metrics" in result.tables]
    per_trial = pd.concat(filter_tables, ignore_index=True) if filter_tables else pd.DataFrame()
    ranking = _score_filter_rows(per_trial, cfg) if not per_trial.empty else pd.DataFrame()
    validation_scores = ranking.copy()
    if not validation_scores.empty:
        validation_scores.insert(0, "validation_mode", "aggregate_all_trials_phase3")

    design_assessment = build_stage6_design_assessment(results, cfg)
    decision_table = build_stage6_decision_table(ranking, design_assessment)

    return {
        "filter_per_trial_metrics": per_trial,
        "filter_validation_scores": validation_scores,
        "filter_ranking_summary": ranking,
        "filter_design_assessment": design_assessment,
        "filter_decision_summary": decision_table,
    }


def select_final_filter(decision_table: pd.DataFrame, cfg: StageConfig) -> dict[str, Any]:
    if decision_table.empty:
        return {}
    top = decision_table.iloc[0].to_dict()
    spec = _spec_map(cfg).get(str(top.get("filter", "")), {})
    return {**top, "filter_spec": spec}


def lsl_bridge_processing_snippet(selected: Mapping[str, Any], sample_rate_hz: float = 100.0) -> dict[str, Any]:
    """
    Translate the chosen Handgrip_Analysis filter into an LSL_Bridge config snippet.

    Only a subset of candidate types map directly to the current LSL_Bridge
    implementation. Unsupported selections still produce a structured payload
    indicating that manual implementation is required.
    """
    filter_name = str(selected.get("filter", ""))
    spec = dict(selected.get("filter_spec", {}))
    snippet: dict[str, Any] = {"processing": {"filters": []}}
    if not spec:
        snippet["note"] = "No selected filter spec available."
        return snippet

    filter_type = str(spec.get("type", ""))
    if filter_type == "identity":
        snippet["processing"]["filters"] = [{"type": "identity", "name": filter_name}]
        return snippet
    if filter_type == "butter_lowpass" and int(spec.get("order", 2)) == 2:
        snippet["processing"]["filters"] = [
            {
                "type": "butterworth_lowpass_2nd",
                "name": filter_name,
                "sample_rate_hz": float(spec.get("sample_rate_hz", sample_rate_hz)),
                "cutoff_hz": float(spec["cutoff_hz"]),
                "q": float(spec.get("q", 1.0 / math.sqrt(2.0))),
                "reset_on_gap_s": float(spec.get("reset_on_gap_s", 1.0)),
                "min_dt_s": float(spec.get("min_dt_s", 1e-6)),
            }
        ]
        return snippet
    if filter_type == "one_pole_lowpass":
        snippet["processing"]["filters"] = [
            {
                "type": "lowpass_1pole",
                "name": filter_name,
                "cutoff_hz": float(spec["cutoff_hz"]),
                "reset_on_gap_s": float(spec.get("reset_on_gap_s", 1.0)),
                "min_dt_s": float(spec.get("min_dt_s", 1e-6)),
            }
        ]
        return snippet

    snippet["note"] = (
        f"Selected filter '{filter_name}' of type '{filter_type}' does not map directly to the current "
        "LSL_Bridge processing module. Manual implementation or filter substitution is required."
    )
    return snippet


def filter_acceptance_markdown(ranking: pd.DataFrame, cfg: StageConfig) -> str:
    lines: list[str] = [
        "# Stage 6 Filter Acceptance Report",
        "",
        "## Summary",
        "",
    ]
    if ranking.empty:
        lines.extend([
            "No filter ranking rows were generated.",
            "",
            "Check that the manifest includes Stage 6 rest and/or dynamic trials and that `filter_config` points to valid candidates.",
        ])
        return "\n".join(lines) + "\n"

    top = ranking.iloc[0]
    lines.extend(
        [
            f"- Top review-ranked filter: `{top.get('filter')}`",
            f"- Composite review score: `{top.get('composite_score')}`",
            f"- Trials represented: `{top.get('n_trials')}`",
            "",
            "## Review Ranking",
            "",
            "| rank | filter | composite_score | n_trials |",
            "|---:|---|---:|---:|",
        ]
    )
    for _, row in ranking.reset_index(drop=True).iterrows():
        lines.append(
            f"| {row.get('review_rank')} | `{row.get('filter')}` | {row.get('composite_score')} | {row.get('n_trials')} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Stage 6 now runs both the multi-trial candidate review and the representative-trial design pass.",
            "- The final recommendation should be taken from `filter_decision_summary.csv` and the detailed markdown design report.",
            "- Phase 4 should still upgrade this to grouped cross-trial validation, e.g. leave-one-session-out with leave-one-trial-out fallback.",
        ]
    )
    return "\n".join(lines) + "\n"
