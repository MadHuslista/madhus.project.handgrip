"""Unit tests for the report interpretation layer.

These cover the value-based verdicts and the report<->reference-doc anchor
contract, without requiring a full recording session.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from handgrip_calibration import report_interpretation as ri

_DOC = Path(__file__).resolve().parents[2] / "docs" / "calibration-report-reference.md"


def test_anchors_exist_in_reference_doc() -> None:
    """Every concept the report can deep-link to must exist as an anchor in the doc."""
    doc = _DOC.read_text(encoding="utf-8")
    present = set(re.findall(r'<a id="([^"]+)"></a>', doc))
    for concept, anchor in ri.ANCHORS.items():
        assert anchor in present, f"{concept} -> #{anchor} missing from reference doc"


def test_every_plot_has_a_summary_and_anchor() -> None:
    for stem in ri.PLOT_SUMMARIES:
        assert ri.PLOT_SUMMARIES[stem]
        assert f"plot.{stem}" in ri.ANCHORS


def test_interpret_metrics_flags_overfit_via_cv_gap() -> None:
    fit = {
        "metrics": {"rmse_N": 0.5, "max_abs_error_N": 0.8, "max_abs_error_percent_range": 1.6,
                    "r2": 0.999, "residual_bias_N": 0.0},
        "cv_metrics": {"cv_rmse_N": 14.6},
        "passes_residual_threshold": True,
        "residual_threshold_percent_range": 2.0,
    }
    notes = " ".join(ri.interpret_metrics(fit))
    assert "overfitting" in notes.lower()
    assert "R²" in notes


def test_interpret_metrics_handles_missing_and_nan() -> None:
    assert ri.interpret_metrics({}) == []
    weird = {"metrics": {"rmse_N": float("nan"), "r2": None}, "cv_metrics": {}}
    # must not raise and must not emit a bogus NaN verdict
    assert all("nan" not in n.lower() for n in ri.interpret_metrics(weird))


def test_interpret_selection_detects_thin_margin() -> None:
    fit = {
        "selected_model_id": "affine_ols",
        "model_ranking": [
            {"model_id": "affine_ols", "selection_likelihood": 0.35},
            {"model_id": "affine_wls", "selection_likelihood": 0.33},
        ],
    }
    assert "thin margin" in ri.interpret_selection(fit, []).lower()


def test_interpret_holdout_missing_and_pass() -> None:
    assert "provisional" in ri.interpret_holdout({}).lower()
    passing = {
        "metrics": {"rmse_N": 0.6, "max_abs_error_N": 0.9, "bias_N": -0.1},
        "thresholds": {"max_rmse_N": 5.0, "max_abs_error_N": 10.0, "max_bias_N": 2.0},
        "passes_holdout_gate": True,
    }
    assert "passed" in ri.interpret_holdout(passing).lower()


def test_interpret_event_completeness_detects_mismatch() -> None:
    counts = pd.DataFrame(
        {"event": ["session_start", "session_end", "series_start", "series_end",
                   "hold_start", "hold_end"],
         "count": [1, 1, 1, 1, 5, 4]}
    )
    assert "mismatch" in ri.interpret_event_completeness(counts).lower()


def test_ref_block_includes_link() -> None:
    block = "\n".join(ri.ref_block("plot.target_timeseries", summary="x", interpretation="y"))
    assert "What it is" in block and "Interpretation" in block
    assert ri.DOC_REF in block and "plot.target_timeseries" in block
