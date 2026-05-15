"""Unit tests for viz.state — pure axis-limit helpers."""
from __future__ import annotations

import math

import numpy as np
import pytest

from lsl_viewer.viz.state import compute_axis_limits, update_xy_span


class TestComputeAxisLimits:
    def test_returns_none_for_empty_array(self):
        result = compute_axis_limits(np.array([]), np.array([]))
        assert result is None

    def test_returns_none_when_all_nan(self):
        result = compute_axis_limits(
            np.array([float("nan")]), np.array([float("nan")])
        )
        assert result is None

    def test_uniform_data_adds_span(self):
        # Single-value data → should add a span so limits aren't degenerate
        result = compute_axis_limits(np.array([5.0]), np.array([3.0]))
        assert result is not None
        xmin, xmax, ymin, ymax = result
        assert xmin < 5.0 < xmax
        assert ymin < 3.0 < ymax

    def test_symmetric_margin_applied(self):
        x = np.array([0.0, 10.0])
        y = np.array([0.0, 100.0])
        result = compute_axis_limits(x, y, margin_ratio=0.1)
        assert result is not None
        xmin, xmax, ymin, ymax = result
        assert math.isclose(xmin, -1.0, rel_tol=1e-6)
        assert math.isclose(xmax, 11.0, rel_tol=1e-6)
        assert math.isclose(ymin, -10.0, rel_tol=1e-6)
        assert math.isclose(ymax, 110.0, rel_tol=1e-6)

    def test_ignores_non_finite_pairs(self):
        # inf/nan pairs should be excluded
        x = np.array([0.0, float("nan"), 10.0, float("inf")])
        y = np.array([0.0, 5.0, 100.0, 50.0])
        result = compute_axis_limits(x, y)
        assert result is not None
        # Only finite pair (0, 0) and (10, 100) are considered
        xmin, xmax, ymin, ymax = result
        assert xmin < 0.0
        assert xmax > 10.0


class TestUpdateXyMaxSpan:
    def test_empty_span_returns_data_limits(self):
        x = np.array([1.0, 5.0])
        y = np.array([2.0, 8.0])
        result = update_xy_span({}, x, y, margin_ratio=0.0)
        assert result["xmin"] == pytest.approx(1.0)
        assert result["xmax"] == pytest.approx(5.0)
        assert result["ymin"] == pytest.approx(2.0)
        assert result["ymax"] == pytest.approx(8.0)

    def test_existing_span_only_expands(self):
        x = np.array([2.0, 4.0])
        y = np.array([3.0, 6.0])
        existing = {"xmin": 0.0, "xmax": 10.0, "ymin": 0.0, "ymax": 20.0}
        result = update_xy_span(existing, x, y, margin_ratio=0.0)
        # Existing span is larger — should be preserved
        assert result["xmin"] == pytest.approx(0.0)
        assert result["xmax"] == pytest.approx(10.0)
        assert result["ymin"] == pytest.approx(0.0)
        assert result["ymax"] == pytest.approx(20.0)

    def test_new_data_outside_existing_expands(self):
        x = np.array([-5.0, 15.0])
        y = np.array([-10.0, 25.0])
        existing = {"xmin": 0.0, "xmax": 10.0, "ymin": 0.0, "ymax": 20.0}
        result = update_xy_span(existing, x, y, margin_ratio=0.0)
        assert result["xmin"] == pytest.approx(-5.0)
        assert result["xmax"] == pytest.approx(15.0)
        assert result["ymin"] == pytest.approx(-10.0)
        assert result["ymax"] == pytest.approx(25.0)

    def test_does_not_mutate_input_dict(self):
        original = {"xmin": 0.0, "xmax": 10.0, "ymin": 0.0, "ymax": 10.0}
        original_copy = dict(original)
        update_xy_span(original, np.array([5.0]), np.array([5.0]))
        assert original == original_copy


class TestViewerState:
    def test_to_handles_state_returns_correct_keys(self):
        from lsl_viewer.types import ViewerState

        state = ViewerState(
            xy_reference_time_shift_s=1.5,
            xy_reference_tail_delta_s=0.3,
            xy_reference_shift_clipped=True,
        )
        d = state.to_handles_state()
        assert d["xy_reference_time_shift_s"] == pytest.approx(1.5)
        assert d["xy_reference_tail_delta_s"] == pytest.approx(0.3)
        assert d["xy_reference_shift_clipped"] is True

    def test_sync_from_handles_state_updates_fields(self):
        from lsl_viewer.types import ViewerState

        state = ViewerState()
        d = {
            "xy_reference_time_shift_s": 2.0,
            "xy_reference_tail_delta_s": 0.5,
            "xy_reference_shift_clipped": True,
        }
        state.sync_from_handles_state(d)
        assert state.xy_reference_time_shift_s == pytest.approx(2.0)
        assert state.xy_reference_tail_delta_s == pytest.approx(0.5)
        assert state.xy_reference_shift_clipped is True

    def test_round_trip_handles_proxy_does_not_lose_data(self):
        """Verify the FigureHandles adapter pattern used in charts.py."""
        from lsl_viewer.types import ViewerState

        state = ViewerState(
            xy_reference_time_shift_s=0.25,
            xy_reference_tail_delta_s=0.1,
            xy_reference_shift_clipped=False,
        )
        proxy_state = state.to_handles_state()
        # Simulate mutation by core/alignment (sets a new shift)
        proxy_state["xy_reference_time_shift_s"] = 0.30
        state.sync_from_handles_state(proxy_state)
        assert state.xy_reference_time_shift_s == pytest.approx(0.30)
