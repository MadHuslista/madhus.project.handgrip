"""Unit tests for handgrip_analysis.io."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from handgrip_analysis.io import (
    CaptureData,
    estimate_fs,
    load_capture,
    sampling_summary,
)


def _make_csv(
    n: int = 200,
    fs: float = 100.0,
    with_filtered: bool = False,
    with_current_units: bool = False,
    time_col: str = "device_clock_us",
) -> str:
    """Create a minimal in-memory CSV string."""
    t_us = (np.arange(n) / fs * 1e6).astype(int)
    y = np.random.default_rng(0).normal(size=n)
    data: dict = {time_col: t_us, "target_raw_count": y}
    if with_current_units:
        data["target_current_units"] = y * 1.1
    if with_filtered:
        data["target_filtered_units"] = y * 0.9
    return pd.DataFrame(data).to_csv(index=False)


# ---------------------------------------------------------------------------
# estimate_fs
# ---------------------------------------------------------------------------


def test_estimate_fs_exact():
    t = np.linspace(0, 1, 101)  # 0–1 s, 100 intervals → 100 Hz
    fs = estimate_fs(t)
    assert fs == pytest.approx(100.0, rel=1e-6)


def test_estimate_fs_too_short():
    assert math.isnan(estimate_fs(np.array([0.0])))


# ---------------------------------------------------------------------------
# sampling_summary
# ---------------------------------------------------------------------------


def test_sampling_summary_keys():
    t = np.linspace(0, 2, 201)
    s = sampling_summary(t)
    assert "n_samples" in s
    assert "fs_median_hz" in s
    assert "duration_s" in s


def test_sampling_summary_short():
    s = sampling_summary(np.array([0.0]))
    assert s["n_samples"] == 1
    assert s["duration_s"] == 0.0
    assert math.isnan(s["fs_median_hz"])


# ---------------------------------------------------------------------------
# load_capture
# ---------------------------------------------------------------------------


def test_load_capture_device_clock(tmp_path):
    csv_content = _make_csv(n=300, fs=100.0, time_col="device_clock_us")
    p = tmp_path / "cap.csv"
    p.write_text(csv_content)
    cap = load_capture(str(p), time_source="device")
    assert isinstance(cap, CaptureData)
    assert cap.fs_estimate_hz == pytest.approx(100.0, rel=0.05)
    assert cap.time_source == "device_clock_us"
    assert len(cap.time_s) == 300


def test_load_capture_auto_selects_device(tmp_path):
    csv_content = _make_csv(n=200, fs=50.0, time_col="device_clock_us")
    p = tmp_path / "cap.csv"
    p.write_text(csv_content)
    cap = load_capture(str(p), time_source="auto")
    assert cap.time_source == "device_clock_us"


def test_load_capture_series_raw(tmp_path):
    csv_content = _make_csv(n=100)
    p = tmp_path / "cap.csv"
    p.write_text(csv_content)
    cap = load_capture(str(p))
    y = cap.series("raw")
    assert y.shape == (100,)


def test_load_capture_series_filtered(tmp_path):
    csv_content = _make_csv(n=100, with_filtered=True)
    p = tmp_path / "cap.csv"
    p.write_text(csv_content)
    cap = load_capture(str(p))
    y_f = cap.series("filtered")
    assert y_f.shape == (100,)


def test_load_capture_series_current_units(tmp_path):
    csv_content = _make_csv(n=100, with_current_units=True)
    p = tmp_path / "cap.csv"
    p.write_text(csv_content)
    cap = load_capture(str(p))
    y_current = cap.series("current_units")
    assert y_current.shape == (100,)


def test_load_capture_no_current_units_column_raises(tmp_path):
    csv_content = _make_csv(n=100, with_current_units=False)
    p = tmp_path / "cap.csv"
    p.write_text(csv_content)
    cap = load_capture(str(p))
    with pytest.raises(KeyError, match="target_current_units"):
        cap.series("current_units")


def test_load_capture_no_filtered_column_raises(tmp_path):
    csv_content = _make_csv(n=100, with_filtered=False)
    p = tmp_path / "cap.csv"
    p.write_text(csv_content)
    cap = load_capture(str(p))
    with pytest.raises(KeyError, match="target_filtered_units"):
        cap.series("filtered")


def test_load_capture_missing_column_raises(tmp_path):
    df = pd.DataFrame({"device_clock_us": [0, 10000], "some_other_col": [1, 2]})
    p = tmp_path / "bad.csv"
    p.write_text(df.to_csv(index=False))
    with pytest.raises(ValueError, match="Missing required signal columns"):
        load_capture(str(p))


def test_load_capture_lsl_timestamp(tmp_path):
    n = 200
    t_s = np.arange(n) / 100.0 + 1_700_000_000.0  # Unix-like LSL timestamps
    df = pd.DataFrame({"lsl_timestamp_s": t_s, "target_raw_count": np.ones(n)})
    p = tmp_path / "lsl.csv"
    p.write_text(df.to_csv(index=False))
    cap = load_capture(str(p), time_source="lsl")
    assert cap.time_source == "lsl_timestamp_s"
    assert cap.time_s[0] == pytest.approx(0.0)


def test_load_capture_host_unix_ns(tmp_path):
    n = 150
    t_ns = (np.arange(n) / 50.0 * 1e9).astype(int)
    df = pd.DataFrame({"host_unix_time_ns": t_ns, "target_raw_count": np.zeros(n)})
    p = tmp_path / "host.csv"
    p.write_text(df.to_csv(index=False))
    cap = load_capture(str(p), time_source="host")
    assert cap.time_source == "host_unix_time_ns"
    assert cap.fs_estimate_hz == pytest.approx(50.0, rel=0.05)
