"""Affine calibration fitting.

The first implemented calibration model is intentionally simple and auditable:
reference_force_N = a * target_raw + b. Static accepted holds are reduced to one
point per hold before fitting, which prevents the 500 Hz reference stream from
numerically dominating the ~100 Hz target stream and keeps the fitted model tied
to the operator-approved protocol steps.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config_schema import AppConfig
from .export import write_json
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


@dataclass(frozen=True)
class AffineFitResult:
    """Complete affine calibration fit result."""

    schema: str
    model: str
    force_N_a: float
    force_N_b: float
    metrics: FitMetrics
    residual_threshold_percent_range: float
    passes_residual_threshold: bool
    recommended_firmware_constants: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["force_N"] = {"a": data.pop("force_N_a"), "b": data.pop("force_N_b")}
        return data


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def fit_affine_from_dataset(dataset: pd.DataFrame, config: AppConfig) -> AffineFitResult:
    """Fit `reference_force_N = a * target_raw + b` from a hold dataset."""

    fit_points = dataset[dataset["accepted_by_quality"].fillna(False)].copy()
    if fit_points.empty:
        # If no quality config was used or all points were flagged, fall back to
        # operator-accepted points but annotate the result. This is safer than
        # silently producing no calibration from a manually curated dataset.
        fit_points = dataset.copy()
        notes = ["No quality-accepted points found; fitted all operator-accepted segmented holds."]
    else:
        notes = []
    x = fit_points["target_raw_median"].to_numpy(dtype=float)
    y = fit_points["reference_force_median_N"].to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    if len(x) < 2:
        raise ValueError("At least two valid calibration points are required for an affine fit")

    if config.fit.weighted_by_reference_noise and "reference_force_std_N" in fit_points.columns:
        std = fit_points.loc[valid, "reference_force_std_N"].to_numpy(dtype=float)
        weights = 1.0 / np.maximum(std, 1e-9)
        coeff = np.polyfit(x, y, deg=1, w=weights)
    else:
        coeff = np.polyfit(x, y, deg=1)
    a = float(coeff[0])
    b = float(coeff[1])
    pred = a * x + b
    residuals = y - pred
    rmse = float(np.sqrt(np.mean(residuals**2)))
    mae = float(np.mean(np.abs(residuals)))
    max_abs = float(np.max(np.abs(residuals)))
    max_pct = 100.0 * max_abs / config.fit.operating_range_N
    threshold = config.fit.residual_threshold_percent_operating_range

    firmware_constants = {
        "affine_force_N_equals_a_raw_plus_b": {"a": a, "b": b},
        "hx711_get_units_style_approximation": {
            "scale": (1.0 / a) if a != 0 else None,
            "offset": (-b / a) if a != 0 else None,
            "warning": "Verify against the exact HX711 library semantics before flashing firmware constants.",
        },
    }
    if max_pct > threshold:
        notes.append(
            "Residual threshold exceeded. Inspect residual plots; consider better static holds or a multipoint/nonlinear correction only after repeatability is verified."
        )
    return AffineFitResult(
        schema="handgrip_fit_result.v1",
        model="affine",
        force_N_a=a,
        force_N_b=b,
        metrics=FitMetrics(
            n_points=int(len(x)),
            rmse_N=rmse,
            mae_N=mae,
            max_abs_error_N=max_abs,
            max_abs_error_percent_range=float(max_pct),
            r2=_r2(y, pred),
        ),
        residual_threshold_percent_range=threshold,
        passes_residual_threshold=bool(max_pct <= threshold),
        recommended_firmware_constants=firmware_constants,
        notes=notes,
    )


def fit_session(session_dir: str | Path, config: AppConfig) -> tuple[pd.DataFrame, AffineFitResult]:
    """Segment a session, fit the affine model, and write `fit_result.json`."""

    session_dir = Path(session_dir)
    dataset = segment_accepted_holds(session_dir, config=config)
    result = fit_affine_from_dataset(dataset, config)
    write_json(session_dir / "fit_result.json", result.to_dict())
    return dataset, result
