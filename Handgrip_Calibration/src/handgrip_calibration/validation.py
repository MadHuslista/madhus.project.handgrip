# @package handgrip_calibration.validation
#  @brief Independent protocol validation utilities.
"""Independent protocol validation utilities.

The primary fitter selects a model from static calibration holds. This module is
for holdout sessions: segment the holdout holds, apply an already-selected model,
and write metrics without refitting. This is the release gate before firmware
constants are deployed.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ._utils import finite_or_none as _finite_or_none
from .config_schema import AppConfig
from .export import write_json
from .report import _candidate_predict
from .segmentation import segment_accepted_holds

log = logging.getLogger(__name__)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray, *, operating_range_N: float) -> dict[str, Any]:
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    n = int(np.count_nonzero(valid))
    if n == 0:
        return {
            "n_points": 0,
            "rmse_N": None,
            "mae_N": None,
            "max_abs_error_N": None,
            "max_abs_error_percent_range": None,
            "bias_N": None,
            "residual_std_N": None,
            "r2": None,
        }
    residuals = y_true[valid] - y_pred[valid]
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y_true[valid] - np.mean(y_true[valid])) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {
        "n_points": n,
        "rmse_N": _finite_or_none(float(np.sqrt(np.mean(residuals**2)))),
        "mae_N": _finite_or_none(float(np.mean(np.abs(residuals)))),
        "max_abs_error_N": _finite_or_none(float(np.max(np.abs(residuals)))),
        "max_abs_error_percent_range": _finite_or_none(float(100.0 * np.max(np.abs(residuals)) / operating_range_N)),
        "bias_N": _finite_or_none(float(np.mean(residuals))),
        "residual_std_N": _finite_or_none(float(np.std(residuals, ddof=1)) if n > 1 else 0.0),
        "r2": _finite_or_none(float(r2)),
    }


def _candidate_from_fit_result(fit: dict[str, Any]) -> dict[str, Any]:
    model_id = str(fit.get("selected_model_id") or fit.get("model") or "affine_legacy")
    params = dict(fit.get("model_parameters") or {})
    if not params and isinstance(fit.get("force_N"), dict):
        force = fit["force_N"]
        if force.get("a") is not None and force.get("b") is not None:
            params = {"a": force["a"], "b": force["b"]}
    return {
        "model_id": model_id,
        "model_family": fit.get("selected_model_family", "unknown"),
        "parameters": params,
    }


def _thresholds(config: AppConfig) -> dict[str, float]:
    """Derive release-gate thresholds from typed config or operating_range_N defaults."""
    ht = config.holdout_thresholds
    operating_range = float(config.fit.operating_range_N)
    return {
        "max_rmse_N": ht.max_rmse_N if ht.max_rmse_N is not None else max(1.0, 0.01 * operating_range),
        "max_abs_error_N": ht.max_abs_error_N if ht.max_abs_error_N is not None else max(2.0, 0.02 * operating_range),
        "max_bias_N": ht.max_bias_N if ht.max_bias_N is not None else max(0.5, 0.005 * operating_range),
    }


def validate_session_against_model(holdout_session_dir: str | Path, model_fit_result: str | Path, config: AppConfig) -> dict[str, Any]:
    # @brief Validate an independent holdout session against an existing fitted model.
    #  @param holdout_session_dir Path to the holdout session directory.
    #  @param model_fit_result Path to an existing fit_result.json artifact.
    #  @param config Application configuration with validation thresholds.
    #  @return Validation result dictionary with metrics and pass/fail recommendation.
    """Validate a holdout session against an existing ``fit_result.json``.

    The holdout session is segmented using accepted static holds, but no model is
    fitted or updated. The selected model from ``model_fit_result`` is applied to
    the holdout target raw medians, and release-gate metrics are written to
    ``holdout_validation.json`` under the holdout session directory.
    """

    holdout_session_dir = Path(holdout_session_dir)
    model_fit_result = Path(model_fit_result)
    if not model_fit_result.exists():
        raise FileNotFoundError(f"Model fit result not found: {model_fit_result}")
    with model_fit_result.open("r", encoding="utf-8") as fh:
        fit = json.load(fh)
    dataset = segment_accepted_holds(holdout_session_dir, config=config)
    candidate = _candidate_from_fit_result(fit)
    if not candidate.get("parameters"):
        raise ValueError("Selected model has no serializable parameters to validate")

    x = dataset["target_raw_median"].to_numpy(dtype=float)
    y_true = dataset["reference_force_median_N"].to_numpy(dtype=float)
    y_pred = _candidate_predict(candidate, dataset, x)
    residuals = y_true - y_pred
    thresholds = _thresholds(config)
    metrics = _metrics(y_true, y_pred, operating_range_N=float(config.fit.operating_range_N))
    passes = bool(
        metrics["n_points"] > 0
        and metrics["rmse_N"] is not None
        and metrics["max_abs_error_N"] is not None
        and metrics["bias_N"] is not None
        and float(metrics["rmse_N"]) <= thresholds["max_rmse_N"]
        and float(metrics["max_abs_error_N"]) <= thresholds["max_abs_error_N"]
        and abs(float(metrics["bias_N"])) <= thresholds["max_bias_N"]
    )

    out_frame = dataset.copy()
    out_frame["predicted_force_N"] = y_pred
    out_frame["holdout_residual_N"] = residuals
    out_frame.to_csv(holdout_session_dir / "holdout_predictions.csv", index=False)

    result = {
        "schema": "handgrip_holdout_validation.v1",
        "holdout_session_dir": str(holdout_session_dir),
        "model_fit_result": str(model_fit_result),
        "selected_model_id": candidate.get("model_id"),
        "selected_model_family": candidate.get("model_family"),
        "metrics": metrics,
        "thresholds": thresholds,
        "passes_holdout_gate": passes,
        "firmware_deployment_recommendation": "approve_constants_for_deployment" if passes else "do_not_deploy_investigate_protocol_or_model",
        "notes": [
            "This validation does not refit the model; it applies the selected model to independent accepted holdout holds.",
            "Use holdout_predictions.csv for residual-by-force and direction-specific inspection.",
        ],
    }
    write_json(holdout_session_dir / "holdout_validation.json", result)
    log.info(
        "Holdout validation complete: passes_gate=%s, RMSE=%.4g N, model=%s",
        passes,
        metrics.get("rmse_N"),
        candidate.get("model_id"),
    )
    return result
