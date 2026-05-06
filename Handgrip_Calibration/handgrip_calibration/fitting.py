"""Calibration model fitting and model selection.

This module implements the upgraded fitting strategy for Handgrip_Calibration:
fit a small, auditable candidate set on operator/quality accepted static holds,
rank candidates by physical force error, and select the simplest model that is
statistically defensible. Dynamic trials remain validation material and are not
used for primary calibration fitting.

Implemented candidate models
----------------------------
- affine_ols: baseline ordinary least-squares affine fit.
- affine_wls: affine fit weighted by per-hold reference noise.
- affine_huber: robust affine fit using an iterative Huber loss.
- quadratic_wls: degree-2 polynomial, gated by monotonicity and CV metrics.
- piecewise_linear_monotone: firmware-friendly multipoint lookup table.
- odr_affine: diagnostic errors-in-variables affine fit using scipy.odr.
- hysteresis_affine_diagnostic: separate direction fits for up/down analysis.
- drift_affine_diagnostic: affine model with a centered elapsed-time term.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .config_schema import AppConfig, FitConfig
from .export import append_ndjson, write_json
from .segmentation import segment_accepted_holds


@dataclass(frozen=True)
class FitMetrics:
    """Standard fit-quality metrics in physical force units."""

    n_points: int
    rmse_N: float
    mae_N: float
    max_abs_error_N: float
    max_abs_error_percent_range: float
    r2: float
    adjusted_r2: float
    residual_bias_N: float
    residual_std_N: float
    aicc: float
    bic: float


@dataclass(frozen=True)
class CandidateResult:
    """Complete result for one fit candidate."""

    model_id: str
    model_family: str
    parameters: dict[str, Any]
    n_parameters: int
    deployable_to_firmware: bool
    diagnostic_only: bool
    metrics: FitMetrics
    cv_metrics: dict[str, float | int | None]
    selection_score: float
    selection_likelihood: float
    accepted_for_deployment: bool
    rejection_reasons: list[str]
    firmware_export: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationFitResult:
    """Selected calibration model plus candidate-model audit trail.

    ``force_N_a`` and ``force_N_b`` are intentionally kept for compatibility with
    the original affine-only API and tests. They are populated when the selected
    model exposes an affine component; nonlinear models also include their full
    parameters in ``model_parameters`` and ``recommended_firmware_constants``.
    """

    schema: str
    model: str
    selected_model_id: str
    selected_model_family: str
    force_N_a: float | None
    force_N_b: float | None
    model_parameters: dict[str, Any]
    metrics: FitMetrics
    cv_metrics: dict[str, float | int | None]
    residual_threshold_percent_range: float
    passes_residual_threshold: bool
    selection_likelihood: float
    model_ranking: list[dict[str, Any]]
    recommended_firmware_constants: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["force_N"] = {"a": data.pop("force_N_a"), "b": data.pop("force_N_b")}
        return data


# Backward-compatible alias for external imports from the original release.
AffineFitResult = CalibrationFitResult


@dataclass(frozen=True)
class _FitData:
    frame: pd.DataFrame
    x: np.ndarray
    y: np.ndarray
    sample_weight_sigma: np.ndarray
    target_sigma: np.ndarray


@dataclass(frozen=True)
class _ModelSpec:
    model_id: str
    family: str
    n_parameters: int
    diagnostic_only: bool
    deployable_to_firmware: bool
    predict: Callable[[pd.DataFrame, np.ndarray], np.ndarray]
    parameters: dict[str, Any]
    firmware_export: dict[str, Any] | None
    notes: list[str] = field(default_factory=list)


def _finite_or_none(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    value = float(value)
    return value if math.isfinite(value) else None


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    if np.count_nonzero(valid) < 2:
        return float("nan")
    yt = y_true[valid]
    yp = y_pred[valid]
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def _fit_metrics(y_true: np.ndarray, y_pred: np.ndarray, *, n_parameters: int, operating_range_N: float) -> FitMetrics:
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    n = int(np.count_nonzero(valid))
    if n == 0:
        return FitMetrics(0, *(float("nan") for _ in range(9)))
    residuals = y_true[valid] - y_pred[valid]
    rss = float(np.sum(residuals**2))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    mae = float(np.mean(np.abs(residuals)))
    max_abs = float(np.max(np.abs(residuals)))
    max_pct = float(100.0 * max_abs / operating_range_N)
    r2 = _r2(y_true, y_pred)
    if n > n_parameters + 1 and math.isfinite(r2):
        adj_r2 = float(1.0 - (1.0 - r2) * (n - 1) / (n - n_parameters - 1))
    else:
        adj_r2 = float("nan")
    sigma2 = max(rss / max(n, 1), np.finfo(float).tiny)
    aic = float(n * math.log(sigma2) + 2 * n_parameters)
    if n > n_parameters + 1:
        aicc = float(aic + (2 * n_parameters * (n_parameters + 1)) / (n - n_parameters - 1))
    else:
        aicc = float("nan")
    bic = float(n * math.log(sigma2) + n_parameters * math.log(max(n, 2)))
    return FitMetrics(
        n_points=n,
        rmse_N=rmse,
        mae_N=mae,
        max_abs_error_N=max_abs,
        max_abs_error_percent_range=max_pct,
        r2=float(r2),
        adjusted_r2=adj_r2,
        residual_bias_N=float(np.mean(residuals)),
        residual_std_N=float(np.std(residuals, ddof=1)) if n > 1 else 0.0,
        aicc=aicc,
        bic=bic,
    )


def _prepare_fit_data(dataset: pd.DataFrame, config: AppConfig) -> tuple[_FitData, list[str]]:
    """Filter finite accepted static holds and compute uncertainty vectors."""

    notes: list[str] = []
    if "accepted_by_quality" in dataset.columns:
        fit_points = dataset[dataset["accepted_by_quality"].fillna(False)].copy()
    else:
        fit_points = pd.DataFrame()
    if fit_points.empty:
        fit_points = dataset.copy()
        notes.append("No quality-accepted points found; fitted all operator-accepted segmented holds.")

    if "target_raw_median" not in fit_points.columns or "reference_force_median_N" not in fit_points.columns:
        raise ValueError("calibration_dataset.csv must contain target_raw_median and reference_force_median_N")

    x_all = fit_points["target_raw_median"].to_numpy(dtype=float)
    y_all = fit_points["reference_force_median_N"].to_numpy(dtype=float)
    valid = np.isfinite(x_all) & np.isfinite(y_all)
    fit_points = fit_points.loc[valid].copy().reset_index(drop=True)
    if len(fit_points) < 2:
        raise ValueError("At least two valid calibration points are required for model fitting")

    if "t_mid_lsl" not in fit_points.columns and {"t_start_lsl", "t_end_lsl"}.issubset(fit_points.columns):
        fit_points["t_mid_lsl"] = 0.5 * (fit_points["t_start_lsl"].astype(float) + fit_points["t_end_lsl"].astype(float))

    x = fit_points["target_raw_median"].to_numpy(dtype=float)
    y = fit_points["reference_force_median_N"].to_numpy(dtype=float)

    if "reference_force_std_N" in fit_points.columns:
        ref_std = fit_points["reference_force_std_N"].to_numpy(dtype=float)
    else:
        ref_std = np.full_like(y, config.fit.reference_noise_floor_N)
    ref_std = np.where(np.isfinite(ref_std), np.abs(ref_std), config.fit.reference_noise_floor_N)
    sample_weight_sigma = np.maximum(ref_std, config.fit.reference_noise_floor_N)

    if "target_raw_std" in fit_points.columns:
        target_std = fit_points["target_raw_std"].to_numpy(dtype=float)
    else:
        target_std = np.full_like(x, config.fit.target_raw_noise_floor)
    target_std = np.where(np.isfinite(target_std), np.abs(target_std), config.fit.target_raw_noise_floor)
    target_sigma = np.maximum(target_std, config.fit.target_raw_noise_floor)
    return _FitData(fit_points, x, y, sample_weight_sigma, target_sigma), notes


def _sigma_to_polyfit_weights(sigma: np.ndarray) -> np.ndarray:
    """Convert standard deviations to numpy.polyfit weights.

    ``polyfit`` weights multiply the unsquared residual, so inverse sigma is the
    correct representation for inverse-variance weighted least squares.
    """

    return 1.0 / np.maximum(sigma, np.finfo(float).eps)


def _linear_solve(X: np.ndarray, y: np.ndarray, *, sigma: np.ndarray | None = None) -> np.ndarray:
    if sigma is not None:
        w = 1.0 / np.maximum(sigma, np.finfo(float).eps)
        Xw = X * w[:, None]
        yw = y * w
    else:
        Xw = X
        yw = y
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    return beta


def _affine_spec(a: float, b: float, *, model_id: str, family: str, notes: list[str] | None = None) -> _ModelSpec:
    def predict(_frame: pd.DataFrame, x: np.ndarray) -> np.ndarray:
        return a * x + b

    firmware = {
        "type": "affine_force_N_equals_a_raw_plus_b",
        "force_N_equals_a_raw_plus_b": {"a": float(a), "b": float(b)},
        "hx711_get_units_style_approximation": {
            "scale": (1.0 / float(a)) if a != 0 else None,
            "offset": (-float(b) / float(a)) if a != 0 else None,
            "warning": "Verify against the exact HX711 library semantics before flashing firmware constants.",
        },
    }
    return _ModelSpec(
        model_id=model_id,
        family=family,
        n_parameters=2,
        diagnostic_only=False,
        deployable_to_firmware=True,
        predict=predict,
        parameters={"a": float(a), "b": float(b)},
        firmware_export=firmware,
        notes=notes or [],
    )


def _fit_affine_ols(data: _FitData, _cfg: FitConfig) -> _ModelSpec:
    coeff = np.polyfit(data.x, data.y, deg=1)
    return _affine_spec(float(coeff[0]), float(coeff[1]), model_id="affine_ols", family="affine")


def _fit_affine_wls(data: _FitData, cfg: FitConfig) -> _ModelSpec:
    if not cfg.weighted_by_reference_noise:
        return _fit_affine_ols(data, cfg)
    coeff = np.polyfit(data.x, data.y, deg=1, w=_sigma_to_polyfit_weights(data.sample_weight_sigma))
    return _affine_spec(float(coeff[0]), float(coeff[1]), model_id="affine_wls", family="affine_weighted")


def _mad_scale(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return 0.0
    med = float(np.median(values))
    mad = float(np.median(np.abs(values - med)))
    return 1.4826 * mad


def _fit_affine_huber(data: _FitData, cfg: FitConfig) -> _ModelSpec:
    X = np.column_stack([data.x, np.ones_like(data.x)])
    beta = _linear_solve(X, data.y, sigma=data.sample_weight_sigma if cfg.weighted_by_reference_noise else None)
    residuals = data.y - X @ beta
    scale = _mad_scale(residuals)
    if not math.isfinite(scale) or scale <= 0:
        scale = float(np.std(residuals)) if len(residuals) > 1 else cfg.reference_noise_floor_N
    delta = cfg.robust.huber_delta_N if cfg.robust.huber_delta_N is not None else cfg.robust.huber_epsilon * max(scale, cfg.reference_noise_floor_N)
    delta = max(float(delta), cfg.reference_noise_floor_N)
    robust_weights = np.ones_like(data.y, dtype=float)
    sigma_base = data.sample_weight_sigma if cfg.weighted_by_reference_noise else np.ones_like(data.y)
    for _ in range(cfg.robust.max_iter):
        residuals = data.y - X @ beta
        abs_r = np.abs(residuals)
        robust_weights = np.where(abs_r <= delta, 1.0, delta / np.maximum(abs_r, np.finfo(float).eps))
        robust_weights = np.clip(robust_weights, cfg.robust.min_weight, 1.0)
        combined_sigma = sigma_base / np.sqrt(robust_weights)
        new_beta = _linear_solve(X, data.y, sigma=combined_sigma)
        if float(np.linalg.norm(new_beta - beta)) <= cfg.robust.convergence_tol:
            beta = new_beta
            break
        beta = new_beta

    spec = _affine_spec(float(beta[0]), float(beta[1]), model_id="affine_huber", family="affine_robust")
    return _ModelSpec(
        model_id=spec.model_id,
        family=spec.family,
        n_parameters=spec.n_parameters,
        diagnostic_only=spec.diagnostic_only,
        deployable_to_firmware=spec.deployable_to_firmware,
        predict=spec.predict,
        parameters={**spec.parameters, "huber_delta_N": float(delta), "robust_weights": robust_weights.tolist()},
        firmware_export={**(spec.firmware_export or {}), "robust_training_only": True},
        notes=["Robust weights are used only during fitting; exported firmware equation remains affine."],
    )


def _fit_quadratic_wls(data: _FitData, cfg: FitConfig) -> _ModelSpec:
    if len(data.x) < 3:
        raise ValueError("quadratic_wls requires at least three calibration points")
    weights = _sigma_to_polyfit_weights(data.sample_weight_sigma) if cfg.weighted_by_reference_noise else None
    coeff = np.polyfit(data.x, data.y, deg=2, w=weights)
    a2, a1, a0 = [float(c) for c in coeff]

    def predict(_frame: pd.DataFrame, x: np.ndarray) -> np.ndarray:
        return a2 * x**2 + a1 * x + a0

    return _ModelSpec(
        model_id="quadratic_wls",
        family="polynomial_degree_2",
        n_parameters=3,
        diagnostic_only=False,
        deployable_to_firmware=True,
        predict=predict,
        parameters={"a2": a2, "a1": a1, "a0": a0},
        firmware_export={
            "type": "quadratic_force_N_equals_a2_raw2_plus_a1_raw_plus_a0",
            "force_N_equals_a2_raw2_plus_a1_raw_plus_a0": {"a2": a2, "a1": a1, "a0": a0},
        },
    )


def _aggregate_multipoint_knots(frame: pd.DataFrame, cfg: FitConfig) -> tuple[np.ndarray, np.ndarray]:
    aggregate_by = cfg.multipoint.aggregate_by
    if aggregate_by in frame.columns and frame[aggregate_by].dropna().nunique() >= cfg.multipoint.min_points:
        grouped = frame.groupby(aggregate_by, dropna=True).agg(
            target_raw_median=("target_raw_median", "median"),
            reference_force_median_N=("reference_force_median_N", "median"),
        )
        knots = grouped.sort_values("target_raw_median")
        xk = knots["target_raw_median"].to_numpy(dtype=float)
        yk = knots["reference_force_median_N"].to_numpy(dtype=float)
    else:
        order = np.argsort(frame["target_raw_median"].to_numpy(dtype=float))
        xk = frame["target_raw_median"].to_numpy(dtype=float)[order]
        yk = frame["reference_force_median_N"].to_numpy(dtype=float)[order]
    valid = np.isfinite(xk) & np.isfinite(yk)
    xk = xk[valid]
    yk = yk[valid]
    # Collapse repeated raw medians after rounding to keep numpy.interp stable.
    if len(xk):
        tmp = pd.DataFrame({"x": xk, "y": yk})
        tmp["x_round"] = tmp["x"].round(9)
        collapsed = tmp.groupby("x_round", sort=True).agg(x=("x", "median"), y=("y", "median"))
        xk = collapsed["x"].to_numpy(dtype=float)
        yk = collapsed["y"].to_numpy(dtype=float)
    if len(xk) > cfg.multipoint.max_knots:
        # Keep evenly spaced knots over the observed range so firmware exports
        # remain compact and auditable.
        idx = np.linspace(0, len(xk) - 1, cfg.multipoint.max_knots).round().astype(int)
        xk = xk[idx]
        yk = yk[idx]
    return xk, yk


def _is_monotone(values: np.ndarray, *, tol: float = 1e-9) -> bool:
    if len(values) < 2:
        return True
    d = np.diff(values)
    return bool(np.all(d >= -tol) or np.all(d <= tol))


def _fit_piecewise_linear_monotone(data: _FitData, cfg: FitConfig) -> _ModelSpec:
    xk, yk = _aggregate_multipoint_knots(data.frame, cfg)
    if len(xk) < cfg.multipoint.min_points:
        raise ValueError(f"piecewise_linear_monotone requires at least {cfg.multipoint.min_points} knots")
    if not _is_monotone(yk):
        raise ValueError("piecewise_linear_monotone rejected: knot forces are not monotone")

    def predict(_frame: pd.DataFrame, x: np.ndarray) -> np.ndarray:
        pred = np.interp(x, xk, yk)
        if cfg.multipoint.extrapolation == "reject":
            # Knots are aggregated by nominal force, so repeated holds at the same
            # endpoint can land a few raw counts outside the median endpoint knot.
            # Treat that as endpoint noise, not true extrapolation.
            edge_margin = max(1.0, 0.005 * float(xk[-1] - xk[0]))
            pred = pred.astype(float)
            pred[(x < xk[0] - edge_margin) | (x > xk[-1] + edge_margin)] = np.nan
        return pred

    return _ModelSpec(
        model_id="piecewise_linear_monotone",
        family="monotone_multipoint",
        n_parameters=int(2 * len(xk)),
        diagnostic_only=False,
        deployable_to_firmware=True,
        predict=predict,
        parameters={"x_raw_knots": xk.tolist(), "force_N_knots": yk.tolist(), "extrapolation": cfg.multipoint.extrapolation},
        firmware_export={
            "type": "monotone_piecewise_linear_lookup_table",
            "x_raw_knots": xk.tolist(),
            "force_N_knots": yk.tolist(),
            "extrapolation": cfg.multipoint.extrapolation,
        },
        notes=["Use only inside the calibrated raw-count range unless extrapolation is explicitly changed."],
    )


def _fit_odr_affine(data: _FitData, cfg: FitConfig) -> _ModelSpec:
    """Fit a diagnostic errors-in-variables affine model via Deming regression.

    This pure-NumPy implementation approximates affine ODR for the calibration
    case without adding SciPy as a hard runtime dependency. The variance ratio is
    estimated from the per-hold y uncertainty in Newtons and x uncertainty in raw
    counts, so the result should be interpreted as a diagnostic sensitivity check
    rather than a traceable uncertainty analysis.
    """

    x = data.x.astype(float)
    y = data.y.astype(float)
    if len(x) < 3:
        raise ValueError("odr_affine requires at least three calibration points")
    sx2 = float(np.nanmedian(np.maximum(data.target_sigma, cfg.target_raw_noise_floor) ** 2))
    sy2 = float(np.nanmedian(np.maximum(data.sample_weight_sigma, cfg.reference_noise_floor_N) ** 2))
    if sx2 <= 0 or sy2 <= 0:
        raise ValueError("odr_affine requires positive x/y uncertainty estimates")
    lam = sy2 / sx2
    x_bar = float(np.mean(x))
    y_bar = float(np.mean(y))
    xc = x - x_bar
    yc = y - y_bar
    sxx = float(np.mean(xc**2))
    syy = float(np.mean(yc**2))
    sxy = float(np.mean(xc * yc))
    if abs(sxy) <= np.finfo(float).eps:
        raise ValueError("odr_affine cannot fit when covariance is approximately zero")
    disc = (syy - lam * sxx) ** 2 + 4.0 * lam * sxy**2
    a = (syy - lam * sxx + math.sqrt(max(disc, 0.0))) / (2.0 * sxy)
    b = y_bar - a * x_bar
    spec = _affine_spec(float(a), float(b), model_id="odr_affine", family="affine_odr", notes=["Diagnostic errors-in-variables affine fit using Deming regression."])
    return _ModelSpec(
        model_id=spec.model_id,
        family=spec.family,
        n_parameters=spec.n_parameters,
        diagnostic_only=True,
        deployable_to_firmware=True,
        predict=spec.predict,
        parameters={**spec.parameters, "variance_ratio_y_over_x": float(lam), "method": "deming_regression"},
        firmware_export=spec.firmware_export,
        notes=spec.notes,
    )


def _fit_hysteresis_affine(data: _FitData, cfg: FitConfig) -> _ModelSpec:
    col = cfg.diagnostics.hysteresis_direction_column
    if col not in data.frame.columns:
        raise ValueError(f"hysteresis diagnostic requires column {col!r}")
    directions = [d for d in sorted(data.frame[col].dropna().astype(str).unique()) if d.lower() not in {"flat", "none", "nan"}]
    if len(directions) < 2:
        raise ValueError("hysteresis diagnostic requires at least two non-flat directions")
    params: dict[str, dict[str, float]] = {}
    for direction in directions:
        mask = data.frame[col].astype(str).to_numpy() == direction
        if np.count_nonzero(mask) < 2:
            continue
        coeff = np.polyfit(data.x[mask], data.y[mask], deg=1)
        params[direction] = {"a": float(coeff[0]), "b": float(coeff[1]), "n": int(np.count_nonzero(mask))}
    if len(params) < 2:
        raise ValueError("hysteresis diagnostic had fewer than two fit-capable directions")
    fallback = np.polyfit(data.x, data.y, deg=1)

    def predict(frame: pd.DataFrame, x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x, dtype=float)
        dirs = frame[col].astype(str).to_numpy() if col in frame.columns else np.array([""] * len(x))
        for i, (xx, direction) in enumerate(zip(x, dirs)):
            p = params.get(str(direction))
            if p is None:
                out[i] = float(fallback[0]) * xx + float(fallback[1])
            else:
                out[i] = p["a"] * xx + p["b"]
        return out

    return _ModelSpec(
        model_id="hysteresis_affine_diagnostic",
        family="direction_dependent_affine",
        n_parameters=2 * len(params),
        diagnostic_only=True,
        deployable_to_firmware=False,
        predict=predict,
        parameters={"directions": params, "fallback_affine": {"a": float(fallback[0]), "b": float(fallback[1])}},
        firmware_export=None,
        notes=["Diagnostic only: if this wins materially, inspect fixture hysteresis before encoding direction-dependent firmware behavior."],
    )


def _fit_drift_affine(data: _FitData, cfg: FitConfig) -> _ModelSpec:
    col = cfg.diagnostics.drift_time_column
    if col not in data.frame.columns:
        raise ValueError(f"drift diagnostic requires column {col!r}")
    t = data.frame[col].to_numpy(dtype=float)
    if np.count_nonzero(np.isfinite(t)) < 3:
        raise ValueError("drift diagnostic requires at least three finite time points")
    t0 = float(np.nanmedian(t))
    tc = t - t0
    X = np.column_stack([data.x, np.ones_like(data.x), tc])
    beta = _linear_solve(X, data.y, sigma=data.sample_weight_sigma if cfg.weighted_by_reference_noise else None)
    a, b, c = [float(v) for v in beta]

    def predict(frame: pd.DataFrame, x: np.ndarray) -> np.ndarray:
        if col in frame.columns:
            tt = frame[col].to_numpy(dtype=float) - t0
        elif {"t_start_lsl", "t_end_lsl"}.issubset(frame.columns):
            tt = 0.5 * (frame["t_start_lsl"].to_numpy(dtype=float) + frame["t_end_lsl"].to_numpy(dtype=float)) - t0
        else:
            tt = np.zeros_like(x)
        return a * x + b + c * tt

    return _ModelSpec(
        model_id="drift_affine_diagnostic",
        family="affine_plus_time_drift",
        n_parameters=3,
        diagnostic_only=True,
        deployable_to_firmware=False,
        predict=predict,
        parameters={"a": a, "b": b, "drift_N_per_s": c, "time_center_lsl": t0},
        firmware_export=None,
        notes=["Diagnostic only: prefer fixing/measuring drift before baking time into the calibration model."],
    )


_FITTERS: dict[str, Callable[[_FitData, FitConfig], _ModelSpec]] = {
    "affine_ols": _fit_affine_ols,
    "affine_wls": _fit_affine_wls,
    "affine_huber": _fit_affine_huber,
    "quadratic_wls": _fit_quadratic_wls,
    "piecewise_linear_monotone": _fit_piecewise_linear_monotone,
    "odr_affine": _fit_odr_affine,
    "hysteresis_affine_diagnostic": _fit_hysteresis_affine,
    "drift_affine_diagnostic": _fit_drift_affine,
}


def _build_cv_folds(frame: pd.DataFrame, cfg: FitConfig) -> list[tuple[np.ndarray, np.ndarray]]:
    n = len(frame)
    if n < 4:
        return []
    group_col = cfg.selection.cv_group_by
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    if group_col in frame.columns and frame[group_col].notna().nunique() >= 3:
        groups = frame[group_col].astype(str).to_numpy()
        unique = list(dict.fromkeys(groups.tolist()))
        # Keep a bounded number of folds for operator-heavy protocols.
        if len(unique) > cfg.selection.max_cv_folds:
            idx = np.linspace(0, len(unique) - 1, cfg.selection.max_cv_folds).round().astype(int)
            unique = [unique[i] for i in idx]
        for group in unique:
            test = groups == group
            train = ~test
            if np.count_nonzero(train) >= 3 and np.count_nonzero(test) >= 1:
                folds.append((train, test))
    if len(folds) >= 2:
        return folds
    # Fallback: deterministic leave-one-out with bounded folds.
    indices = np.arange(n)
    if n > cfg.selection.max_cv_folds:
        indices = np.linspace(0, n - 1, cfg.selection.max_cv_folds).round().astype(int)
    for i in indices:
        test = np.zeros(n, dtype=bool)
        test[int(i)] = True
        train = ~test
        if np.count_nonzero(train) >= 3:
            folds.append((train, test))
    return folds


def _subset_data(data: _FitData, mask: np.ndarray) -> _FitData:
    return _FitData(
        frame=data.frame.loc[mask].copy().reset_index(drop=True),
        x=data.x[mask],
        y=data.y[mask],
        sample_weight_sigma=data.sample_weight_sigma[mask],
        target_sigma=data.target_sigma[mask],
    )


def _cross_validate(model_id: str, data: _FitData, cfg: FitConfig) -> dict[str, float | int | None]:
    folds = _build_cv_folds(data.frame, cfg)
    if not folds:
        return {
            "cv_rmse_N": None,
            "cv_mae_N": None,
            "cv_max_abs_error_N": None,
            "cv_max_abs_error_percent_range": None,
            "cv_rmse_se_N": None,
            "cv_fold_count": 0,
            "cv_point_count": 0,
            "cv_coverage_fraction": 0.0,
        }
    pred_all = np.full_like(data.y, np.nan, dtype=float)
    fold_rmses: list[float] = []
    successful_folds = 0
    for train_mask, test_mask in folds:
        try:
            spec = _FITTERS[model_id](_subset_data(data, train_mask), cfg)
            pred = spec.predict(data.frame.loc[test_mask].copy().reset_index(drop=True), data.x[test_mask])
            finite = np.isfinite(pred)
            if not np.any(finite):
                continue
            pred_all[np.where(test_mask)[0][finite]] = pred[finite]
            residuals = data.y[test_mask][finite] - pred[finite]
            fold_rmses.append(float(np.sqrt(np.mean(residuals**2))))
            successful_folds += 1
        except Exception:
            continue
    valid = np.isfinite(pred_all)
    point_count = int(np.count_nonzero(valid))
    if point_count == 0:
        return {
            "cv_rmse_N": None,
            "cv_mae_N": None,
            "cv_max_abs_error_N": None,
            "cv_max_abs_error_percent_range": None,
            "cv_rmse_se_N": None,
            "cv_fold_count": successful_folds,
            "cv_point_count": 0,
            "cv_coverage_fraction": 0.0,
        }
    residuals = data.y[valid] - pred_all[valid]
    cv_rmse = float(np.sqrt(np.mean(residuals**2)))
    return {
        "cv_rmse_N": cv_rmse,
        "cv_mae_N": float(np.mean(np.abs(residuals))),
        "cv_max_abs_error_N": float(np.max(np.abs(residuals))),
        "cv_max_abs_error_percent_range": float(100.0 * np.max(np.abs(residuals)) / cfg.operating_range_N),
        "cv_rmse_se_N": float(np.std(fold_rmses, ddof=1) / math.sqrt(len(fold_rmses))) if len(fold_rmses) > 1 else None,
        "cv_fold_count": int(successful_folds),
        "cv_point_count": point_count,
        "cv_coverage_fraction": float(point_count / len(data.y)),
    }


def _monotonicity_rejection(spec: _ModelSpec, data: _FitData, cfg: FitConfig) -> str | None:
    if not cfg.selection.require_monotonic or len(data.x) < 2:
        return None
    x_min = float(np.nanmin(data.x))
    x_max = float(np.nanmax(data.x))
    if not math.isfinite(x_min) or not math.isfinite(x_max) or x_min == x_max:
        return None
    x_grid = np.linspace(x_min, x_max, 200)
    dummy = pd.DataFrame({"target_raw_median": x_grid})
    try:
        y_grid = spec.predict(dummy, x_grid)
    except Exception:
        return "monotonicity_check_failed"
    finite = y_grid[np.isfinite(y_grid)]
    if len(finite) < 2:
        return "monotonicity_check_no_finite_predictions"
    if not _is_monotone(finite, tol=max(1e-9, cfg.operating_range_N * 1e-8)):
        return "non_monotonic_prediction_over_calibrated_range"
    return None


def _score_candidate(metrics: FitMetrics, cv: dict[str, float | int | None], spec: _ModelSpec, rejection_reasons: list[str], cfg: FitConfig) -> float:
    cv_rmse = cv.get("cv_rmse_N")
    cv_rmse_value = float(cv_rmse) if cv_rmse is not None and math.isfinite(float(cv_rmse)) else metrics.rmse_N
    error_score = cv_rmse_value / cfg.operating_range_N
    max_error_score = metrics.max_abs_error_N / cfg.operating_range_N
    score = (
        cfg.selection.alpha_cv_rmse * error_score
        + cfg.selection.beta_max_error * max_error_score
        + cfg.selection.lambda_complexity * spec.n_parameters
    )
    if any("monotonic" in reason for reason in rejection_reasons):
        score += cfg.selection.monotonicity_violation_penalty
    if spec.diagnostic_only:
        score += cfg.selection.diagnostic_model_penalty
    return float(score)


def _candidate_from_spec(spec: _ModelSpec, data: _FitData, cfg: FitConfig) -> CandidateResult:
    y_pred = spec.predict(data.frame, data.x)
    metrics = _fit_metrics(data.y, y_pred, n_parameters=spec.n_parameters, operating_range_N=cfg.operating_range_N)
    cv = _cross_validate(spec.model_id, data, cfg)
    rejection_reasons: list[str] = []
    if metrics.n_points < max(2, min(spec.n_parameters + 1, len(data.y))):
        rejection_reasons.append("too_few_finite_predictions")
    coverage = cv.get("cv_coverage_fraction")
    if coverage is not None and float(coverage) < cfg.selection.min_cv_coverage_fraction and cv.get("cv_fold_count", 0):
        rejection_reasons.append("insufficient_cross_validation_coverage")
    if spec.diagnostic_only and not cfg.selection.allow_diagnostics_as_primary:
        rejection_reasons.append("diagnostic_only_model")
    monotonic_rejection = _monotonicity_rejection(spec, data, cfg)
    if monotonic_rejection:
        rejection_reasons.append(monotonic_rejection)

    accepted = bool(spec.deployable_to_firmware and not rejection_reasons)
    score = _score_candidate(metrics, cv, spec, rejection_reasons, cfg)
    return CandidateResult(
        model_id=spec.model_id,
        model_family=spec.family,
        parameters=spec.parameters,
        n_parameters=spec.n_parameters,
        deployable_to_firmware=spec.deployable_to_firmware,
        diagnostic_only=spec.diagnostic_only,
        metrics=metrics,
        cv_metrics=cv,
        selection_score=score,
        selection_likelihood=0.0,
        accepted_for_deployment=accepted,
        rejection_reasons=rejection_reasons,
        firmware_export=spec.firmware_export,
        notes=spec.notes,
    )


def _with_likelihoods(candidates: list[CandidateResult], cfg: FitConfig) -> list[CandidateResult]:
    eligible = [c for c in candidates if c.accepted_for_deployment]
    if not eligible:
        eligible = [c for c in candidates if c.deployable_to_firmware and not c.diagnostic_only]
    if not eligible:
        eligible = candidates
    scores = np.array([c.selection_score for c in eligible], dtype=float)
    scores = np.where(np.isfinite(scores), scores, np.nanmax(scores[np.isfinite(scores)]) + 10.0 if np.any(np.isfinite(scores)) else 10.0)
    raw = np.exp(-(scores - np.nanmin(scores)))
    denom = float(np.sum(raw)) if float(np.sum(raw)) > 0 else 1.0
    likelihood_by_id = {c.model_id: float(v / denom) for c, v in zip(eligible, raw)}
    return [replace(c, selection_likelihood=likelihood_by_id.get(c.model_id, 0.0)) for c in candidates]


def _select_candidate(candidates: list[CandidateResult], cfg: FitConfig) -> CandidateResult:
    if cfg.primary_model != "auto":
        for c in candidates:
            if c.model_id == cfg.primary_model:
                if c.accepted_for_deployment or cfg.selection.allow_diagnostics_as_primary:
                    return c
                # If explicitly requested but gated, return it anyway with clear rejection reasons.
                return c
        raise ValueError(f"Configured primary_model={cfg.primary_model!r} was not fitted")

    eligible = [c for c in candidates if c.accepted_for_deployment]
    if not eligible:
        fallback = [c for c in candidates if c.model_id in {"affine_wls", "affine_ols", "affine_huber"}]
        if fallback:
            return sorted(fallback, key=lambda c: c.selection_score)[0]
        return sorted(candidates, key=lambda c: c.selection_score)[0]

    best = sorted(eligible, key=lambda c: c.selection_score)[0]
    if not cfg.selection.prefer_simpler_within_cv_rmse_se:
        return best

    best_cv = best.cv_metrics.get("cv_rmse_N")
    best_se = best.cv_metrics.get("cv_rmse_se_N")
    if best_cv is None:
        return best
    tolerance = float(best_se) if best_se is not None and math.isfinite(float(best_se)) else max(0.02 * float(best_cv), 1e-12)
    within: list[CandidateResult] = []
    for c in eligible:
        cv_rmse = c.cv_metrics.get("cv_rmse_N")
        metric = float(cv_rmse) if cv_rmse is not None and math.isfinite(float(cv_rmse)) else c.metrics.rmse_N
        if metric <= float(best_cv) + tolerance:
            within.append(c)
    if not within:
        return best
    family_order = {
        "affine_ols": 0,
        "affine_wls": 1,
        "affine_huber": 2,
        "quadratic_wls": 3,
        "piecewise_linear_monotone": 4,
    }
    return sorted(within, key=lambda c: (c.n_parameters, family_order.get(c.model_id, 99), c.selection_score))[0]


def _ranking(candidates: list[CandidateResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, c in enumerate(sorted(candidates, key=lambda c: c.selection_score), start=1):
        rows.append({
            "rank": rank,
            "model_id": c.model_id,
            "model_family": c.model_family,
            "accepted_for_deployment": c.accepted_for_deployment,
            "diagnostic_only": c.diagnostic_only,
            "selection_score": _finite_or_none(c.selection_score),
            "selection_likelihood": _finite_or_none(c.selection_likelihood),
            "rmse_N": _finite_or_none(c.metrics.rmse_N),
            "cv_rmse_N": _finite_or_none(c.cv_metrics.get("cv_rmse_N")),
            "max_abs_error_N": _finite_or_none(c.metrics.max_abs_error_N),
            "max_abs_error_percent_range": _finite_or_none(c.metrics.max_abs_error_percent_range),
            "r2": _finite_or_none(c.metrics.r2),
            "n_parameters": c.n_parameters,
            "rejection_reasons": c.rejection_reasons,
        })
    return rows


def fit_candidates_from_dataset(dataset: pd.DataFrame, config: AppConfig) -> tuple[pd.DataFrame, list[CandidateResult], list[str]]:
    """Fit all configured candidate models from a calibration hold dataset."""

    data, notes = _prepare_fit_data(dataset, config)
    candidates: list[CandidateResult] = []
    for model_id in config.fit.candidate_models:
        if model_id == "odr_affine" and not config.fit.diagnostics.enable_odr_affine:
            continue
        if model_id == "hysteresis_affine_diagnostic" and not config.fit.diagnostics.enable_hysteresis:
            continue
        if model_id == "drift_affine_diagnostic" and not config.fit.diagnostics.enable_drift:
            continue
        try:
            spec = _FITTERS[model_id](data, config.fit)
            candidates.append(_candidate_from_spec(spec, data, config.fit))
        except Exception as exc:
            # Failed candidates are still surfaced in fit_candidates.json so the
            # report can explain why they were unavailable for a given session.
            failed_metrics = FitMetrics(
                n_points=0,
                rmse_N=float("nan"),
                mae_N=float("nan"),
                max_abs_error_N=float("nan"),
                max_abs_error_percent_range=float("nan"),
                r2=float("nan"),
                adjusted_r2=float("nan"),
                residual_bias_N=float("nan"),
                residual_std_N=float("nan"),
                aicc=float("nan"),
                bic=float("nan"),
            )
            candidates.append(CandidateResult(
                model_id=model_id,
                model_family="unavailable",
                parameters={},
                n_parameters=0,
                deployable_to_firmware=False,
                diagnostic_only=model_id.endswith("_diagnostic") or model_id == "odr_affine",
                metrics=failed_metrics,
                cv_metrics={
                    "cv_rmse_N": None,
                    "cv_mae_N": None,
                    "cv_max_abs_error_N": None,
                    "cv_max_abs_error_percent_range": None,
                    "cv_rmse_se_N": None,
                    "cv_fold_count": 0,
                    "cv_point_count": 0,
                    "cv_coverage_fraction": 0.0,
                },
                selection_score=float("inf"),
                selection_likelihood=0.0,
                accepted_for_deployment=False,
                rejection_reasons=["fit_failed"],
                firmware_export=None,
                notes=[str(exc)],
            ))
    if not candidates:
        raise ValueError("No fit candidates were evaluated")
    return data.frame, _with_likelihoods(candidates, config.fit), notes


def _result_from_candidate(selected: CandidateResult, candidates: list[CandidateResult], notes: list[str], config: AppConfig) -> CalibrationFitResult:
    params = selected.parameters
    a: float | None = None
    b: float | None = None
    if "a" in params and "b" in params:
        a = float(params["a"])
        b = float(params["b"])
    elif selected.model_id == "quadratic_wls":
        # Provide local affine tangent at the median raw value only as metadata;
        # firmware should use the quadratic constants below.
        a2 = float(params["a2"])
        a1 = float(params["a1"])
        a0 = float(params["a0"])
        a = a1
        b = a0
        notes.append("Selected model is quadratic; force_N.a/b are only a legacy linear component. Use model_parameters for deployment.")
    elif selected.model_id == "piecewise_linear_monotone":
        xk = np.asarray(params.get("x_raw_knots", []), dtype=float)
        yk = np.asarray(params.get("force_N_knots", []), dtype=float)
        if len(xk) >= 2:
            coeff = np.polyfit(xk, yk, deg=1)
            a = float(coeff[0])
            b = float(coeff[1])
            notes.append("Selected model is multipoint; force_N.a/b are only a least-squares legacy approximation. Use knot table for deployment.")

    threshold = config.fit.residual_threshold_percent_operating_range
    result_notes = list(notes)
    if selected.metrics.max_abs_error_percent_range > threshold:
        result_notes.append(
            "Residual threshold exceeded. Inspect residual plots; improve static holds or use nonlinear correction only if repeatability is verified."
        )
    if selected.rejection_reasons:
        result_notes.append(f"Selected model has gate warnings: {', '.join(selected.rejection_reasons)}")

    firmware = selected.firmware_export or {"type": "none", "warning": "Selected model has no firmware export."}
    return CalibrationFitResult(
        schema="handgrip_fit_result.v2",
        model=selected.model_id,
        selected_model_id=selected.model_id,
        selected_model_family=selected.model_family,
        force_N_a=a,
        force_N_b=b,
        model_parameters=selected.parameters,
        metrics=selected.metrics,
        cv_metrics=selected.cv_metrics,
        residual_threshold_percent_range=threshold,
        passes_residual_threshold=bool(selected.metrics.max_abs_error_percent_range <= threshold),
        selection_likelihood=float(selected.selection_likelihood),
        model_ranking=_ranking(candidates),
        recommended_firmware_constants=firmware,
        notes=result_notes,
    )


def fit_model_selection_from_dataset(dataset: pd.DataFrame, config: AppConfig) -> tuple[pd.DataFrame, CalibrationFitResult, list[CandidateResult]]:
    """Fit all candidates, select the deployment model, and return all results."""

    fit_frame, candidates, notes = fit_candidates_from_dataset(dataset, config)
    selected = _select_candidate(candidates, config.fit)
    result = _result_from_candidate(selected, candidates, notes, config)
    return fit_frame, result, candidates


def fit_affine_from_dataset(dataset: pd.DataFrame, config: AppConfig) -> CalibrationFitResult:
    """Backward-compatible wrapper returning the selected fit result.

    Older callers imported this function expecting an affine result. It now runs
    the configured model-selection strategy and returns the selected model while
    preserving affine-style ``force_N_a`` / ``force_N_b`` fields when available.
    """

    _, result, _ = fit_model_selection_from_dataset(dataset, config)
    return result


def fit_session(session_dir: str | Path, config: AppConfig) -> tuple[pd.DataFrame, CalibrationFitResult]:
    """Segment a session, fit all candidates, and write fit artifacts.

    Written files:
    - ``calibration_dataset.csv`` from segmentation.
    - ``fit_result.json`` containing the selected model.
    - ``fit_candidates.json`` containing every candidate and its metrics.
    - ``model_selection_report.json`` containing compact ranking metadata.
    """

    session_dir = Path(session_dir)
    dataset = segment_accepted_holds(session_dir, config=config)
    _, result, candidates = fit_model_selection_from_dataset(dataset, config)
    write_json(session_dir / "fit_result.json", result.to_dict())
    write_json(session_dir / "fit_candidates.json", [c.to_dict() for c in candidates])
    write_json(session_dir / "model_selection_report.json", {
        "schema": "handgrip_model_selection_report.v1",
        "selected_model_id": result.selected_model_id,
        "selected_model_family": result.selected_model_family,
        "selection_likelihood": result.selection_likelihood,
        "passes_residual_threshold": result.passes_residual_threshold,
        "residual_threshold_percent_range": result.residual_threshold_percent_range,
        "ranking": result.model_ranking,
    })
    # Persist fit-stage events into the same event log used by the recorder. This
    # makes the full lifecycle auditable even when fitting/reporting are run
    # after the live acquisition process has stopped.
    append_ndjson(session_dir / "events.ndjson", [
        {
            "event": "calibration_candidate_selected",
            "session_id": session_dir.name,
            "host_time_unix": __import__("time").time(),
            "phase": "fit",
            "payload": {
                "selected_model_id": result.selected_model_id,
                "selected_model_family": result.selected_model_family,
                "selection_likelihood": result.selection_likelihood,
                "passes_residual_threshold": result.passes_residual_threshold,
            },
        },
        {
            "event": "firmware_constants_exported",
            "session_id": session_dir.name,
            "host_time_unix": __import__("time").time(),
            "phase": "fit",
            "payload": result.recommended_firmware_constants,
        },
    ])
    return dataset, result
