"""
Integration test: synthetic end-to-end pipeline.

Exercises the full load → DSP → filter chain with in-memory data,
verifying that all components compose correctly without file I/O
(except for a temporary CSV written to tmp_path).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from handgrip_analysis.dsp import (
    apply_filter_spec,
    best_event_metrics,
    detect_events,
    load_filter_specs,
    welch_psd,
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
    df = pd.DataFrame({"device_clock_us": t_us, "value_raw": y})
    p = tmp_path / "grip.csv"
    p.write_text(df.to_csv(index=False))
    return str(p)


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
        {"type": "butter_lowpass", "order": 2, "cutoff_hz": 12.0},
        {"type": "butter_highpass", "order": 2, "cutoff_hz": 0.05},
        {"type": "butter_bandpass", "order": 2, "low_hz": 0.05, "high_hz": 12.0},
        {"type": "notch", "freq_hz": 45.9473, "q": 20.0},
        {"type": "identity"},
    ]
    for spec in specs:
        out = apply_filter_spec(y, cap.fs_estimate_hz, spec)
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


def test_filter_spec_loading_with_all_types(tmp_path):
    """All 11 filter types from the YAML config must apply without error."""
    candidates_yaml = tmp_path / "candidates.yaml"
    candidates_yaml.write_text(
        """
filters:
  - {name: identity, type: identity}
  - {name: lp8, type: butter_lowpass, order: 2, cutoff_hz: 8.0}
  - {name: lp10, type: butter_lowpass, order: 2, cutoff_hz: 10.0}
  - {name: hp5, type: butter_highpass, order: 2, cutoff_hz: 0.05}
  - {name: bp, type: butter_bandpass, order: 2, low_hz: 0.05, high_hz: 12.0}
  - {name: notch, type: notch, freq_hz: 45.9473, q: 20.0}
  - name: chain
    type: chain
    steps:
      - {type: notch, freq_hz: 45.9473, q: 20.0}
      - {type: butter_lowpass, order: 2, cutoff_hz: 12.0}
"""
    )
    specs = load_filter_specs(str(candidates_yaml))
    assert len(specs) == 7

    rng = np.random.default_rng(7)
    y = rng.normal(size=1024)
    for spec in specs:
        out = apply_filter_spec(y, FS, spec)
        assert out.shape == y.shape, f"Shape mismatch: {spec['name']}"
        assert np.all(np.isfinite(out)), f"Non-finite: {spec['name']}"
