"""Uncertainty helpers for trial-level aggregation."""
from __future__ import annotations

from typing import Iterable, Literal

import numpy as np
import pandas as pd
from scipy import stats

StatisticName = Literal["mean", "median", "std", "p90", "p95"]


def finite_array(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)]


def statistic_value(values: Iterable[float], statistic: StatisticName = "median") -> float:
    arr = finite_array(values)
    if arr.size == 0:
        return float("nan")
    if statistic == "mean":
        return float(np.mean(arr))
    if statistic == "median":
        return float(np.median(arr))
    if statistic == "std":
        return float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    if statistic == "p90":
        return float(np.percentile(arr, 90))
    if statistic == "p95":
        return float(np.percentile(arr, 95))
    raise ValueError(f"Unsupported statistic: {statistic!r}")


def robust_summary(values: Iterable[float]) -> dict[str, float | int]:
    """Return robust descriptive statistics for repeated trial metrics."""
    arr = finite_array(values)
    if arr.size == 0:
        return {
            "n": 0,
            "mean": float("nan"),
            "median": float("nan"),
            "std": float("nan"),
            "iqr": float("nan"),
            "p10": float("nan"),
            "p90": float("nan"),
        }
    q10, q25, q50, q75, q90 = np.percentile(arr, [10, 25, 50, 75, 90])
    return {
        "n": int(arr.size),
        "mean": float(np.mean(arr)),
        "median": float(q50),
        "std": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "iqr": float(q75 - q25),
        "p10": float(q10),
        "p90": float(q90),
    }


def bootstrap_ci(
    values: Iterable[float],
    *,
    statistic: StatisticName = "median",
    confidence_level: float = 0.95,
    n_resamples: int = 5000,
    random_seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap confidence interval for a scalar statistic.

    For fewer than two finite values the interval collapses to the observed
    statistic.  This keeps early calibration sessions usable while still making
    the small-n limitation explicit through the reported ``n`` column.
    """
    arr = finite_array(values)
    if arr.size == 0:
        return float("nan"), float("nan")
    center = statistic_value(arr, statistic)
    if arr.size < 2:
        return center, center

    def func(x: np.ndarray, axis: int = -1) -> np.ndarray:
        if statistic == "mean":
            return np.mean(x, axis=axis)
        if statistic == "median":
            return np.median(x, axis=axis)
        if statistic == "std":
            return np.std(x, axis=axis, ddof=1)
        if statistic == "p90":
            return np.percentile(x, 90, axis=axis)
        if statistic == "p95":
            return np.percentile(x, 95, axis=axis)
        raise ValueError(statistic)

    try:
        res = stats.bootstrap(
            (arr,),
            func,
            vectorized=True,
            confidence_level=confidence_level,
            n_resamples=n_resamples,
            method="basic",
            random_state=random_seed,
        )
        return float(res.confidence_interval.low), float(res.confidence_interval.high)
    except Exception:
        # Degenerate data can make scipy's bootstrap emit errors/warnings.  A
        # collapsed interval is more useful than failing the whole analysis.
        return center, center


def summarize_numeric_frame(
    df: pd.DataFrame,
    *,
    group_cols: list[str],
    confidence_level: float = 0.95,
    n_resamples: int = 5000,
    random_seed: int = 42,
) -> pd.DataFrame:
    """Aggregate every numeric column by group using robust trial summaries."""
    numeric_cols = [c for c in df.select_dtypes(include="number").columns if c not in group_cols]
    rows: list[dict[str, object]] = []
    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys, strict=True))
        row["n_trials"] = int(len(group))
        for col in numeric_cols:
            summary = robust_summary(group[col].to_numpy(dtype=float))
            row[f"{col}__median"] = summary["median"]
            row[f"{col}__mean"] = summary["mean"]
            row[f"{col}__std"] = summary["std"]
            row[f"{col}__iqr"] = summary["iqr"]
            lo, hi = bootstrap_ci(
                group[col].to_numpy(dtype=float),
                statistic="median",
                confidence_level=confidence_level,
                n_resamples=n_resamples,
                random_seed=random_seed,
            )
            row[f"{col}__median_ci_low"] = lo
            row[f"{col}__median_ci_high"] = hi
        rows.append(row)
    return pd.DataFrame(rows)
