"""Markdown/HTML report generation for a calibration session."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from . import report_interpretation as ri
from .export import ensure_dir, read_ndjson
from .protocol_analysis import (
    creep_zero_return_summary,
    dynamic_summary,
    event_count_table,
    hold_quality_summary,
    hysteresis_summary,
    stream_health_table,
)

log = logging.getLogger(__name__)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {} if path.suffix == ".json" else None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_plot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _candidate_predict(candidate: dict[str, Any], frame: pd.DataFrame, x: np.ndarray) -> np.ndarray:
    """Predict from a serialized candidate result.

    This mirrors the deployable model families from ``fitting.py`` so report
    generation does not need to refit the session.
    """

    model_id = candidate.get("model_id")
    params = candidate.get("parameters", {}) or {}
    if model_id in {"affine_ols", "affine_wls", "affine_huber", "odr_affine"}:
        return float(params["a"]) * x + float(params["b"])
    if model_id == "quadratic_wls":
        return float(params["a2"]) * x**2 + float(params["a1"]) * x + float(params["a0"])
    if model_id == "piecewise_linear_monotone":
        xk = np.asarray(params.get("x_raw_knots", []), dtype=float)
        yk = np.asarray(params.get("force_N_knots", []), dtype=float)
        if len(xk) < 2:
            return np.full_like(x, np.nan, dtype=float)
        pred = np.interp(x, xk, yk)
        if params.get("extrapolation", "reject") == "reject":
            edge_margin = max(1.0, 0.005 * float(xk[-1] - xk[0]))
            pred = pred.astype(float)
            pred[(x < xk[0] - edge_margin) | (x > xk[-1] + edge_margin)] = np.nan
        return pred
    if model_id == "hysteresis_affine_diagnostic":
        dirs = params.get("directions", {}) or {}
        fallback = params.get("fallback_affine", {}) or {}
        out = np.empty_like(x, dtype=float)
        direction_values = (
            frame["direction"].astype(str).to_numpy()
            if "direction" in frame.columns
            else np.array([""] * len(x))
        )
        for i, (xx, direction) in enumerate(zip(x, direction_values)):
            p = dirs.get(str(direction), fallback)
            if "a" not in p or "b" not in p:
                out[i] = np.nan
            else:
                out[i] = float(p["a"]) * xx + float(p["b"])
        return out
    if model_id == "drift_affine_diagnostic":
        if "t_mid_lsl" in frame.columns:
            t = frame["t_mid_lsl"].to_numpy(dtype=float)
        elif {"t_start_lsl", "t_end_lsl"}.issubset(frame.columns):
            t = 0.5 * (
                frame["t_start_lsl"].to_numpy(dtype=float)
                + frame["t_end_lsl"].to_numpy(dtype=float)
            )
        else:
            t = np.full_like(x, float(params.get("time_center_lsl", 0.0)))
        tc = t - float(params.get("time_center_lsl", np.nanmedian(t)))
        return float(params["a"]) * x + float(params["b"]) + float(params["drift_N_per_s"]) * tc
    return np.full_like(x, np.nan, dtype=float)


def _selected_candidate(
    fit: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any] | None:
    selected_id = fit.get("selected_model_id") or fit.get("model")
    for candidate in candidates:
        if candidate.get("model_id") == selected_id:
            return candidate
    # Backward-compatible fallback for old affine-only fit_result.json.
    coeff = fit.get("force_N", {}) if isinstance(fit, dict) else {}
    if coeff.get("a") is not None and coeff.get("b") is not None:
        return {
            "model_id": "affine_legacy",
            "parameters": {"a": coeff["a"], "b": coeff["b"]},
            "metrics": fit.get("metrics", {}),
        }
    return None


def generate_plots(session_dir: str | Path) -> list[Path]:
    # @brief Generate diagnostic plots for a calibration session.
    #  @param session_dir Session directory path.
    #  @return List of generated plot file paths.
    """Generate diagnostic plots from session files.

    Plots are intentionally simple and independent. This keeps the report useful
    on a lab PC without an interactive plotting stack.
    """

    session_dir = Path(session_dir)
    plots_dir = ensure_dir(session_dir / "plots")
    generated: list[Path] = []
    target_csv = session_dir / "target.csv"
    reference_csv = session_dir / "reference.csv"
    dataset_csv = session_dir / "calibration_dataset.csv"
    fit_json = session_dir / "fit_result.json"
    candidates_json = session_dir / "fit_candidates.json"

    if target_csv.exists() and reference_csv.exists():
        target = pd.read_csv(target_csv)
        reference = pd.read_csv(reference_csv)
        if "timestamp_lsl" in target and "raw" in target and not target.empty:
            plt.figure(figsize=(10, 4))
            plt.plot(
                target["timestamp_lsl"] - target["timestamp_lsl"].iloc[0],
                target["raw"],
                label="target raw",
            )
            plt.xlabel("Time since target start [s]")
            plt.ylabel("Target raw / units")
            plt.title("Target time series")
            plt.legend()
            out = plots_dir / "target_timeseries.png"
            _save_plot(out)
            generated.append(out)
        if "timestamp_lsl" in reference and "raw" in reference and not reference.empty:
            plt.figure(figsize=(10, 4))
            plt.plot(
                reference["timestamp_lsl"] - reference["timestamp_lsl"].iloc[0],
                reference["raw"],
                label="reference raw/force",
            )
            plt.xlabel("Time since reference start [s]")
            plt.ylabel("Reference force / raw")
            plt.title("Reference time series")
            plt.legend()
            out = plots_dir / "reference_timeseries.png"
            _save_plot(out)
            generated.append(out)

    if dataset_csv.exists() and fit_json.exists():
        dataset = pd.read_csv(dataset_csv)
        fit = _load_json(fit_json) or {}
        candidates_raw = _load_json(candidates_json) if candidates_json.exists() else []
        candidates = candidates_raw if isinstance(candidates_raw, list) else []
        selected = _selected_candidate(fit, candidates)
        if not dataset.empty and selected is not None:
            x = dataset["target_raw_median"].to_numpy(dtype=float)
            y = dataset["reference_force_median_N"].to_numpy(dtype=float)
            order = np.argsort(x)
            pred_selected = _candidate_predict(selected, dataset, x)

            # Plot 1: all deployable candidate curves over the calibration range.
            x_grid = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), 250)
            grid_frame = pd.DataFrame({"target_raw_median": x_grid})
            plt.figure(figsize=(8, 5))
            plt.scatter(x, y, label="accepted holds")
            plotted_any = False
            for candidate in candidates:
                if candidate.get("parameters") and candidate.get("model_family") != "unavailable":
                    # Keep the comparison readable: plot deployable candidates and the selected candidate.
                    is_selected = candidate.get("model_id") == (
                        fit.get("selected_model_id") or fit.get("model")
                    )
                    if not (candidate.get("deployable_to_firmware") or is_selected):
                        continue
                    y_grid = _candidate_predict(candidate, grid_frame, x_grid)
                    if np.count_nonzero(np.isfinite(y_grid)) >= 2:
                        label = str(candidate.get("model_id"))
                        if is_selected:
                            label += " (selected)"
                        plt.plot(x_grid, y_grid, label=label)
                        plotted_any = True
            if not plotted_any:
                plt.plot(x[order], pred_selected[order], label=str(selected.get("model_id")))
            plt.xlabel("Target raw median")
            plt.ylabel("Reference force median [N]")
            plt.title("Calibration model comparison")
            plt.legend()
            out = plots_dir / "model_comparison_curve.png"
            _save_plot(out)
            generated.append(out)

            # Plot 2: selected residuals by force.
            plt.figure(figsize=(7, 4))
            plt.axhline(0, linestyle="--", linewidth=1)
            plt.scatter(y, y - pred_selected)
            plt.xlabel("Reference force [N]")
            plt.ylabel("Residual [N]")
            plt.title(f"Selected residuals: {selected.get('model_id')}")
            out = plots_dir / "selected_residuals_by_force.png"
            _save_plot(out)
            generated.append(out)

            # Plot 3: compact residual comparison for fitted candidates.
            plt.figure(figsize=(8, 5))
            plt.axhline(0, linestyle="--", linewidth=1)
            plotted = 0
            for candidate in candidates:
                if (
                    not candidate.get("parameters")
                    or candidate.get("model_family") == "unavailable"
                ):
                    continue
                if not candidate.get("deployable_to_firmware") and candidate.get("model_id") != (
                    fit.get("selected_model_id") or fit.get("model")
                ):
                    continue
                pred = _candidate_predict(candidate, dataset, x)
                if np.count_nonzero(np.isfinite(pred)) >= 2:
                    plt.scatter(y, y - pred, label=str(candidate.get("model_id")), alpha=0.75)
                    plotted += 1
            if plotted:
                plt.xlabel("Reference force [N]")
                plt.ylabel("Residual [N]")
                plt.title("Residual comparison by candidate")
                plt.legend()
                out = plots_dir / "model_comparison_residuals.png"
                _save_plot(out)
                generated.append(out)
            else:
                plt.close()

            # Plot 4: metric bars.
            rows: list[dict[str, Any]] = []
            for candidate in candidates:
                metrics = candidate.get("metrics", {}) or {}
                if metrics.get("rmse_N") is not None:
                    rows.append(
                        {
                            "model_id": candidate.get("model_id"),
                            "rmse_N": metrics.get("rmse_N"),
                            "max_abs_error_N": metrics.get("max_abs_error_N"),
                        }
                    )
            metric_df = pd.DataFrame(rows).dropna()
            if not metric_df.empty:
                metric_df = metric_df.sort_values("rmse_N")
                xs = np.arange(len(metric_df))
                width = 0.35
                plt.figure(figsize=(max(8, len(metric_df) * 1.2), 4.5))
                plt.bar(xs - width / 2, metric_df["rmse_N"], width, label="RMSE [N]")
                plt.bar(xs + width / 2, metric_df["max_abs_error_N"], width, label="Max abs [N]")
                plt.xticks(xs, metric_df["model_id"], rotation=30, ha="right")
                plt.ylabel("Error [N]")
                plt.title("Model error metrics")
                plt.legend()
                out = plots_dir / "model_metric_bars.png"
                _save_plot(out)
                generated.append(out)

            # Plot 5: model likelihoods / decision weights.
            likelihood_rows = [
                {
                    "model_id": c.get("model_id"),
                    "selection_likelihood": c.get("selection_likelihood", 0.0),
                }
                for c in candidates
                if c.get("selection_likelihood", 0.0) is not None
            ]
            likelihood_df = pd.DataFrame(likelihood_rows)
            if not likelihood_df.empty and float(likelihood_df["selection_likelihood"].sum()) > 0:
                likelihood_df = likelihood_df.sort_values("selection_likelihood", ascending=False)
                plt.figure(figsize=(max(8, len(likelihood_df) * 1.2), 4.5))
                plt.bar(likelihood_df["model_id"], likelihood_df["selection_likelihood"])
                plt.ylabel("Relative decision likelihood")
                plt.title("Model-selection likelihoods")
                plt.xticks(rotation=30, ha="right")
                out = plots_dir / "model_likelihoods.png"
                _save_plot(out)
                generated.append(out)

            # Plot 6: robust weights if the Huber model was fitted.
            for candidate in candidates:
                if candidate.get("model_id") == "affine_huber":
                    weights = candidate.get("parameters", {}).get("robust_weights")
                    if weights:
                        plt.figure(figsize=(7, 4))
                        plt.scatter(np.arange(len(weights)), weights)
                        plt.ylim(0, 1.05)
                        plt.xlabel("Accepted hold index")
                        plt.ylabel("Robust training weight")
                        plt.title("Huber robust-fit hold weights")
                        out = plots_dir / "robust_huber_weights.png"
                        _save_plot(out)
                        generated.append(out)
                    break

            if "direction" in dataset.columns:
                plt.figure(figsize=(7, 4))
                for direction, group in dataset.groupby("direction"):
                    plt.scatter(
                        group["reference_force_median_N"],
                        group["target_raw_median"],
                        label=str(direction),
                    )
                plt.xlabel("Reference force [N]")
                plt.ylabel("Target raw median")
                plt.title("Ascending/descending hold comparison")
                plt.legend()
                out = plots_dir / "hysteresis_up_down.png"
                _save_plot(out)
                generated.append(out)
    return generated


def _table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_No rows._\n"
    present = [c for c in columns if c in df.columns]
    return df[present].to_markdown(index=False) + "\n"


def _candidate_table(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "_No candidate model file found._\n"
    rows = []
    for c in candidates:
        m = c.get("metrics", {}) or {}
        cv = c.get("cv_metrics", {}) or {}
        rows.append(
            {
                "model": c.get("model_id"),
                "family": c.get("model_family"),
                "deploy": c.get("accepted_for_deployment"),
                "likelihood": c.get("selection_likelihood"),
                "RMSE_N": m.get("rmse_N"),
                "CV_RMSE_N": cv.get("cv_rmse_N"),
                "MaxAbs_N": m.get("max_abs_error_N"),
                "R2": m.get("r2"),
                "rejections": ";".join(c.get("rejection_reasons", [])),
            }
        )
    return pd.DataFrame(rows).to_markdown(index=False) + "\n"


def _dict_table(data: dict[str, Any]) -> str:
    if not data:
        return "_No data available._\n"
    return (
        pd.DataFrame([{"metric": k, "value": v} for k, v in data.items()]).to_markdown(index=False)
        + "\n"
    )


def _safe_json_excerpt(data: Any, limit: int = 6000) -> str:
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)[:limit]
    except Exception:
        return str(data)[:limit]


def generate_report(session_dir: str | Path) -> Path:
    # @brief Generate Markdown and HTML calibration reports for a session.
    #  @param session_dir Session directory path.
    #  @return Path to the generated HTML report.
    """Generate Markdown and HTML calibration reports.

    The report is intentionally protocol-aware. Some sections will be marked as
    not available when a session did not run that protocol layer; this lets the
    same command summarize reference verification, primary calibration, creep,
    dynamic validation, and holdout sessions without branching the user workflow.
    """

    session_dir = Path(session_dir)
    manifest = _load_yaml(session_dir / "session_manifest.yaml")
    fit = _load_json(session_dir / "fit_result.json") or {}
    validation = _load_json(session_dir / "holdout_validation.json") or {}
    candidates_raw = (
        _load_json(session_dir / "fit_candidates.json")
        if (session_dir / "fit_candidates.json").exists()
        else []
    )
    candidates = candidates_raw if isinstance(candidates_raw, list) else []
    events = read_ndjson(session_dir / "events.ndjson")
    dataset = (
        pd.read_csv(session_dir / "calibration_dataset.csv")
        if (session_dir / "calibration_dataset.csv").exists()
        else pd.DataFrame()
    )
    holdout_predictions = (
        pd.read_csv(session_dir / "holdout_predictions.csv")
        if (session_dir / "holdout_predictions.csv").exists()
        else pd.DataFrame()
    )
    plots = generate_plots(session_dir)

    session = manifest.get("session", {})
    protocol = manifest.get("protocol", {})
    metrics = fit.get("metrics", {}) if isinstance(fit, dict) else {}
    coeff = fit.get("force_N", {}) if isinstance(fit, dict) else {}
    selected_model = (
        fit.get("selected_model_id", fit.get("model", "unknown"))
        if isinstance(fit, dict)
        else "unknown"
    )
    model_family = (
        fit.get("selected_model_family", "unknown") if isinstance(fit, dict) else "unknown"
    )
    firmware = fit.get("recommended_firmware_constants", {}) if isinstance(fit, dict) else {}
    stream_table = stream_health_table(session_dir)
    counts_table = event_count_table(session_dir)
    hold_summary = hold_quality_summary(dataset)
    hyst = hysteresis_summary(dataset)
    creep = creep_zero_return_summary(session_dir)
    dyn = dynamic_summary(session_dir)

    deployment_recommendation = "insufficient_evidence"
    if validation:
        deployment_recommendation = validation.get(
            "firmware_deployment_recommendation", deployment_recommendation
        )
    elif fit:
        deployment_recommendation = "fit_available_but_holdout_validation_missing"

    lines = [
        "# Handgrip Calibration Report",
        "",
        "## Summary",
        "",
        f"- **Session ID:** `{session.get('session_id', session_dir.name)}`",
        f"- **Operator:** {session.get('operator', 'unknown')}",
        f"- **Purpose:** {session.get('purpose', 'unknown')}",
        f"- **Protocol:** `{protocol.get('name', 'unknown')}` / type `{protocol.get('protocol_type', 'unknown')}`",
        f"- **Selected model:** `{selected_model}` ({model_family})"
        if fit
        else "- **Selected model:** not fitted in this session",
        f"- **Model-selection likelihood:** {fit.get('selection_likelihood', float('nan')):.3f}"
        if isinstance(fit.get("selection_likelihood"), (int, float))
        else "- **Model-selection likelihood:** not available",
        f"- **Affine-compatible equation:** `force_N = {coeff.get('a', float('nan')):.12g} * raw + {coeff.get('b', float('nan')):.12g}`"
        if coeff
        else "- **Affine-compatible equation:** not available",
        f"- **RMSE:** {metrics.get('rmse_N', float('nan')):.6g} N"
        if metrics
        else "- **RMSE:** not available",
        f"- **Max abs error:** {metrics.get('max_abs_error_N', float('nan')):.6g} N"
        if metrics
        else "- **Max abs error:** not available",
        f"- **Residual threshold pass:** {fit.get('passes_residual_threshold', 'unknown') if fit else 'not evaluated'}",
        f"- **Firmware deployment recommendation:** `{deployment_recommendation}`",
        "",
        "## 1. Reference-chain verification summary",
        "",
        ri.SECTION_INTROS["1. Reference-chain verification summary"],
        "",
        "This section verifies acquisition integrity before treating the RS485 reference as ground truth.",
        "",
        _table(
            stream_table,
            [
                "stream",
                "n_samples",
                "duration_s",
                "sample_rate_hz",
                "max_gap_s",
                "value_col",
                "mean",
                "std",
                "min",
                "max",
            ],
        ),
        "",
        *ri.ref_block(
            "sec.reference_chain", interpretation=ri.interpret_stream_health(stream_table)
        ),
        "### Event counts",
        "",
        _table(counts_table, ["event", "count"]),
        "",
        *ri.ref_block("sec.events", interpretation=ri.interpret_event_completeness(counts_table)),
        "## 2. Static fit summary",
        "",
        ri.SECTION_INTROS["2. Static fit summary"],
        "",
        _dict_table(hold_summary),
        "",
        "### Accepted hold dataset",
        "",
        _table(
            dataset,
            [
                "trial_id",
                "target_force_nominal_N",
                "direction",
                "target_raw_median",
                "reference_force_median_N",
                "reference_force_std_N",
                "reference_slope_N_s",
                "accepted_by_quality",
                "quality_rejection_reason",
            ],
        ),
        "",
        "## 3. Holdout accuracy summary",
        "",
        ri.SECTION_INTROS["3. Holdout accuracy summary"],
        "",
        *ri.ref_block("sec.holdout", interpretation=ri.interpret_holdout(validation)),
        *(
            [
                "### Holdout validation result",
                "",
                "```json",
                _safe_json_excerpt(validation, 4000),
                "```",
                "",
                "### Holdout predictions",
                "",
                _table(
                    holdout_predictions,
                    [
                        "trial_id",
                        "target_force_nominal_N",
                        "direction",
                        "reference_force_median_N",
                        "predicted_force_N",
                        "holdout_residual_N",
                        "accepted_by_quality",
                    ],
                ),
            ]
            if validation
            else [
                "> **Holdout validation not yet performed.**",
                "> Run `handgrip-cal validate-holdout <holdout_dir> --model <this_dir>/fit_result.json`",
                "> to populate this section and upgrade this report to the integrated view.",
            ]
        ),
        "",
        "## 4. Hysteresis / reversibility summary",
        "",
        ri.SECTION_INTROS["4. Hysteresis / reversibility summary"],
        "",
        _table(
            hyst,
            [
                "force_N",
                "n_ascending",
                "n_descending",
                "target_raw_delta_desc_minus_asc",
                "reference_force_delta_desc_minus_asc_N",
            ],
        ),
        "",
        "## 5. Creep / zero-return summary",
        "",
        ri.SECTION_INTROS["5. Creep / zero-return summary"],
        "",
        _table(
            creep,
            [
                "phase",
                "target_force_N",
                "duration_s",
                "n_reference_samples",
                "reference_start_mean_N",
                "reference_end_mean_N",
                "delta_end_minus_start_N",
                "slope_N_per_s",
            ],
        ),
        "",
        "## 6. Dynamic validation summary",
        "",
        ri.SECTION_INTROS["6. Dynamic validation summary"],
        "",
        _table(
            dyn, ["trial_type", "label", "index", "duration_s", "peak_force_N", "speed_N_per_s"]
        ),
        "",
        "## 7. Previous calibration comparison",
        "",
        ri.SECTION_INTROS["7. Previous calibration comparison"],
        "",
        "Not computed automatically in this report. Compare sessions by running the same holdout protocol against the old and new `fit_result.json` files, then compare `holdout_validation.json` metrics: RMSE, max absolute error, bias, zero return, and hysteresis.",
        "",
        "## 8. Firmware deployment recommendation",
        "",
        ri.SECTION_INTROS["8. Firmware deployment recommendation"],
        "",
        f"**Recommendation:** `{deployment_recommendation}`",
        "",
        "Deploy constants only when the selected model passes residual gates and an independent holdout session passes its holdout gate. If this report has no `holdout_validation.json`, treat the firmware constants as provisional.",
        "",
        "### Firmware export",
        "",
        "```json",
        _safe_json_excerpt(firmware, 4000),
        "```",
        "",
        *ri.ref_block("firmware.hx711_scale_offset", interpretation=ri.interpret_firmware(firmware)),
        "## Model candidate ranking",
        "",
        ri.SECTION_INTROS["Model candidate ranking"],
        "",
        _candidate_table(candidates),
        "",
        *(
            ["**Selected-model read-out:**", ""]
            + [f"- {line}" for line in ri.interpret_metrics(fit)]
            + ["", f"- {ri.interpret_selection(fit, candidates)}", ""]
            if fit
            else []
        ),
        "## Selected fit result JSON excerpt",
        "",
        "```json",
        _safe_json_excerpt(fit, 6000),
        "```",
        "",
        "## Event summary",
        "",
        _table(
            pd.DataFrame(events),
            [
                "event",
                "trial_id",
                "target_force_N",
                "phase",
                "reason",
                "host_time_unix",
                "lsl_time",
            ],
        ),
        "",
        "## Plots",
        "",
    ]
    for plot in plots:
        rel = plot.relative_to(session_dir)
        lines.append(f"![{plot.stem}]({rel.as_posix()})")
        lines.append("")
        lines.extend(
            ri.ref_block(
                f"plot.{plot.stem}",
                summary=ri.PLOT_SUMMARIES.get(plot.stem, ""),
                interpretation=ri.interpret_plot(plot.stem, fit, dataset, candidates),
            )
        )
    lines.extend(
        [
            "## Interpretation guidance",
            "",
            f"For full definitions and how-to-read guidance for every metric, model, and plot "
            f"above, see the {ri.doc_link('sec.summary', 'Calibration Report Reference')}.",
            "",
            "- Use static staircase holds for primary model fitting.",
            "- Use low-force refinement only if low-force residuals are systematic and reference noise is acceptable.",
            "- Use creep/zero-return and dynamic protocols as validation/diagnostic layers, not as primary coefficient estimators.",
            "- Prefer the selected model only inside the calibrated raw-count and force range.",
            "- Treat `odr_affine`, `hysteresis_affine_diagnostic`, and `drift_affine_diagnostic` as diagnostics unless explicitly configured otherwise.",
            "- If a nonlinear model wins by only a tiny margin, prefer the affine model and improve the calibration protocol before increasing firmware complexity.",
            "",
            "## Firmware constant caution",
            "",
            "The report includes HX711-style scale/offset approximations for affine models, but firmware constants must be verified against the exact HX711 library semantics before flashing. In particular, confirm whether the runtime uses `force = a * raw + b` or `units = (raw - offset) / scale`.",
            "",
            "## Limitations",
            "",
            "- The fit is only as good as the accepted static holds.",
            "- Dynamic trials are validation data, not primary fit data.",
            "- If the reference board applies hidden zeroing, display masking, dynamic tracking, or stability gating, the reference trace may not represent the true physical input.",
        ]
    )
    md_path = session_dir / "calibration_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report written: %s", md_path)

    html = (
        "<html><head><meta charset='utf-8'><title>Handgrip Calibration Report</title></head><body><pre>"
        + md_path.read_text(encoding="utf-8")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        + "</pre></body></html>"
    )
    (session_dir / "calibration_report.html").write_text(html, encoding="utf-8")
    return md_path
