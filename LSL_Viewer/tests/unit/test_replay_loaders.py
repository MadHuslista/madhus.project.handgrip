"""Unit tests for core.replay — pure functions and data-loading helpers."""
from __future__ import annotations

import math

import numpy as np

from lsl_viewer.core.replay import (
    normalize_common_timebases,
    window_from_replay,
)
from lsl_viewer.types import DualReplayData


def _make_replay_data(
    n_target: int = 100,
    n_reference: int = 500,
    target_rate_hz: float = 100.0,
    reference_rate_hz: float = 500.0,
) -> DualReplayData:
    target_ts = np.arange(n_target, dtype=np.float64) / target_rate_hz
    reference_ts = np.arange(n_reference, dtype=np.float64) / reference_rate_hz
    return DualReplayData(
        target_timestamps_s=target_ts,
        target_device_clock_us=target_ts * 1e6,
        target_raw=np.sin(target_ts),
        target_filtered=np.sin(target_ts) * 0.9,
        reference_timestamps_s=reference_ts,
        reference_clock_s=reference_ts,
        reference_raw=np.cos(reference_ts),
        source_name="fixture",
        source_type="test",
        target_labels=["device_clock_us", "target_raw_count", "target_filtered_units"],
        reference_labels=["reference_clock_s", "reference_force_N"],
    )


class TestNormalizeCommonTimebases:
    def test_shifts_to_zero(self):
        target_ts = np.array([5.0, 5.01, 5.02])
        reference_ts = np.array([5.005, 5.015])
        t_out, r_out = normalize_common_timebases(target_ts, reference_ts)
        assert math.isclose(float(t_out[0]), 0.0, abs_tol=1e-12)

    def test_empty_arrays(self):
        t_out, r_out = normalize_common_timebases(np.array([]), np.array([]))
        assert t_out.size == 0
        assert r_out.size == 0


class TestWindowFromReplay:
    def test_no_data_before_start(self):
        data = _make_replay_data()
        # elapsed_s < 0 → no data in window
        result = window_from_replay(data, elapsed_s=-1.0, window_seconds=5.0)
        assert result is None

    def test_early_window_contains_data(self):
        data = _make_replay_data()
        result = window_from_replay(data, elapsed_s=0.5, window_seconds=0.5)
        assert result is not None
        assert result.target is not None
        assert result.reference is not None
        assert np.all(result.target.timestamps_s <= 0.5)
        assert np.all(result.target.timestamps_s >= 0.0)

    def test_mid_window_slices_correctly(self):
        data = _make_replay_data()
        window_s = 0.1
        elapsed_s = 0.5
        result = window_from_replay(data, elapsed_s=elapsed_s, window_seconds=window_s)
        assert result is not None
        t = result.target
        assert t is not None
        assert np.all(t.timestamps_s >= elapsed_s - window_s - 1e-9)
        assert np.all(t.timestamps_s <= elapsed_s + 1e-9)

    def test_duration_property(self):
        data = _make_replay_data(n_target=100, n_reference=500)
        # Last timestamp of reference: 499/500 = 0.998 s
        # Last timestamp of target: 99/100 = 0.99 s
        # Duration should be max = 0.998 s
        assert math.isclose(data.duration_s, 499.0 / 500.0, rel_tol=1e-6)
