"""Condition-level aggregation utilities."""
from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from .domain import ConditionSummary, Metrics, TrialResult
from .uncertainty import bootstrap_ci, robust_summary

IDENTITY_COLUMNS = {
    "stage",
    "condition",
    "trial_type",
    "trial_id",
    "session_id",
    "path",
    "channel",
    "include",
    "load_nominal_n",
    "notes",
}


def trial_results_frame(results: Sequence[TrialResult]) -> pd.DataFrame:
    """Convert trial results to a flat DataFrame."""
    return pd.DataFrame([result.metrics_record() for result in results])


def aggregate_condition_results(
    results: Sequence[TrialResult],
    *,
    confidence_level: float = 0.95,
    n_resamples: int = 5000,
    random_seed: int = 42,
) -> list[ConditionSummary]:
    """Aggregate scalar trial metrics into condition summaries."""
    frame = trial_results_frame(results)
    if frame.empty:
        return []
    summaries: list[ConditionSummary] = []
    numeric_cols = [c for c in frame.select_dtypes(include="number").columns if c not in IDENTITY_COLUMNS]
    for (stage, condition), group in frame.groupby(["stage", "condition"], dropna=False):
        aggregate: Metrics = {}
        uncertainty: Metrics = {}
        for col in numeric_cols:
            stats = robust_summary(group[col].to_numpy(dtype=float))
            aggregate[f"{col}__median"] = stats["median"]
            aggregate[f"{col}__mean"] = stats["mean"]
            aggregate[f"{col}__std"] = stats["std"]
            aggregate[f"{col}__p90"] = stats["p90"]
            lo, hi = bootstrap_ci(
                group[col].to_numpy(dtype=float),
                statistic="median",
                confidence_level=confidence_level,
                n_resamples=n_resamples,
                random_seed=random_seed,
            )
            uncertainty[f"{col}__median_ci_low"] = lo
            uncertainty[f"{col}__median_ci_high"] = hi
        summaries.append(
            ConditionSummary(
                stage=str(stage),
                condition=str(condition),
                n_trials=int(len(group)),
                metrics=group.reset_index(drop=True),
                aggregate=aggregate,
                uncertainty=uncertainty,
            )
        )
    return summaries


def condition_summaries_frame(summaries: Sequence[ConditionSummary]) -> pd.DataFrame:
    """Convert condition summaries into one flat table."""
    return pd.DataFrame([summary.to_record() for summary in summaries])
