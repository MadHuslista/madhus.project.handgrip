# @package handgrip_analysis.pipeline
# @brief Validation, planning, and execution pipeline for trial-aware analysis.

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
from .plotting import generate_stage_figures
from .report import save_csv, save_json
from .stages import get_stage_module

log = logging.getLogger(__name__)

STANDARD_ARTIFACT_FILENAMES = {
    "plan": "plan.json",
    "per_trial_metrics": "per_trial_metrics.csv",
    "condition_summary": "condition_summary.csv",
    "summary": "summary.json",
}


# @brief Build an analysis plan for a selected stage and trial subset.
# @param trials All manifest trials.
# @param stage Stage key to run.
# @param outdir Output directory path.
# @param condition Optional condition filter.
# @param trial_type Optional trial-type filter.
# @return AnalysisPlan describing selected trials and output path.
# @throws StageExecutionError Raised when no trials match requested filters.
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


# @brief Execute stage analyzers for every trial in a plan.
# @param plan Precomputed analysis plan.
# @param cfg Stage configuration.
# @return Tuple of trial results and condition summaries.
def execute_plan(plan: AnalysisPlan, cfg: StageConfig) -> tuple[list[TrialResult], list[ConditionSummary]]:
    """Execute trial analyzers and aggregate their results."""
    module = get_stage_module(plan.stage)
    results: list[TrialResult] = []
    for spec in plan.trials:
        log.info("execute_plan: %s %s", spec.stage, spec.identity)
        results.append(module.analyze_trial(spec, cfg))
    summaries = module.summarize_trials(results, cfg)
    return results, summaries


# @brief Merge per-trial named tables into stage-level tables.
# @param results Sequence of trial results.
# @return Dictionary of table name to concatenated DataFrame.
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


# @brief Create the standard Phase 3 output directory structure.
# @param outdir Stage output root.
# @return Dictionary of standard directory names to paths.
def _ensure_phase3_directories(outdir: Path) -> dict[str, Path]:
    """Create the standard Phase 3 directory family."""
    dirs = {
        "figures": ensure_dir(outdir / "figures"),
        "figures_per_trial": ensure_dir(outdir / "figures" / "per_trial"),
        "figures_aggregate": ensure_dir(outdir / "figures" / "aggregate"),
        "tables": ensure_dir(outdir / "tables"),
    }
    for key in ("figures_per_trial", "figures_aggregate"):
        readme = dirs[key] / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Generated figures\n\n"
                "This directory is populated by the manifest-driven pipeline. "
                "If this README is the only file present, plotting failed or no plottable trials were selected.\n",
                encoding="utf-8",
            )
    return dirs


# @brief Write Stage 6-specific artifact tables and acceptance report.
# @param outdir Stage output root.
# @param cfg Stage configuration.
# @param results Sequence of trial results.
# @param paths Mutable artifact path dictionary to update.
# @return In-memory Stage 6 artifact tables.
def _write_stage6_tables(
    outdir: Path,
    cfg: StageConfig,
    results: Sequence[TrialResult],
    paths: dict[str, Path],
) -> dict[str, pd.DataFrame]:
    """Write Stage 6-specific CSV artifacts and return the in-memory tables."""
    if not results:
        return {}
    from .stages.stage6_filters import filter_acceptance_markdown, stage6_artifact_tables

    tables = stage6_artifact_tables(list(results), cfg)
    for name, table in tables.items():
        table_path = outdir / f"{name}.csv"
        save_csv(table_path, table)
        paths[name] = table_path

    ranking = tables.get("filter_ranking_summary", pd.DataFrame())
    report_path = outdir / "filter_acceptance_report.md"
    report_path.write_text(filter_acceptance_markdown(ranking, cfg), encoding="utf-8")
    paths["filter_acceptance_report"] = report_path
    return tables


# @brief Write all standard artifacts for a completed stage execution.
# @param plan Executed analysis plan.
# @param cfg Stage configuration.
# @param results Trial-level results.
# @param summaries Condition-level summaries.
# @param all_trials Optional full manifest trial set for Stage 6 context.
# @return Dictionary mapping artifact keys to filesystem paths.
def write_stage_outputs(
    plan: AnalysisPlan,
    cfg: StageConfig,
    results: Sequence[TrialResult],
    summaries: Sequence[ConditionSummary],
    *,
    all_trials: Sequence[TrialSpec] | None = None,
) -> dict[str, Path]:
    """Write standard Phase 3 artifacts for a completed stage plan."""
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

    stage6_tables: dict[str, pd.DataFrame] = {}
    if plan.stage.startswith("stage6"):
        stage6_tables = _write_stage6_tables(outdir, cfg, results, paths)

    figure_paths = generate_stage_figures(plan, cfg, results, summaries, dirs)
    for key, figure_path in figure_paths.items():
        paths[key] = figure_path

    if plan.stage.startswith("stage6"):
        from .stage6_report import write_stage6_report

        extra_paths = write_stage6_report(
            outdir=outdir,
            cfg=cfg,
            all_trials=tuple(all_trials or plan.trials),
            artifact_tables=stage6_tables,
            figure_paths=figure_paths,
        )
        paths.update(extra_paths)

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


# @brief Run full manifest pipeline: load, plan, execute, and write outputs.
# @param manifest_path Trial manifest CSV path.
# @param stage Stage key to run.
# @param outdir Output directory path.
# @param cfg Optional stage configuration override.
# @param condition Optional condition filter.
# @param trial_type Optional trial-type filter.
# @return Dictionary of generated artifact paths.
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
    return write_stage_outputs(plan, stage_cfg, results, summaries, all_trials=trials)
