"""Common helpers for stage analyzers."""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from ..aggregation import aggregate_condition_results
from ..domain import ConditionSummary, StageConfig, TrialResult, TrialSpec


def base_metrics(spec: TrialSpec) -> dict[str, object]:
    return {
        "capture_file": spec.path.name,
        "load_nominal_n": spec.load_nominal_n,
    }


def finite_or_nan(value: object) -> float:
    try:
        out = float(value)
    except Exception:
        return float("nan")
    return out if np.isfinite(out) else float("nan")


def flatten_sampling(prefix: str, sampling: Mapping[str, object]) -> dict[str, float]:
    return {f"{prefix}_{k}": finite_or_nan(v) for k, v in sampling.items()}


def summarize_default(results: Sequence[TrialResult], cfg: StageConfig) -> list[ConditionSummary]:
    return aggregate_condition_results(
        results,
        confidence_level=cfg.confidence_level,
        n_resamples=cfg.bootstrap_resamples,
        random_seed=cfg.random_seed,
    )


def numeric_table_to_metrics(prefix: str, df: pd.DataFrame, value_col: str | None = None) -> dict[str, float]:
    """Return compact numeric metrics from a table.

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
