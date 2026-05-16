"""Integration tests for unprefixed Hydra CLI overrides in stage scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _write_capture_csv(path: Path, fs: float = 100.0, n: int = 1200) -> None:
    """Write a synthetic capture with one clear grip event."""
    rng = np.random.default_rng(17)
    t_us = (np.arange(n) / fs * 1e6).astype(int)
    y = rng.normal(scale=0.3, size=n)
    y[200:500] += 20.0
    df = pd.DataFrame({"device_clock_us": t_us, "target_raw_count": y})
    path.write_text(df.to_csv(index=False), encoding="utf-8")


def _run_stage(script_name: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    script_path = cwd / "scripts" / script_name
    cmd = [sys.executable, str(script_path), *args]
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def test_stage1_accepts_unprefixed_input_and_outdir(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    csv_path = tmp_path / "stage1.csv"
    outdir = tmp_path / "out_stage1"
    _write_capture_csv(csv_path)

    result = _run_stage(
        "stage1_startup_warmup.py",
        [
            "analysis=stage1",
            f"input={csv_path}",
            f"outdir={outdir}",
            "analysis.channel=raw",
        ],
        project_root,
    )

    assert result.returncode == 0, result.stderr
    assert (outdir / "summary.json").exists()


def test_stage4_accepts_unprefixed_inputs_and_outdir(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    csv_a = tmp_path / "stage4_a.csv"
    csv_b = tmp_path / "stage4_b.csv"
    outdir = tmp_path / "out_stage4"
    _write_capture_csv(csv_a)
    _write_capture_csv(csv_b)

    result = _run_stage(
        "stage4_grip_dynamics.py",
        [
            "analysis=stage4",
            f"inputs=[{csv_a},{csv_b}]",
            f"outdir={outdir}",
            "analysis.channel=raw",
        ],
        project_root,
    )

    assert result.returncode == 0, result.stderr
    assert (outdir / "event_metrics.csv").exists()


def test_stage1_missing_outdir_fails_with_clear_error(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    csv_path = tmp_path / "stage1_missing_out.csv"
    _write_capture_csv(csv_path)

    result = _run_stage(
        "stage1_startup_warmup.py",
        [
            "analysis=stage1",
            f"input={csv_path}",
            "analysis.channel=raw",
        ],
        project_root,
    )

    assert result.returncode != 0
    assert "Missing required argument: outdir=<value>" in result.stderr
