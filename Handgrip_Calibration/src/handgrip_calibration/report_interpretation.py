"""Human-readable summaries, doc links, and value-based interpretations.

This module keeps all non-expert explanation text and the dynamic
"interpretation from the actual fit values" logic out of ``report.py`` so the
report assembler stays a thin layout layer.

Every interpretation is defensive: missing or non-finite values produce a
neutral note rather than an exception, because the report must render for
partial sessions (no holdout, no dynamic trials, failed fits, ...).

Anchors point at ``docs/calibration-report-reference.md`` using the stable
concept IDs defined in ``docs/.work/report-concept-inventory.md``.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Repo-relative path; clickable in repo/Git/editor markdown viewers. The HTML
# report wraps markdown in <pre>, so there the link shows as plain text.
DOC_REF = "Handgrip_Calibration/docs/calibration-report-reference.md"

# concept id -> heading anchor in the reference doc (anchors are <a id="..."> tags).
ANCHORS: dict[str, str] = {
    # plots
    "plot.target_timeseries": "plot.target_timeseries",
    "plot.reference_timeseries": "plot.reference_timeseries",
    "plot.model_comparison_curve": "plot.model_comparison_curve",
    "plot.selected_residuals_by_force": "plot.selected_residuals_by_force",
    "plot.model_comparison_residuals": "plot.model_comparison_residuals",
    "plot.model_metric_bars": "plot.model_metric_bars",
    "plot.model_likelihoods": "plot.model_likelihoods",
    "plot.robust_huber_weights": "plot.robust_huber_weights",
    "plot.hysteresis_up_down": "plot.hysteresis_up_down",
    # sections / fields
    "sec.summary": "sec.summary",
    "sec.reference_chain": "sec.reference_chain",
    "sec.events": "sec.events",
    "sec.static_fit": "sec.static_fit",
    "sec.accepted_holds": "sec.accepted_holds",
    "sec.holdout": "sec.holdout",
    "diag.hysteresis_deltas": "diag.hysteresis_deltas",
    "diag.creep_zero_return": "diag.creep_zero_return",
    "diag.dynamic_summary": "diag.dynamic_summary",
    "field.selection_likelihood": "field.selection_likelihood",
    "field.firmware_deployment_recommendation": "field.firmware_deployment_recommendation",
    "firmware.hx711_scale_offset": "firmware.hx711_scale_offset",
    "metric.cv": "metric.cv",
}

# one-line "what it is" per generated plot stem.
PLOT_SUMMARIES: dict[str, str] = {
    "target_timeseries": "Target sensor raw value over time during the session.",
    "reference_timeseries": "Reference force/raw value over time during the session.",
    "model_comparison_curve": (
        "Accepted calibration holds (points) with each deployable model's fitted "
        "curve mapping raw counts to force."
    ),
    "selected_residuals_by_force": (
        "Prediction error of the selected model at each force level "
        "(error = reference force - predicted force)."
    ),
    "model_comparison_residuals": "Prediction errors of all candidate models, overlaid.",
    "model_metric_bars": "Typical error (RMSE) and worst-case error per model, side by side.",
    "model_likelihoods": "Relative selection weight the policy assigned to each eligible model.",
    "robust_huber_weights": (
        "How much the robust fit trusted each hold (1.0 = full trust, lower = down-weighted "
        "as a likely outlier)."
    ),
    "hysteresis_up_down": (
        "Raw value when force was increasing vs decreasing, at each force level "
        "(overlap = good reversibility)."
    ),
}

# one-line "what it is" per report section, keyed by the section heading prefix.
SECTION_INTROS: dict[str, str] = {
    "1. Reference-chain verification summary": (
        "What it is: a health check on the raw target and reference streams before the "
        "data is trusted for fitting."
    ),
    "2. Static fit summary": (
        "What it is: aggregate quality of the accepted static holds that feed the fit."
    ),
    "3. Holdout accuracy summary": (
        "What it is: how the selected model performs on an independent session it was not "
        "trained on - the strongest deployment evidence."
    ),
    "4. Hysteresis / reversibility summary": (
        "What it is: whether the sensor reads the same at a given force when loading vs unloading."
    ),
    "5. Creep / zero-return summary": (
        "What it is: slow drift while a load is held, and whether the sensor returns to zero "
        "after unloading."
    ),
    "6. Dynamic validation summary": (
        "What it is: ramp/squeeze trials used to validate behavior - not used to fit the "
        "calibration coefficients."
    ),
    "7. Previous calibration comparison": (
        "What it is: how to compare this calibration against a previous one."
    ),
    "8. Firmware deployment recommendation": (
        "What it is: the overall go/no-go call on writing these constants to firmware."
    ),
    "Model candidate ranking": (
        "What it is: every model that was fitted, ranked by the selection policy, with its "
        "error metrics and any reasons it was rejected."
    ),
}


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _num(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def doc_link(concept: str, text: str = "reference") -> str:
    anchor = ANCHORS.get(concept)
    target = f"{DOC_REF}#{anchor}" if anchor else DOC_REF
    return f"[{text}]({target})"


def ref_block(concept: str, summary: str = "", interpretation: str = "") -> list[str]:
    """Uniform markdown block: what-it-is, interpretation, reference link."""
    lines: list[str] = []
    if summary:
        lines.append(f"> **What it is.** {summary}")
    if interpretation:
        lines.append(f">")
        lines.append(f"> **Interpretation.** {interpretation}")
    lines.append(f">")
    lines.append(f"> **More:** {doc_link(concept)}.")
    lines.append("")
    return lines


def _operating_range_N(metrics: dict[str, Any]) -> float | None:
    """Recover the configured operating range from absolute and percent error."""
    abs_err = _num(metrics.get("max_abs_error_N"))
    pct = _num(metrics.get("max_abs_error_percent_range"))
    if abs_err is not None and pct not in (None, 0.0):
        return 100.0 * abs_err / pct
    return None


# --------------------------------------------------------------------------- #
# metric / selection / holdout interpreters
# --------------------------------------------------------------------------- #
def interpret_metrics(fit: dict[str, Any]) -> list[str]:
    """Value-based verdicts on the selected-model fit metrics."""
    metrics = fit.get("metrics", {}) or {}
    cv = fit.get("cv_metrics", {}) or {}
    out: list[str] = []

    r2 = _num(metrics.get("r2"))
    if r2 is not None:
        pct = r2 * 100.0
        if r2 >= 0.999:
            verdict = "excellent linear agreement"
        elif r2 >= 0.99:
            verdict = "good agreement, but inspect residual plots for shape"
        elif r2 >= 0.95:
            verdict = "moderate - check for curvature or outliers"
        else:
            verdict = "poor - the model does not explain the data well"
        out.append(f"R² = {r2:.5g}: explains ~{pct:.2f}% of force variation ({verdict}).")

    rmse = _num(metrics.get("rmse_N"))
    rng = _operating_range_N(metrics)
    if rmse is not None:
        tail = f" (~{100.0 * rmse / rng:.2f}% of the operating range)" if rng else ""
        out.append(f"RMSE = {rmse:.4g} N: typical error on the training holds{tail}.")

    max_abs = _num(metrics.get("max_abs_error_N"))
    if max_abs is not None:
        out.append(f"Max abs error = {max_abs:.4g} N: worst single-hold error.")

    bias = _num(metrics.get("residual_bias_N"))
    if bias is not None:
        if abs(bias) < 1e-6:
            out.append("Residual bias ≈ 0 N: no systematic offset (expected for a fitted line).")
        else:
            direction = "low" if bias > 0 else "high"
            out.append(f"Residual bias = {bias:.3g} N: predictions run slightly {direction}.")

    cv_rmse = _num(cv.get("cv_rmse_N"))
    if cv_rmse is not None and rmse is not None:
        if rmse > 0 and cv_rmse > 3.0 * rmse:
            out.append(
                f"⚠ Cross-validated RMSE ({cv_rmse:.4g} N) is far above training RMSE "
                f"({rmse:.4g} N): sign of overfitting / unstable fit - do not trust the "
                "training error alone."
            )
        else:
            out.append(
                f"Cross-validated RMSE = {cv_rmse:.4g} N: error on held-out points is close to "
                "the training error, so the fit generalizes."
            )

    passes = fit.get("passes_residual_threshold")
    thr = _num(fit.get("residual_threshold_percent_range"))
    if passes is not None:
        max_pct = _num(metrics.get("max_abs_error_percent_range"))
        detail = (
            f" (worst error {max_pct:.2f}% vs {thr:.2f}% gate)"
            if (max_pct is not None and thr is not None)
            else ""
        )
        out.append(
            ("✓ Passes the residual-error gate" if passes else "✗ Fails the residual-error gate")
            + detail
            + "."
        )
    return out


def interpret_selection(fit: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    """Comment on how decisive the model choice was (rank-1 vs rank-2 margin)."""
    ranking = fit.get("model_ranking") or []
    eligible = [r for r in ranking if _num(r.get("selection_likelihood"))]
    eligible.sort(key=lambda r: _num(r.get("selection_likelihood")) or 0.0, reverse=True)
    selected = fit.get("selected_model_id") or fit.get("model") or "the selected model"
    if not eligible:
        return f"`{selected}` was selected; no comparable likelihoods were available."
    top = eligible[0]
    top_l = _num(top.get("selection_likelihood")) or 0.0
    if len(eligible) == 1:
        return f"`{top.get('model_id')}` was the only eligible model (likelihood {top_l:.2f})."
    second = eligible[1]
    margin = top_l - (_num(second.get("selection_likelihood")) or 0.0)
    if margin < 0.10:
        tone = (
            f"Thin margin ({margin:.2f}) over `{second.get('model_id')}`: the choice is nearly a "
            "tie - prefer the simplest adequate model and improve the protocol before adding "
            "firmware complexity."
        )
    else:
        tone = f"Clear lead ({margin:.2f}) over the runner-up `{second.get('model_id')}`."
    return f"`{top.get('model_id')}` won with likelihood {top_l:.2f}. {tone}"


def interpret_holdout(validation: dict[str, Any]) -> str:
    if not validation:
        return (
            "No independent holdout was validated for this session, so firmware constants are "
            "provisional. Run `handgrip-cal validate-holdout` to upgrade this evidence."
        )
    metrics = validation.get("metrics", {}) or {}
    thr = validation.get("thresholds", {}) or {}
    passes = validation.get("passes_holdout_gate")
    parts: list[str] = []
    checks = [
        ("rmse_N", "max_rmse_N", "RMSE"),
        ("max_abs_error_N", "max_abs_error_N", "max abs error"),
        ("bias_N", "max_bias_N", "bias"),
    ]
    for mkey, tkey, label in checks:
        val = _num(metrics.get(mkey))
        lim = _num(thr.get(tkey))
        if val is None:
            continue
        if lim is None:
            parts.append(f"{label} {val:.3g} N")
        else:
            mark = "✓" if abs(val) <= lim else "✗"
            parts.append(f"{mark} {label} {val:.3g} N (≤ {lim:g})")
    head = (
        "✓ Holdout gate PASSED on independent data"
        if passes
        else "✗ Holdout gate FAILED - investigate before deploying"
        if passes is not None
        else "Holdout metrics"
    )
    body = "; ".join(parts) if parts else "no comparable metrics"
    return f"{head}: {body}."


def interpret_stream_health(stream_table: pd.DataFrame) -> str:
    if stream_table is None or stream_table.empty:
        return "No stream-health table available."
    notes: list[str] = []
    for _, row in stream_table.iterrows():
        name = str(row.get("stream", "stream"))
        rate = _num(row.get("sample_rate_hz"))
        gap = _num(row.get("max_gap_s"))
        flags: list[str] = []
        if gap is not None and gap > 0.5:
            flags.append(f"large {gap:.2g}s gap")
        rate_txt = f"{rate:.1f} Hz" if rate is not None else "unknown rate"
        notes.append(f"{name}: {rate_txt}" + (f" ({', '.join(flags)})" if flags else " (continuous)"))
    healthy = "no major gaps" if all("gap" not in n for n in notes) else "gaps detected - inspect"
    return f"{'; '.join(notes)}. Acquisition looks {('healthy' if healthy.startswith('no') else 'suspect')}: {healthy}."


def interpret_event_completeness(counts_table: pd.DataFrame) -> str:
    if counts_table is None or counts_table.empty:
        return "No event-count table available."
    counts = {str(r["event"]): int(r["count"]) for _, r in counts_table.iterrows() if "event" in r}
    issues: list[str] = []
    for required in ("session_start", "session_end", "series_start", "series_end"):
        if counts.get(required, 0) < 1:
            issues.append(f"missing {required}")
    for a, b in (("hold_start", "hold_end"), ("baseline_start", "baseline_end")):
        if counts.get(a, 0) != counts.get(b, 0):
            issues.append(f"{a}/{b} mismatch ({counts.get(a, 0)}≠{counts.get(b, 0)})")
    holds = counts.get("hold_start", 0)
    if issues:
        return f"⚠ Protocol structure incomplete: {', '.join(issues)} - treat the report cautiously."
    return f"✓ Protocol structure looks complete ({holds} holds, matched start/end markers)."


def interpret_firmware(firmware: dict[str, Any]) -> str:
    if not firmware:
        return "No firmware constants were exported."
    ab = firmware.get("force_N_equals_a_raw_plus_b", {}) or {}
    a = _num(ab.get("a"))
    b = _num(ab.get("b"))
    hx = firmware.get("hx711_get_units_style_approximation", {}) or {}
    scale = _num(hx.get("scale"))
    offset = _num(hx.get("offset"))
    parts: list[str] = []
    if a is not None and b is not None:
        parts.append(f"direct form `force_N = {a:.6g}*raw + {b:.6g}`")
    if scale is not None and offset is not None:
        parts.append(f"HX711 form `force_N = (raw - {offset:.6g}) / {scale:.6g}`")
    caution = (
        " Verify the exact HX711 library semantics (tare/offset/sign/averaging order) before "
        "flashing - the two forms are equivalent only if the runtime applies them as written."
    )
    return ("Two equivalent encodings: " + "; ".join(parts) + "." + caution) if parts else (
        "Firmware constants exported." + caution
    )


def explain_rejection(reason: str) -> str:
    return {
        "diagnostic_only_model": "diagnostic model, excluded from deployment by design",
        "too_few_finite_predictions": "produced too few valid predictions to evaluate",
        "insufficient_cross_validation_coverage": "cross-validation could not cover enough points",
        "non_monotonic_prediction_over_calibrated_range": (
            "its curve is not monotonic across the calibrated range (would invert force readings)"
        ),
        "monotonicity_check_failed": "its monotonicity could not be verified",
        "fit_failed": "the fit did not converge / errored",
    }.get(reason, reason)


# --------------------------------------------------------------------------- #
# per-plot interpreter
# --------------------------------------------------------------------------- #
def interpret_plot(
    stem: str,
    fit: dict[str, Any],
    dataset: pd.DataFrame,
    candidates: list[dict[str, Any]],
) -> str:
    metrics = fit.get("metrics", {}) or {}
    selected = fit.get("selected_model_id") or fit.get("model") or "selected model"

    if stem in ("target_timeseries", "reference_timeseries"):
        return (
            "Scan for missing intervals, clipping/saturation, or drift while force should be "
            "steady. Stable holds should appear as flat plateaus."
        )
    if stem == "model_comparison_curve":
        return (
            f"If the candidate curves overlap, a straight line already fits and the simplest "
            f"model (`{selected}`) is justified. Diverging curves only matter where they are "
            "supported by points - not in gaps or at the ends."
        )
    if stem == "selected_residuals_by_force":
        max_abs = _num(metrics.get("max_abs_error_N"))
        tail = f" Worst residual here is {max_abs:.3g} N." if max_abs is not None else ""
        return (
            "Good residuals scatter randomly around zero with no trend across force. A curve or "
            "slope means the model shape is wrong; a single far point is an outlier." + tail
        )
    if stem == "model_comparison_residuals":
        return (
            "Use this to check whether a more complex model removes a *repeated* residual pattern "
            "across all force levels (real improvement) rather than just hugging one point."
        )
    if stem == "model_metric_bars":
        return (
            "Shorter bars are better. A model with marginally lower RMSE but many more parameters "
            "is usually not worth the firmware complexity."
        )
    if stem == "model_likelihoods":
        return interpret_selection(fit, candidates)
    if stem == "robust_huber_weights":
        weights: list[float] = []
        for c in candidates:
            if c.get("model_id") == "affine_huber":
                weights = [w for w in (c.get("parameters", {}) or {}).get("robust_weights", [])]
                break
        low = sum(1 for w in weights if _num(w) is not None and w < 0.99)
        if weights:
            if low == 0:
                return "All holds kept weight ≈ 1.0: no outliers; the robust fit matches OLS."
            return (
                f"{low} of {len(weights)} holds were down-weighted as possible outliers. A few is "
                "fine; many means protocol quality, not model choice, is the problem."
            )
        return "Shows which holds the robust fit down-weighted (1.0 = fully trusted)."
    if stem == "hysteresis_up_down":
        return (
            "Overlapping ascending/descending points mean good reversibility. Direction-separated "
            "clusters indicate mechanical hysteresis or fixture load-path effects - investigate "
            "before encoding direction-dependent behavior."
        )
    return ""
