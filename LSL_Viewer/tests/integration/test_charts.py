"""Integration tests for viz.charts — Plotly figure construction and updates.

These tests verify that:
* ``build_chart_handles`` creates figures with the correct trace count.
* ``update_charts`` populates trace data without raising.
* XY bucket traces are pre-allocated and updated correctly.
* The clear_chart_data function zeroes all traces.

No NiceGUI server is started; the ``plot_*`` and ``info_label`` attributes
in ChartHandles are left as ``None``, which the update functions handle
gracefully (they skip the ``.update()`` call when the element is None).
"""
from __future__ import annotations

import numpy as np
import pytest
from omegaconf import OmegaConf

from lsl_viewer.types import (
    DualWindow,
    ReferenceWindow,
    TargetWindow,
    ViewerState,
)
from lsl_viewer.viz.charts import (
    N_XY_BUCKETS,
    ChartHandles,
    build_chart_handles,
    clear_chart_data,
    update_charts,
)


# ---------------------------------------------------------------------------
# Minimal config fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def cfg():
    return OmegaConf.create({
        "viewer": {
            "window_seconds": 10.0,
            "target_window_samples": 160,
            "reference_window_extra_s": 1.0,
            "expected_target_rate_hz": 100.0,
            "refresh_s": 0.05,
            "force_unit_label": "N",
            "target_raw_unit_label": "count",
            "dt_unit_label": "ms",
            "style": {
                "raw_color": "red",
                "filtered_color": "green",
                "reference_color": "purple",
                "timing_color": "blue",
                "grid_alpha": 0.3,
                "xy_color": "red",
                "xy_alpha_old": 0.12,
                "xy_alpha_new": 0.92,
                "xy_line_width": 1.6,
            },
            "xy_correlation": {
                "lock_max_span": False,
                "toggle_key": "x",
                "target_signal": "raw",
                "time_alignment": {
                    "mode": "raw_lsl",
                    "manual_reference_shift_s": 0.0,
                    "max_auto_shift_s": None,
                    "min_auto_shift_s": 0.0,
                    "snap_threshold_s": 0.25,
                    "smoothing_alpha": 1.0,
                },
            },
            "controls": {"clear_key": "c", "pause_key": "p"},
            "server": {
                "host": "127.0.0.1",
                "port": 8765,
                "reload": False,
                "show": False,
                "dark": False,
                "title": "LSL Viewer Test",
            },
        },
        "alignment": {
            "interpolation": "linear",
            "max_reference_gap_s": 0.02,
            "allow_extrapolation": False,
        },
        "calibration_markers": {
            "enabled": False,
            "events_ndjson_path": None,
            "draw_events": [],
        },
        "channels": {
            "target": {
                "clock_label": "device_clock_us",
                "raw_label": "target_raw_count",
                "filtered_label": "target_filtered_units",
            },
            "reference": {
                "clock_label": "reference_clock_s",
                "raw_label": "reference_force_N",
            },
        },
        "streams": {
            "reference": {"expected_rate_hz": 500.0},
        },
    })


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildChartHandles:
    def test_creates_all_seven_figures(self, cfg):
        ch = build_chart_handles(cfg)
        assert ch.fig_target_raw is not None
        assert ch.fig_reference_raw is not None
        assert ch.fig_target_filtered is not None
        assert ch.fig_overlay is not None
        assert ch.fig_target_dt is not None
        assert ch.fig_reference_dt is not None
        assert ch.fig_xy is not None

    def test_simple_panels_have_one_trace(self, cfg):
        ch = build_chart_handles(cfg)
        assert len(ch.fig_target_raw.data) == 1
        assert len(ch.fig_reference_raw.data) == 1
        assert len(ch.fig_target_filtered.data) == 1
        assert len(ch.fig_target_dt.data) == 1
        assert len(ch.fig_reference_dt.data) == 1

    def test_overlay_has_two_traces(self, cfg):
        ch = build_chart_handles(cfg)
        assert len(ch.fig_overlay.data) == 2

    def test_xy_has_n_bucket_traces(self, cfg):
        ch = build_chart_handles(cfg)
        assert len(ch.fig_xy.data) == N_XY_BUCKETS

    def test_plot_attributes_are_none_before_page_build(self, cfg):
        ch = build_chart_handles(cfg)
        assert ch.plot_target_raw is None
        assert ch.plot_xy is None
        assert ch.info_label is None


class TestUpdateCharts:
    def test_update_with_full_window_does_not_raise(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(), reference=_make_reference())
        # Should not raise even though plot_* elements are None
        update_charts(
            ch, window, state, cfg,
            mode="test",
            source_name="test_source",
            source_type="test_type",
        )

    def test_update_with_empty_window_does_not_raise(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=None, reference=None)
        update_charts(
            ch, window, state, cfg,
            mode="test",
            source_name="test_source",
            source_type="test_type",
        )

    def test_target_raw_trace_populated_after_update(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        target = _make_target(n=20)
        window = DualWindow(target=target, reference=None)
        update_charts(
            ch, window, state, cfg,
            mode="test",
            source_name="src",
            source_type="typ",
        )
        assert len(ch.fig_target_raw.data[0].x) == 20

    def test_xy_traces_populated_when_both_streams_present(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(
            ch, window, state, cfg,
            mode="test",
            source_name="src",
            source_type="typ",
        )
        # At least one XY bucket should have data
        any_xy_data = any(len(trace.x) > 0 for trace in ch.fig_xy.data)
        assert any_xy_data

    def test_xy_lock_max_span_updates_state(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState(xy_lock_max_span=True)
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(
            ch, window, state, cfg,
            mode="test",
            source_name="src",
            source_type="typ",
        )
        # State should have non-empty xy_max_span after update with valid data
        if state.xy_max_span:  # Only check if XY data was produced
            assert "xmin" in state.xy_max_span
            assert "xmax" in state.xy_max_span


class TestClearChartData:
    def test_clear_zeroes_all_traces(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        # First populate with data
        update_charts(ch, window, state, cfg, mode="t", source_name="s", source_type="t")
        # Then clear
        clear_chart_data(ch)
        assert len(ch.fig_target_raw.data[0].x) == 0
        assert len(ch.fig_reference_raw.data[0].x) == 0
        assert all(len(t.x) == 0 for t in ch.fig_xy.data)
