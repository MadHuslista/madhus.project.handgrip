"""Relaxation/artifact helpers for static calibration holds.

The functions in this module intentionally stay offline and optional.  They
characterise and compensate fixture-induced hold relaxation without changing the
firmware model family or hiding the raw hold-level evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class HoldRelaxationMetrics:
    """Compact per-hold dynamics summary for diagnostics and audit logs."""

    start_median: float
    end_median: float
    delta_end_minus_start: float
    slope_per_s: float
    lin_r2: float
    monotonic_fraction: float
    exp_tau_s: float
    exp_r2: float

    def to_dict(self, prefix: str) -> dict[str, float]:
        return {f"{prefix}_{key}": value for key, value in asdict(self).items()}


def finite_median(values: Any) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.median(arr))


def tail_frame(df: pd.DataFrame, *, time_col: str, t_end: float, tail_s: float) -> pd.DataFrame:
    """Return the last ``tail_s`` seconds ending at ``t_end``.

    If ``tail_s <= 0`` the input frame is returned unchanged.
    """

    if tail_s <= 0 or df.empty:
        return df
    t0 = max(float(df[time_col].min()), float(t_end) - float(tail_s))
    return df[(df[time_col] >= t0) & (df[time_col] <= t_end)]


def _window_edge_medians(y: np.ndarray, edge_fraction: float = 0.2) -> tuple[float, float]:
    y = y[np.isfinite(y)]
    if len(y) == 0:
        return float("nan"), float("nan")
    n_edge = max(1, int(round(len(y) * edge_fraction)))
    return float(np.median(y[:n_edge])), float(np.median(y[-n_edge:]))


def _linear_r2(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    if len(x) < 3 or np.nanstd(y) == 0:
        return float("nan"), float("nan")
    slope, intercept = np.polyfit(x, y, deg=1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return float(slope), r2


def _monotonic_fraction(y: np.ndarray) -> float:
    valid = np.isfinite(y)
    y = y[valid]
    if len(y) < 2:
        return float("nan")
    dy = np.diff(y)
    dy = dy[np.isfinite(dy)]
    if len(dy) == 0:
        return float("nan")
    # Direction-free monotonicity: fraction of first differences matching the
    # dominant sign.  Values near 1 indicate a clean one-direction relaxation.
    pos = float(np.mean(dy >= 0))
    neg = float(np.mean(dy <= 0))
    return max(pos, neg)


def _approx_exponential_fit(t: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Approximate a first-order relaxation fit without SciPy.

    This is diagnostic-only.  It estimates the asymptote from the final 20% of
    samples, then fits ``log(abs(y - C))`` versus time.  The estimate is useful
    for detecting exponential-like behavior, but it is deliberately not used as
    the production calibration correction.
    """

    valid = np.isfinite(t) & np.isfinite(y)
    t = t[valid]
    y = y[valid]
    if len(t) < 8 or np.nanstd(y) == 0:
        return float("nan"), float("nan")
    _, c = _window_edge_medians(y, edge_fraction=0.2)
    residual = np.abs(y - c)
    floor = max(float(np.nanmedian(residual)) * 1e-6, 1e-12)
    mask = residual > floor
    if int(np.sum(mask)) < 5:
        return float("nan"), float("nan")
    x = t[mask] - t[mask][0]
    log_r = np.log(residual[mask])
    slope, intercept = np.polyfit(x, log_r, deg=1)
    if slope >= 0:
        return float("nan"), float("nan")
    pred = slope * x + intercept
    ss_res = float(np.sum((log_r - pred) ** 2))
    ss_tot = float(np.sum((log_r - np.mean(log_r)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    tau = float(-1.0 / slope)
    return tau, r2


def compute_hold_relaxation_metrics(
    df: pd.DataFrame, *, time_col: str, value_col: str
) -> HoldRelaxationMetrics:
    """Compute start/end, slope, monotonicity, and exponential diagnostics."""

    if df.empty or time_col not in df.columns or value_col not in df.columns:
        return HoldRelaxationMetrics(
            start_median=float("nan"),
            end_median=float("nan"),
            delta_end_minus_start=float("nan"),
            slope_per_s=float("nan"),
            lin_r2=float("nan"),
            monotonic_fraction=float("nan"),
            exp_tau_s=float("nan"),
            exp_r2=float("nan"),
        )
    t = df[time_col].to_numpy(dtype=float)
    y = df[value_col].to_numpy(dtype=float)
    valid = np.isfinite(t) & np.isfinite(y)
    t = t[valid]
    y = y[valid]
    if len(t) == 0:
        return HoldRelaxationMetrics(
            start_median=float("nan"),
            end_median=float("nan"),
            delta_end_minus_start=float("nan"),
            slope_per_s=float("nan"),
            lin_r2=float("nan"),
            monotonic_fraction=float("nan"),
            exp_tau_s=float("nan"),
            exp_r2=float("nan"),
        )
    rel_t = t - t[0]
    start, end = _window_edge_medians(y)
    slope, lin_r2 = _linear_r2(rel_t, y)
    tau, exp_r2 = _approx_exponential_fit(rel_t, y)
    return HoldRelaxationMetrics(
        start_median=start,
        end_median=end,
        delta_end_minus_start=float(end - start),
        slope_per_s=slope,
        lin_r2=lin_r2,
        monotonic_fraction=_monotonic_fraction(y),
        exp_tau_s=tau,
        exp_r2=exp_r2,
    )


def shape_correlation(
    target_window: pd.DataFrame,
    reference_window: pd.DataFrame,
    *,
    time_col: str,
    target_col: str,
    reference_col: str,
    n_grid: int = 200,
) -> float:
    """Return normalized target/reference shape correlation for one hold."""

    if target_window.empty or reference_window.empty:
        return float("nan")
    t0 = max(float(target_window[time_col].min()), float(reference_window[time_col].min()))
    t1 = min(float(target_window[time_col].max()), float(reference_window[time_col].max()))
    if t1 <= t0:
        return float("nan")
    grid = np.linspace(t0, t1, n_grid)
    target_t = target_window[time_col].to_numpy(dtype=float)
    target_y = target_window[target_col].to_numpy(dtype=float)
    ref_t = reference_window[time_col].to_numpy(dtype=float)
    ref_y = reference_window[reference_col].to_numpy(dtype=float)
    valid_t = np.isfinite(target_t) & np.isfinite(target_y)
    valid_r = np.isfinite(ref_t) & np.isfinite(ref_y)
    if int(np.sum(valid_t)) < 3 or int(np.sum(valid_r)) < 3:
        return float("nan")
    ty = np.interp(grid, target_t[valid_t], target_y[valid_t])
    ry = np.interp(grid, ref_t[valid_r], ref_y[valid_r])
    ty = ty - np.mean(ty)
    ry = ry - np.mean(ry)
    tsy = float(np.std(ty))
    rsy = float(np.std(ry))
    if tsy == 0 or rsy == 0:
        return float("nan")
    return float(np.corrcoef(ty / tsy, ry / rsy)[0, 1])


def expected_relaxation_sign(direction: Any) -> int | None:
    """Expected sign of end-start delta from the observed fixture artifact."""

    text = str(direction or "").lower()
    if text == "ascending":
        return -1
    if text == "descending":
        return 1
    return None


def direction_sign_matches(direction: Any, delta: float) -> bool | None:
    expected = expected_relaxation_sign(direction)
    if expected is None or not np.isfinite(delta):
        return None
    if delta == 0:
        return True
    return bool(np.sign(delta) == expected)


def _robust_keep_mask(values: np.ndarray, *, max_mad_z: float) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    keep = np.isfinite(values)
    finite = values[keep]
    if len(finite) < 3:
        # With two repeats there is no defensible MAD outlier decision.  Keep
        # both and surface the count in the summary instead of pretending a
        # single point can be robustly rejected.
        return keep
    med = float(np.median(finite))
    mad = float(np.median(np.abs(finite - med)))
    if mad <= 0:
        return keep
    robust_z = np.abs(0.6745 * (values - med) / mad)
    return keep & (robust_z <= max_mad_z)


def _direction_stats(
    rows: pd.DataFrame,
    *,
    target_col: str,
    reference_col: str,
    max_mad_z: float,
) -> dict[str, Any]:
    if rows.empty:
        return {
            "n": 0,
            "n_kept": 0,
            "n_outliers": 0,
            "target_median": float("nan"),
            "reference_median_N": float("nan"),
            "source_trial_ids": "",
        }
    target = rows[target_col].to_numpy(dtype=float)
    reference = rows[reference_col].to_numpy(dtype=float)
    keep = _robust_keep_mask(target, max_mad_z=max_mad_z) & _robust_keep_mask(
        reference, max_mad_z=max_mad_z
    )
    kept = rows.loc[keep]
    return {
        "n": int(len(rows)),
        "n_kept": int(len(kept)),
        "n_outliers": int(len(rows) - len(kept)),
        "target_median": finite_median(kept[target_col]) if not kept.empty else float("nan"),
        "reference_median_N": finite_median(kept[reference_col]) if not kept.empty else float("nan"),
        "source_trial_ids": ",".join(str(x) for x in kept.get("trial_id", pd.Series(dtype=str))),
    }


def direction_balanced_tail_median_dataset(
    hold_dataset: pd.DataFrame,
    *,
    target_col: str = "target_raw_tail_median",
    reference_col: str = "reference_force_tail_median_N",
    require_both_directions: bool = True,
    max_mad_z: float = 3.5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse directional static holds into artifact-aware fit points.

    For each nonzero nominal force level, ascending and descending tail medians
    are calculated separately, then averaged.  The averaging cancels the observed
    symmetric relaxation/rebound bias while preserving a simple static mapping
    for firmware deployment.  Zero/flat levels are aggregated with a simple
    median because they do not have a meaningful up/down pair.
    """

    if hold_dataset.empty:
        return hold_dataset.copy(), pd.DataFrame()
    required = {"target_force_nominal_N", "direction", target_col, reference_col}
    missing = sorted(required - set(hold_dataset.columns))
    if missing:
        raise ValueError(f"Cannot apply direction-balanced artifact correction; missing: {missing}")

    corrected_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    finite_nominals = pd.to_numeric(hold_dataset["target_force_nominal_N"], errors="coerce")
    endpoint_levels = {float(finite_nominals.min()), float(finite_nominals.max())}
    grouped = hold_dataset.groupby("target_force_nominal_N", dropna=False, sort=True)
    for nominal, group in grouped:
        try:
            is_endpoint_level = float(nominal) in endpoint_levels
        except Exception:
            is_endpoint_level = False
        group = group.copy()
        directions = group["direction"].astype(str).str.lower()
        flat_group = group[directions == "flat"]
        asc_group = group[directions == "ascending"]
        desc_group = group[directions == "descending"]

        asc = _direction_stats(
            asc_group, target_col=target_col, reference_col=reference_col, max_mad_z=max_mad_z
        )
        desc = _direction_stats(
            desc_group, target_col=target_col, reference_col=reference_col, max_mad_z=max_mad_z
        )
        have_pair = asc["n_kept"] > 0 and desc["n_kept"] > 0
        endpoint_fallback = bool(is_endpoint_level)
        include = have_pair or endpoint_fallback or not require_both_directions
        if have_pair:
            target_balanced = float(np.mean([asc["target_median"], desc["target_median"]]))
            ref_balanced = float(np.mean([asc["reference_median_N"], desc["reference_median_N"]]))
            status = "included_direction_balanced"
            source_ids = ",".join(x for x in [asc["source_trial_ids"], desc["source_trial_ids"]] if x)
        elif include:
            pooled = _direction_stats(
                group, target_col=target_col, reference_col=reference_col, max_mad_z=max_mad_z
            )
            target_balanced = pooled["target_median"]
            ref_balanced = pooled["reference_median_N"]
            status = "included_endpoint_pooled" if endpoint_fallback else "included_unpaired_pooled"
            source_ids = pooled["source_trial_ids"]
        else:
            target_balanced = float("nan")
            ref_balanced = float("nan")
            status = "excluded_missing_direction_pair"
            source_ids = ""

        summary_rows.append(
            {
                "target_force_nominal_N": nominal,
                "artifact_status": status,
                "n_source_holds": int(len(group)),
                "n_ascending": int(len(asc_group)),
                "n_descending": int(len(desc_group)),
                "n_flat": int(len(flat_group)),
                "n_outliers": int(asc["n_outliers"] + desc["n_outliers"]),
                "target_ascending_median": asc["target_median"],
                "target_descending_median": desc["target_median"],
                "target_balanced_median": target_balanced,
                "reference_ascending_median_N": asc["reference_median_N"],
                "reference_descending_median_N": desc["reference_median_N"],
                "reference_balanced_median_N": ref_balanced,
                "source_trial_ids": source_ids,
            }
        )
        if include and np.isfinite(target_balanced) and np.isfinite(ref_balanced):
            first = group.iloc[0].to_dict()
            first.update(
                {
                    "trial_id": f"artifact_balanced_{nominal:g}N",
                    "direction": "direction_balanced",
                    "repeat_index": np.nan,
                    "level_index": np.nan,
                    "target_raw_median": target_balanced,
                    "reference_force_median_N": ref_balanced,
                    "target_raw_mean": target_balanced,
                    "reference_force_mean_N": ref_balanced,
                    "accepted_by_quality": True,
                    "quality_rejection_reason": "",
                    "calibration_artifact_applied": True,
                    "calibration_artifact_method": "direction_balanced_tail_median",
                    "calibration_artifact_source_holds": int(asc["n_kept"] + desc["n_kept"]),
                    "calibration_artifact_outliers": int(asc["n_outliers"] + desc["n_outliers"]),
                    "calibration_artifact_source_trial_ids": source_ids,
                    "calibration_artifact_target_ascending_median": asc["target_median"],
                    "calibration_artifact_target_descending_median": desc["target_median"],
                    "calibration_artifact_reference_ascending_median_N": asc["reference_median_N"],
                    "calibration_artifact_reference_descending_median_N": desc["reference_median_N"],
                }
            )
            corrected_rows.append(first)

    corrected = pd.DataFrame(corrected_rows)
    summary = pd.DataFrame(summary_rows)
    return corrected, summary
