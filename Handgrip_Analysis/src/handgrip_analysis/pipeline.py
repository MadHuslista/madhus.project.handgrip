"""Validation → plan → execute pipeline for trial-aware analysis."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import pandas as pd

from .aggregation import condition_summaries_frame, trial_results_frame
from .domain import AnalysisPlan, ConditionSummary, StageConfig, StageExecutionError, TrialResult, TrialSpec
from .io import ensure_dir
from .manifest import filter_trials, load_manifest
from .report import save_csv, save_json
from .stages import get_stage_module

log = logging.getLogger(__name__)


def build_analysis_plan(
    trials: Sequence[TrialSpec],
    *,
    stage: str,
    outdir: str | Path,
    condition: str | None = None,
    trial_type: str | None = None,
) -> AnalysisPlan:
    """Compute the complete analysis plan before writing outputs."""
    selected = filter_trials(trials, stage=stage, condition=condition, trial_type=trial_type)
    if not selected:
        raise StageExecutionError(
            f"No included trials matched stage={stage!r}, condition={condition!r}, trial_type={trial_type!r}"
        )
    return AnalysisPlan(stage=stage, trials=tuple(selected), outdir=Path(outdir))


def execute_plan(plan: AnalysisPlan, cfg: StageConfig) -> tuple[list[TrialResult], list[ConditionSummary]]:
    """Execute trial analyzers and aggregate their results."""
    module = get_stage_module(plan.stage)
    results: list[TrialResult] = []
    for spec in plan.trials:
        log.info("execute_plan: %s %s", spec.stage, spec.identity)
        results.append(module.analyze_trial(spec, cfg))
    summaries = module.summarize_trials(results, cfg)
    return results, summaries


def _collect_named_tables(results: Sequence[TrialResult]) -> dict[str, pd.DataFrame]:
    tables: dict[str, list[pd.DataFrame]] = {}
    for result in results:
        identity = result.spec.to_record()
        for name, table in result.tables.items():
            if table is None or table.empty:
                continue
            df = table.copy()
            for col, value in reversed(identity.items()):
                if col not in df.columns:
                    df.insert(0, col, value)
            tables.setdefault(name, []).append(df)
    return {name: pd.concat(frames, ignore_index=True) for name, frames in tables.items() if frames}


def write_stage_outputs(
    plan: AnalysisPlan,
    cfg: StageConfig,
    results: Sequence[TrialResult],
    summaries: Sequence[ConditionSummary],
) -> dict[str, Path]:
    """Write standard Phase 1 artifacts for a completed stage plan."""
    outdir = ensure_dir(plan.outdir)
    paths: dict[str, Path] = {}

    plan_path = outdir / "plan.json"
    save_json(plan_path, plan.to_record())
    paths["plan"] = plan_path

    per_trial = trial_results_frame(results)
    per_trial_path = outdir / "per_trial_metrics.csv"
    save_csv(per_trial_path, per_trial)
    paths["per_trial_metrics"] = per_trial_path

    condition_df = condition_summaries_frame(summaries)
    condition_path = outdir / "condition_summary.csv"
    save_csv(condition_path, condition_df)
    paths["condition_summary"] = condition_path

    table_dir = ensure_dir(outdir / "tables")
    for name, df in _collect_named_tables(results).items():
        table_path = table_dir / f"{name}.csv"
        save_csv(table_path, df)
        paths[f"table_{name}"] = table_path

    summary = {
        "stage": plan.stage,
        "outdir": str(outdir),
        "n_trials": len(results),
        "n_conditions": len(summaries),
        "conditions": [summary.to_record() for summary in summaries],
        "artifacts": {key: str(path) for key, path in paths.items()},
    }
    summary_path = outdir / "summary.json"
    save_json(summary_path, summary)
    paths["summary"] = summary_path
    return paths


def run_manifest_analysis(
    *,
    manifest_path: str | Path,
    stage: str,
    outdir: str | Path,
    cfg: StageConfig | None = None,
    condition: str | None = None,
    trial_type: str | None = None,
) -> dict[str, Path]:
    """End-to-end Phase 1 pipeline: load, validate, plan, execute, write."""
    trials = load_manifest(manifest_path)
    plan = build_analysis_plan(trials, stage=stage, condition=condition, trial_type=trial_type, outdir=outdir)
    stage_cfg = cfg or StageConfig(stage=stage)
    results, summaries = execute_plan(plan, stage_cfg)
    return write_stage_outputs(plan, stage_cfg, results, summaries)
