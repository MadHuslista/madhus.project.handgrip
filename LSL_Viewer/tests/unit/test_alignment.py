"""Unit tests for core.alignment — pure functions, zero mocking."""
from __future__ import annotations

import numpy as np

from lsl_viewer.core.alignment import interpolate_reference_to_target
from lsl_viewer.types import FigureHandles, ReferenceWindow, TargetWindow


def _make_handles() -> FigureHandles:
    """Construct a minimal FigureHandles with just the state dict populated."""
    return FigureHandles(fig=None, axes={}, artists={}, state={})


def _make_target(n: int = 50, rate_hz: float = 100.0) -> TargetWindow:
    ts = np.arange(n, dtype=np.float64) / rate_hz
    return TargetWindow(
        timestamps_s=ts,
        device_clock_us=ts * 1e6,
        raw=np.sin(ts * 2 * np.pi),
        filtered=np.sin(ts * 2 * np.pi) * 0.9,
    )


def _make_reference(n: int = 250, rate_hz: float = 500.0) -> ReferenceWindow:
    ts = np.arange(n, dtype=np.float64) / rate_hz
    return ReferenceWindow(
        timestamps_s=ts,
        rs485_clock=ts,
        raw=np.cos(ts * 2 * np.pi) * 2.0,
    )


class TestInterpolateReferenceToTarget:
    def test_returns_empty_for_none_inputs(self):
        x, y, t = interpolate_reference_to_target(None, None, max_reference_gap_s=0.02)
        assert x.size == y.size == t.size == 0

    def test_returns_empty_when_reference_too_short(self):
        target = _make_target()
        ref_short = ReferenceWindow(
            timestamps_s=np.array([0.0]),
            rs485_clock=np.array([0.0]),
            raw=np.array([1.0]),
        )
        x, y, t = interpolate_reference_to_target(target, ref_short, max_reference_gap_s=0.02)
        assert x.size == 0

    def test_aligned_streams_produce_paired_output(self):
        target = _make_target(n=50)
        reference = _make_reference(n=250)
        x, y, t = interpolate_reference_to_target(
            target, reference, max_reference_gap_s=0.005
        )
        assert x.size > 0
        assert x.size == y.size == t.size
        # x values should be within reference.raw range
        assert np.all(np.abs(x) <= 2.5)

    def test_gap_rejection_excludes_sparse_reference(self):
        # Target from 1.0 s to 1.19 s — sits entirely in the gap between ref[0]=0.0 and ref[1]=10.0
        target_ts = np.arange(20, dtype=np.float64) / 100.0 + 1.0  # 1.00 .. 1.19 s
        target = TargetWindow(
            timestamps_s=target_ts,
            device_clock_us=target_ts * 1e6,
            raw=np.sin(target_ts),
            filtered=np.sin(target_ts) * 0.9,
        )
        # Reference points far apart (10 s gap); nearest reference to any target point ≫ 0.005 s
        ref_sparse = ReferenceWindow(
            timestamps_s=np.array([0.0, 10.0, 20.0]),
            rs485_clock=np.array([0.0, 10.0, 20.0]),
            raw=np.array([1.0, 2.0, 3.0]),
        )
        x, y, t = interpolate_reference_to_target(
            target, ref_sparse, max_reference_gap_s=0.005
        )
        assert x.size == 0, "All target points should be rejected — reference gaps too large"

    def test_time_shift_offsets_reference(self):
        target = _make_target(n=50)
        reference = _make_reference(n=250)
        # Without shift: normal pairing
        x_no_shift, _, _ = interpolate_reference_to_target(
            target, reference, max_reference_gap_s=0.005, reference_time_shift_s=0.0
        )
        # With a large shift that pushes reference outside target window → no pairs
        x_large_shift, _, _ = interpolate_reference_to_target(
            target, reference, max_reference_gap_s=0.005, reference_time_shift_s=100.0
        )
        assert x_no_shift.size > 0
        assert x_large_shift.size == 0

    def test_filtered_signal_differs_from_raw(self):
        target = _make_target(n=50)
        reference = _make_reference(n=250)
        _, y_raw, _ = interpolate_reference_to_target(
            target, reference, max_reference_gap_s=0.005, target_signal="raw"
        )
        _, y_filt, _ = interpolate_reference_to_target(
            target, reference, max_reference_gap_s=0.005, target_signal="filtered"
        )
        # filtered = raw * 0.9 in the fixture, so they differ
        assert not np.allclose(y_raw, y_filt)
