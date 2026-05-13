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

STANDARD_ARTIFACT_FILENAMES = {
    "plan": "plan.json",
    "per_trial_metrics": "per_trial_metrics.csv",
    "condition_summary": "condition_summary.csv",
    "summary": "summary.json",
}


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


def _ensure_phase3_directories(outdir: Path) -> dict[str, Path]:
    """Create the standard Phase 3 directory family."""
    dirs = {
        "figures": ensure_dir(outdir / "figures"),
        "figures_per_trial": ensure_dir(outdir / "figures" / "per_trial"),
        "figures_aggregate": ensure_dir(outdir / "figures" / "aggregate"),
        "tables": ensure_dir(outdir / "tables"),
    }
    # Keep empty directories visible in zip handoffs and git worktrees.
    for key in ("figures_per_trial", "figures_aggregate"):
        readme = dirs[key] / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Generated figures\n\n"
                "This directory is part of the standard Phase 3 output contract. "
                "Stage-specific plotting can populate it without changing the artifact layout.\n",
                encoding="utf-8",
            )
    return dirs


def _write_stage6_outputs(
    outdir: Path,
    cfg: StageConfig,
    results: Sequence[TrialResult],
    paths: dict[str, Path],
) -> None:
    """Write Stage 6-specific Phase 3 artifacts."""
    if not results:
        return
    from .stages.stage6_filters import filter_acceptance_markdown, stage6_artifact_tables

    tables = stage6_artifact_tables(list(results), cfg)
    for name in ["filter_per_trial_metrics", "filter_validation_scores", "filter_ranking_summary"]:
        table_path = outdir / f"{name}.csv"
        save_csv(table_path, tables.get(name, pd.DataFrame()))
        paths[name] = table_path

    ranking = tables.get("filter_ranking_summary", pd.DataFrame())
    report_path = outdir / "filter_acceptance_report.md"
    report_path.write_text(filter_acceptance_markdown(ranking, cfg), encoding="utf-8")
    paths["filter_acceptance_report"] = report_path


def write_stage_outputs(
    plan: AnalysisPlan,
    cfg: StageConfig,
    results: Sequence[TrialResult],
    summaries: Sequence[ConditionSummary],
) -> dict[str, Path]:
    """Write standard Phase 3 artifacts for a completed stage plan.

    Required artifact family for every stage:

    - ``plan.json``
    - ``per_trial_metrics.csv``
    - ``condition_summary.csv``
    - ``summary.json``
    - ``figures/per_trial/``
    - ``figures/aggregate/``

    Stage 6 additionally writes the filter-review contract files.
    """
    outdir = ensure_dir(plan.outdir)
    dirs = _ensure_phase3_directories(outdir)
    paths: dict[str, Path] = {}

    plan_path = outdir / STANDARD_ARTIFACT_FILENAMES["plan"]
    save_json(plan_path, plan.to_record())
    paths["plan"] = plan_path

    per_trial = trial_results_frame(results)
    per_trial_path = outdir / STANDARD_ARTIFACT_FILENAMES["per_trial_metrics"]
    save_csv(per_trial_path, per_trial)
    paths["per_trial_metrics"] = per_trial_path

    condition_df = condition_summaries_frame(summaries)
    condition_path = outdir / STANDARD_ARTIFACT_FILENAMES["condition_summary"]
    save_csv(condition_path, condition_df)
    paths["condition_summary"] = condition_path

    table_dir = dirs["tables"]
    for name, df in _collect_named_tables(results).items():
        table_path = table_dir / f"{name}.csv"
        save_csv(table_path, df)
        paths[f"table_{name}"] = table_path

    if plan.stage.startswith("stage6"):
        _write_stage6_outputs(outdir, cfg, results, paths)

    summary = {
        "stage": plan.stage,
        "outdir": str(outdir),
        "n_trials": len(results),
        "n_conditions": len(summaries),
        "conditions": [summary.to_record() for summary in summaries],
        "standard_artifacts": STANDARD_ARTIFACT_FILENAMES,
        "standard_directories": {key: str(value) for key, value in dirs.items()},
        "artifacts": {key: str(path) for key, path in paths.items()},
    }
    summary_path = outdir / STANDARD_ARTIFACT_FILENAMES["summary"]
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
    """End-to-end pipeline: load, validate, plan, execute, write."""
    trials = load_manifest(manifest_path)
    plan = build_analysis_plan(trials, stage=stage, condition=condition, trial_type=trial_type, outdir=outdir)
    stage_cfg = cfg or StageConfig(stage=stage)
    results, summaries = execute_plan(plan, stage_cfg)
    return write_stage_outputs(plan, stage_cfg, results, summaries)
