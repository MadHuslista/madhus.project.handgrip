# @package handgrip_analysis.stages.common
# @brief Shared helper utilities for stage analyzers.

"""Common helpers for stage analyzers."""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from ..aggregation import aggregate_condition_results
from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec


# @brief Build common per-trial metadata metrics.
# @param spec Trial specification.
# @return Dictionary of shared scalar metrics.
def base_metrics(spec: TrialSpec) -> dict[str, object]:
    return {
        "capture_file": spec.path.name,
        "load_nominal_n": spec.load_nominal_n,
    }


# @brief Convert arbitrary value to finite float or NaN.
# @param value Input scalar value.
# @return Finite float value or NaN.
def finite_or_nan(value: object) -> float:
    try:
        out = float(value)
    except Exception:
        return float("nan")
    return out if np.isfinite(out) else float("nan")


# @brief Flatten a sampling metrics mapping with a prefix.
# @param prefix Prefix for output keys.
# @param sampling Sampling metrics mapping.
# @return Flattened prefixed metrics dictionary.
def flatten_sampling(prefix: str, sampling: Mapping[str, object]) -> dict[str, float]:
    return {f"{prefix}_{k}": finite_or_nan(v) for k, v in sampling.items()}


# @brief Run default condition aggregation over trial results.
# @param results Trial results sequence.
# @param cfg Stage configuration.
# @return Condition summary list.
def summarize_default(results: Sequence[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return aggregate_condition_results(
        results,
        confidence_level=cfg.confidence_level,
        n_resamples=cfg.bootstrap_resamples,
        random_seed=cfg.random_seed,
    )


# @brief Compute compact scalar metrics from a numeric table.
# @param prefix Prefix for generated metric keys.
# @param df Input DataFrame.
# @param value_col Optional numeric column used for max/median summaries.
# @return Dictionary of compact numeric metrics.
def numeric_table_to_metrics(prefix: str, df: pd.DataFrame, value_col: str | None = None) -> dict[str, float]:
    """
    Return compact numeric metrics from a table.

    Used for tables whose full content is stored separately but where a summary
    scalar is useful in the per-trial metrics table.
    """
    if df.empty:
        return {f"{prefix}_n_rows": 0.0}
    metrics: dict[str, float] = {f"{prefix}_n_rows": float(len(df))}
    if value_col is not None and value_col in df.columns:
        values = df[value_col].to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if finite.size:
            metrics[f"{prefix}_{value_col}_max"] = float(np.max(finite))
            metrics[f"{prefix}_{value_col}_median"] = float(np.median(finite))
    return metrics
