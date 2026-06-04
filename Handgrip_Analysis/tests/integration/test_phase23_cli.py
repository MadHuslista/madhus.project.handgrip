from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from handgrip_analysis.cli import run_all_main, stage_main


def _write_capture(path: Path, fs: float = 100.0, n: int = 500) -> None:
    rng = np.random.default_rng(456)
    t_us = (np.arange(n) / fs * 1e6).astype(int)
    y = rng.normal(scale=0.1, size=n)
    pd.DataFrame({"device_clock_us": t_us, "target_raw_count": y}).to_csv(path, index=False)


def _write_manifest(path: Path, capture: Path) -> None:
    pd.DataFrame(
        {
            "stage": ["stage2"],
            "condition": ["rest"],
            "trial_type": ["rest"],
            "trial_id": ["trial01"],
            "session_id": ["s1"],
            "path": [capture.name],
        }
    ).to_csv(path, index=False)


def test_stage_cli_accepts_key_value_arguments(tmp_path):
    capture = tmp_path / "20260512_stage2_rest_trial01.csv"
    manifest = tmp_path / "manifest.csv"
    _write_capture(capture)
    _write_manifest(manifest, capture)
    outdir = tmp_path / "out"

    rc = stage_main(["stage=stage2", f"manifest={manifest}", f"outdir={outdir}"])

    assert rc == 0
    assert (outdir / "plan.json").exists()
    assert (outdir / "per_trial_metrics.csv").exists()
    assert (outdir / "condition_summary.csv").exists()
    assert (outdir / "summary.json").exists()
    assert (outdir / "figures" / "per_trial").is_dir()
    assert (outdir / "figures" / "aggregate").is_dir()
    assert list((outdir / "figures" / "per_trial").glob("*.png"))
    assert list((outdir / "figures" / "aggregate").glob("*.png"))


def test_run_all_cli_dispatches_package_pipeline(tmp_path):
    capture = tmp_path / "20260512_stage2_rest_trial01.csv"
    manifest = tmp_path / "manifest.csv"
    _write_capture(capture)
    _write_manifest(manifest, capture)
    outdir = tmp_path / "all"

    rc = run_all_main([f"manifest={manifest}", f"base_outdir={outdir}"])

    assert rc == 0
    assert (outdir / "stage2" / "plan.json").exists()
    assert (outdir / "stage2" / "summary.json").exists()
