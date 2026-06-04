"""
Integration test: synthetic end-to-end pipeline.

Exercises the full load → DSP → filter chain with in-memory data,
verifying that all components compose correctly without file I/O
(except for a temporary CSV written to tmp_path).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from handgrip_analysis.dsp import (
    apply_filter_spec,
    best_event_metrics,
    detect_events,
    load_filter_specs,
)
from handgrip_analysis.io import load_capture, sampling_summary

FS = 100.0
N = 3000


def _make_grip_csv(tmp_path, n: int = N, fs: float = FS) -> str:
    """Write a synthetic grip-sensor CSV; return the path string."""
    rng = np.random.default_rng(99)
    t_us = (np.arange(n) / fs * 1e6).astype(int)
    y = rng.normal(scale=0.5, size=n)
    # Add a grip event at samples 500–1000
    y[500:1000] += 30.0
    df = pd.DataFrame({"device_clock_us": t_us, "target_raw_count": y})
    p = tmp_path / "grip.csv"
    p.write_text(df.to_csv(index=False))
    return str(p)


def test_load_real_new_standard_sample():
    project_root = Path(__file__).resolve().parents[2]
    sample = project_root / "data" / "calibration_signals" / "20260512_stage1_cold_start_trial02.csv"
    if not sample.exists():
        pytest.skip("Real 20260512 sample not available in this workspace")

    cap = load_capture(sample, time_source="auto")
    y = cap.series("raw")

    assert cap.time_source == "device_clock_us"
    assert y.size > 0
    assert np.all(np.isfinite(y))


def test_full_load_and_event_detection(tmp_path):
    p = _make_grip_csv(tmp_path)
    cap = load_capture(p, time_source="device")
    y = cap.series("raw")

    assert cap.fs_estimate_hz == pytest.approx(FS, rel=0.05)
    summary = sampling_summary(cap.time_s)
    assert summary["n_samples"] == N

    events = detect_events(y, cap.fs_estimate_hz)
    assert len(events) >= 1
    # The grip region (500–1000) should be detected
    grip_times = [cap.time_s[ev.peak_idx] for ev in events]
    assert any(4.5 <= t <= 11.0 for t in grip_times)


def test_filter_chain_on_real_load(tmp_path):
    p = _make_grip_csv(tmp_path)
    cap = load_capture(p, time_source="device")
    y = cap.series("raw")

    specs = [
        {"type": "butterworth_lowpass_2nd", "cutoff_hz": 12.0, "sample_rate_hz": cap.fs_estimate_hz},
        {"type": "lowpass_1pole", "cutoff_hz": 12.0},
        {"type": "identity"},
    ]
    for spec in specs:
        out = apply_filter_spec(y, cap.fs_estimate_hz, spec, time_s=cap.time_s)
        assert out.shape == y.shape, f"Shape mismatch for {spec['type']}"
        assert np.all(np.isfinite(out)), f"Non-finite output for {spec['type']}"


def test_best_event_metrics_pipeline(tmp_path):
    p = _make_grip_csv(tmp_path)
    cap = load_capture(p, time_source="device")
    y = cap.series("raw")

    m = best_event_metrics(y, cap.time_s, cap.fs_estimate_hz)
    assert m["n_events"] >= 1
    assert m["peak_value"] > 20.0
    assert np.isfinite(m["rise_10_90_s"])


def test_filter_spec_loading_with_production_types_only(tmp_path):
    """Active YAML filters must be directly deployable in LSL_Bridge."""
    candidates_yaml = tmp_path / "candidates.yaml"
    candidates_yaml.write_text(
        """
filters:
  - {name: identity, type: identity}
  - {name: lp8, type: butterworth_lowpass_2nd, cutoff_hz: 8.0, sample_rate_hz: 100.0}
  - {name: lp10, type: lowpass_1pole, cutoff_hz: 10.0}
"""
    )
    specs = load_filter_specs(str(candidates_yaml))
    assert len(specs) == 3

    rng = np.random.default_rng(7)
    y = rng.normal(size=1024)
    t = np.arange(len(y)) / FS
    for spec in specs:
        out = apply_filter_spec(y, FS, spec, time_s=t)
        assert out.shape == y.shape, f"Shape mismatch: {spec['name']}"
        assert np.all(np.isfinite(out)), f"Non-finite: {spec['name']}"


def test_filter_spec_loading_rejects_offline_active_candidates(tmp_path):
    candidates_yaml = tmp_path / "bad_candidates.yaml"
    candidates_yaml.write_text(
        """
filters:
  - {name: hp5, type: butter_highpass, cutoff_hz: 0.05}
"""
    )
    with pytest.raises(ValueError, match="not directly deployable"):
        load_filter_specs(str(candidates_yaml))



def test_stage6_accepts_current_units_channel(tmp_path):
    from handgrip_analysis.domain import StageConfig, TrialSpec
    from handgrip_analysis.stages.stage6_filters import analyze_trial

    rng = np.random.default_rng(123)
    t_us = (np.arange(N) / FS * 1e6).astype(int)
    force_n = rng.normal(scale=0.2, size=N)
    force_n[500:1000] += np.linspace(0.0, 40.0, 500)
    force_n[1000:1500] += 40.0
    csv_path = tmp_path / "dynamic_current_units.csv"
    pd.DataFrame(
        {
            "device_clock_us": t_us,
            "target_raw_count": force_n * 1000.0 + 800000.0,
            "target_current_units": force_n,
            "target_filtered_units": force_n * 0.5,
        }
    ).to_csv(csv_path, index=False)

    candidates_yaml = tmp_path / "candidates.yaml"
    candidates_yaml.write_text(
        """
filters:
  - {name: identity, type: identity}
  - {name: lp10, type: lowpass_1pole, cutoff_hz: 10.0}
""",
        encoding="utf-8",
    )
    spec = TrialSpec(
        stage="stage6",
        condition="fast_max",
        trial_type="dynamic",
        trial_id="trial01",
        session_id="s1",
        path=csv_path,
        channel="current_units",
    )
    cfg = StageConfig(stage="stage6", channel="current_units", filter_config=candidates_yaml)

    result = analyze_trial(spec, cfg)

    assert result.spec.channel == "current_units"
    filter_metrics = result.tables["filter_metrics"]
    assert set(filter_metrics["filter"]) == {"identity", "lp10"}
    assert np.isfinite(filter_metrics["peak_relative_error"]).any()
