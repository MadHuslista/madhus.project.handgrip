from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from handgrip_analysis.manifest import load_manifest, normalize_manifest_frame, validate_manifest_frame
from handgrip_analysis.pipeline import run_manifest_analysis
from handgrip_analysis.uncertainty import bootstrap_ci, robust_summary


def _write_capture(path: Path, fs: float = 100.0, n: int = 500) -> None:
    rng = np.random.default_rng(123)
    t_us = (np.arange(n) / fs * 1e6).astype(int)
    y = rng.normal(scale=0.1, size=n)
    pd.DataFrame({"device_clock_us": t_us, "target_raw_count": y}).to_csv(path, index=False)


def test_manifest_normalization_infers_filename_fields(tmp_path):
    capture = tmp_path / "20260512_stage2_rest_after_warmup_trial02.csv"
    _write_capture(capture)
    raw = pd.DataFrame({"path": [capture.name], "label": ["legacy_label"]})

    frame = normalize_manifest_frame(raw, base_dir=tmp_path)
    issues = validate_manifest_frame(frame)

    assert not [issue for issue in issues if issue.severity == "error"]
    assert frame.loc[0, "stage"] == "stage2"
    assert frame.loc[0, "condition"] == "rest_after_warmup"
    assert frame.loc[0, "trial_id"] == "trial02"
    assert frame.loc[0, "session_id"] == "20260512"


def test_load_manifest_filters_excluded_rows(tmp_path):
    capture_a = tmp_path / "20260512_stage1_cold_start_trial01.csv"
    capture_b = tmp_path / "20260512_stage1_cold_start_trial02.csv"
    _write_capture(capture_a)
    _write_capture(capture_b)
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        {
            "stage": ["stage1", "stage1"],
            "condition": ["cold_start", "cold_start"],
            "trial_type": ["warmup", "warmup"],
            "trial_id": ["trial01", "trial02"],
            "session_id": ["s1", "s1"],
            "path": [capture_a.name, capture_b.name],
            "include": [True, False],
        }
    ).to_csv(manifest, index=False)

    trials = load_manifest(manifest)

    assert len(trials) == 1
    assert trials[0].trial_id == "trial01"


def test_phase1_pipeline_writes_standard_outputs(tmp_path):
    capture_a = tmp_path / "20260512_stage1_cold_start_trial01.csv"
    capture_b = tmp_path / "20260513_stage1_cold_start_trial02.csv"
    _write_capture(capture_a, n=1000)
    _write_capture(capture_b, n=1000)
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        {
            "stage": ["stage1", "stage1"],
            "condition": ["cold_start", "cold_start"],
            "trial_type": ["warmup", "warmup"],
            "trial_id": ["trial01", "trial02"],
            "session_id": ["s1", "s2"],
            "path": [capture_a.name, capture_b.name],
        }
    ).to_csv(manifest, index=False)

    outdir = tmp_path / "out"
    paths = run_manifest_analysis(manifest_path=manifest, stage="stage1", outdir=outdir)

    assert paths["plan"].exists()
    assert paths["per_trial_metrics"].exists()
    assert paths["condition_summary"].exists()
    assert paths["summary"].exists()
    assert pd.read_csv(paths["per_trial_metrics"]).shape[0] == 2
    assert pd.read_csv(paths["condition_summary"]).loc[0, "n_trials"] == 2


def test_uncertainty_helpers_handle_small_n():
    summary = robust_summary([1.0, 2.0, 100.0])
    ci_low, ci_high = bootstrap_ci([1.0], statistic="median")

    assert summary["median"] == 2.0
    assert ci_low == ci_high == 1.0


def test_phase3_pipeline_writes_standard_directories(tmp_path):
    capture = tmp_path / "20260512_stage1_cold_start_trial01.csv"
    _write_capture(capture, n=1000)
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(
        {
            "stage": ["stage1"],
            "condition": ["cold_start"],
            "trial_type": ["warmup"],
            "trial_id": ["trial01"],
            "session_id": ["s1"],
            "path": [capture.name],
        }
    ).to_csv(manifest, index=False)

    outdir = tmp_path / "out"
    paths = run_manifest_analysis(manifest_path=manifest, stage="stage1", outdir=outdir)

    assert paths["plan"].name == "plan.json"
    assert (outdir / "figures" / "per_trial").is_dir()
    assert (outdir / "figures" / "aggregate").is_dir()
    assert (outdir / "figures" / "per_trial" / "README.md").exists()
    assert list((outdir / "figures" / "per_trial").glob("*.png"))
    assert list((outdir / "figures" / "aggregate").glob("*.png"))
    assert (outdir / "summary.json").exists()
