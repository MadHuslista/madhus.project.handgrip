"""
Integration tests for viz.charts — ECharts option construction and updates.

Tests verify that:
* ``build_chart_handles`` creates option dicts with the correct series counts.
* ``update_charts`` populates series data without raising.
* XY bucket series are pre-allocated (N_XY_BUCKETS) and populated on update.
* ``clear_chart_data`` zeroes all series.
* Marker lines are attached / removed correctly.
* XY lock-max-span updates ViewerState.

No NiceGUI server is started; ``chart_*`` and ``info_label`` attributes in
ChartHandles remain ``None``, which the update functions handle gracefully
(the ``.update()`` call is skipped when the element is ``None``).
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
    bind_chart_element,
    build_chart_handles,
    clear_chart_data,
    downsample_for_render,
    downsample_xy_for_render,
    update_charts,
)

# ---------------------------------------------------------------------------
# Minimal config fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def cfg():
    return OmegaConf.create(
        {
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
                "render": {
                    "max_points_time_series": 1200,
                    "max_points_xy": 1500,
                },
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
        }
    )


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


def _series_data(opts: dict, idx: int = 0) -> list:
    return opts["series"][idx]["data"]


class FakeEChart:
    """Minimal NiceGUI EChart test double with explicit option ownership."""

    def __init__(self, options: dict):
        self.options = options
        self.update_calls = 0

    def update(self) -> None:
        self.update_calls += 1


def _bind_all_fake_charts(ch: ChartHandles) -> list[FakeEChart]:
    bindings = (
        ("opts_target_raw", "chart_target_raw"),
        ("opts_reference_raw", "chart_reference_raw"),
        ("opts_target_filtered", "chart_target_filtered"),
        ("opts_overlay", "chart_overlay"),
        ("opts_target_dt", "chart_target_dt"),
        ("opts_reference_dt", "chart_reference_dt"),
        ("opts_xy", "chart_xy"),
    )
    charts: list[FakeEChart] = []
    for options_attr, chart_attr in bindings:
        fake = FakeEChart(getattr(ch, options_attr))
        bind_chart_element(ch, options_attr=options_attr, chart_attr=chart_attr, chart_el=fake)
        charts.append(fake)
    return charts


# ---------------------------------------------------------------------------
# TestBuildChartHandles
# ---------------------------------------------------------------------------


class TestBuildChartHandles:
    def test_creates_all_seven_option_dicts(self, cfg):
        ch = build_chart_handles(cfg)
        for attr in (
            "opts_target_raw",
            "opts_reference_raw",
            "opts_target_filtered",
            "opts_overlay",
            "opts_target_dt",
            "opts_reference_dt",
            "opts_xy",
        ):
            assert getattr(ch, attr) is not None, f"Missing: {attr}"

    def test_single_series_time_panels(self, cfg):
        ch = build_chart_handles(cfg)
        for opts in (
            ch.opts_target_raw,
            ch.opts_reference_raw,
            ch.opts_target_filtered,
            ch.opts_target_dt,
            ch.opts_reference_dt,
        ):
            assert len(opts["series"]) == 1

    def test_overlay_has_two_series(self, cfg):
        ch = build_chart_handles(cfg)
        assert len(ch.opts_overlay["series"]) == 2

    def test_xy_has_n_bucket_series(self, cfg):
        ch = build_chart_handles(cfg)
        assert len(ch.opts_xy["series"]) == N_XY_BUCKETS

    def test_all_series_start_empty(self, cfg):
        ch = build_chart_handles(cfg)
        for opts in (
            ch.opts_target_raw,
            ch.opts_reference_raw,
            ch.opts_target_filtered,
            ch.opts_target_dt,
            ch.opts_reference_dt,
        ):
            assert _series_data(opts) == []
        assert all(_series_data(ch.opts_xy, i) == [] for i in range(N_XY_BUCKETS))

    def test_chart_attrs_none_before_page_build(self, cfg):
        ch = build_chart_handles(cfg)
        for attr in (
            "chart_target_raw",
            "chart_reference_raw",
            "chart_target_filtered",
            "chart_overlay",
            "chart_target_dt",
            "chart_reference_dt",
            "chart_xy",
            "info_label",
        ):
            assert getattr(ch, attr) is None, f"Expected None: {attr}"

    def test_animation_disabled_on_all_series(self, cfg):
        ch = build_chart_handles(cfg)
        for opts in (
            ch.opts_target_raw,
            ch.opts_reference_raw,
            ch.opts_target_filtered,
            ch.opts_overlay,
            ch.opts_target_dt,
            ch.opts_reference_dt,
        ):
            assert opts.get("animation") is False
            for s in opts["series"]:
                assert s.get("animation") is False

    def test_large_mode_disabled_on_all_series(self, cfg):
        ch = build_chart_handles(cfg)
        for opts in (
            ch.opts_target_raw,
            ch.opts_reference_raw,
            ch.opts_target_filtered,
            ch.opts_overlay,
            ch.opts_target_dt,
            ch.opts_reference_dt,
            ch.opts_xy,
        ):
            for s in opts["series"]:
                assert "large" not in s

    def test_xy_series_are_scatter_buckets(self, cfg):
        ch = build_chart_handles(cfg)
        for s in ch.opts_xy["series"]:
            assert s["type"] == "scatter"
            assert "itemStyle" in s


# ---------------------------------------------------------------------------
# TestRenderBudgeting
# ---------------------------------------------------------------------------


class TestRenderBudgeting:
    def test_downsample_for_render_limits_time_series_without_mutating(self):
        x = np.arange(100, dtype=np.float64)
        y = x * 2

        out_x, out_y = downsample_for_render(x, y, max_points=10)

        assert len(out_x) == 10
        assert len(out_y) == 10
        assert out_x[0] == pytest.approx(0.0)
        assert out_x[-1] == pytest.approx(99.0)
        assert len(x) == 100

    def test_downsample_xy_for_render_limits_all_three_arrays(self):
        x = np.arange(100, dtype=np.float64)
        y = x * 2
        t = x / 100

        out_x, out_y, out_t = downsample_xy_for_render(x, y, t, max_points=12)

        assert len(out_x) == len(out_y) == len(out_t) == 12
        assert out_x[0] == pytest.approx(0.0)
        assert out_x[-1] == pytest.approx(99.0)

    def test_update_charts_applies_time_series_render_budget(self, cfg):
        cfg.viewer.render.max_points_time_series = 10
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=50), reference=None)

        update_charts(ch, window, state, cfg, mode="test", source_name="src", source_type="typ")

        assert len(_series_data(ch.opts_target_raw)) == 10

    def test_update_charts_applies_xy_render_budget(self, cfg):
        cfg.viewer.render.max_points_xy = 11
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=80), reference=_make_reference(n=400))

        update_charts(ch, window, state, cfg, mode="test", source_name="src", source_type="typ")

        xy_point_count = sum(len(_series_data(ch.opts_xy, i)) for i in range(N_XY_BUCKETS))
        assert xy_point_count <= 11


# ---------------------------------------------------------------------------
# TestEChartSinkBinding
# ---------------------------------------------------------------------------


class TestEChartSinkBinding:
    def test_bind_chart_element_rebinds_options_to_element_owner(self, cfg):
        ch = build_chart_handles(cfg)
        original = ch.opts_target_raw
        owned = {**original, "series": original["series"]}
        fake = FakeEChart(owned)

        returned = bind_chart_element(ch, options_attr="opts_target_raw", chart_attr="chart_target_raw", chart_el=fake)

        assert returned is fake
        assert ch.chart_target_raw is fake
        assert ch.opts_target_raw is fake.options

    def test_update_charts_pushes_to_bound_echart_elements(self, cfg):
        ch = build_chart_handles(cfg)
        charts = _bind_all_fake_charts(ch)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=20), reference=_make_reference(n=100))

        update_charts(ch, window, state, cfg, mode="test", source_name="src", source_type="typ")

        assert len(ch.chart_target_raw.options["series"][0]["data"]) == 20
        assert all(fake.update_calls == 1 for fake in charts)

    def test_clear_chart_data_pushes_to_bound_echart_elements(self, cfg):
        ch = build_chart_handles(cfg)
        charts = _bind_all_fake_charts(ch)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=20), reference=_make_reference(n=100))
        update_charts(ch, window, state, cfg, mode="test", source_name="src", source_type="typ")

        clear_chart_data(ch)

        assert ch.chart_target_raw.options["series"][0]["data"] == []
        assert all(fake.update_calls == 2 for fake in charts)


# ---------------------------------------------------------------------------
# TestUpdateCharts
# ---------------------------------------------------------------------------

class TestUpdateCharts:
    def test_full_window_does_not_raise(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(), reference=_make_reference())
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )

    def test_empty_window_does_not_raise(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=None, reference=None)
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )

    def test_target_raw_series_populated(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        target = _make_target(n=20)
        window = DualWindow(target=target, reference=None)
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )
        data = _series_data(ch.opts_target_raw)
        assert len(data) == 20
        # Each entry must be a [t, y] pair
        assert all(isinstance(p, list) and len(p) == 2 for p in data)

    def test_reference_raw_series_populated(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=None, reference=_make_reference(n=30))
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )
        data = _series_data(ch.opts_reference_raw)
        assert len(data) == 30

    def test_overlay_gets_both_series(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=20), reference=_make_reference(n=100))
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )
        assert len(_series_data(ch.opts_overlay, 0)) == 20
        assert len(_series_data(ch.opts_overlay, 1)) == 100

    def test_xy_buckets_populated_with_both_streams(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )
        any_data = any(
            len(_series_data(ch.opts_xy, i)) > 0 for i in range(N_XY_BUCKETS)
        )
        assert any_data

    def test_xy_data_entries_are_pairs(self, cfg):
        """Each XY bucket entry must be a display-ready [float, float] point."""
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )
        for i in range(N_XY_BUCKETS):
            for entry in _series_data(ch.opts_xy, i):
                assert isinstance(entry, list) and len(entry) == 2, f"Bad XY entry in bucket {i}: {entry!r}"

    def test_xy_lock_max_span_updates_state(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState(xy_lock_max_span=True)
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )
        if state.xy_max_span:
            assert "xmin" in state.xy_max_span
            assert "xmax" in state.xy_max_span
            assert "ymin" in state.xy_max_span
            assert "ymax" in state.xy_max_span

    def test_xy_lock_span_axis_bounds_set_in_opts(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState(xy_lock_max_span=True)
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(
            ch, window, state, cfg,
            mode="test", source_name="src", source_type="typ",
        )
        if state.xy_max_span:
            assert "min" in ch.opts_xy["xAxis"]
            assert "max" in ch.opts_xy["xAxis"]

    def test_xy_adaptive_mode_clears_axis_bounds(self, cfg):
        ch = build_chart_handles(cfg)
        # First pass with lock on to set bounds
        state = ViewerState(xy_lock_max_span=True)
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(ch, window, state, cfg, mode="t", source_name="s", source_type="t")
        # Switch to adaptive
        state.xy_lock_max_span = False
        update_charts(ch, window, state, cfg, mode="t", source_name="s", source_type="t")
        assert "min" not in ch.opts_xy["xAxis"]
        assert "max" not in ch.opts_xy["xAxis"]

    def test_replay_progress_text_forwarded(self, cfg):
        """Passing replay_progress_text should not raise (info_label is None)."""
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=10), reference=None)
        update_charts(
            ch, window, state, cfg,
            mode="csv_replay", source_name="file", source_type="csv",
            replay_progress_text="time: 1.23/10.00 s",
        )


# ---------------------------------------------------------------------------
# TestClearChartData
# ---------------------------------------------------------------------------

class TestClearChartData:
    def test_clear_zeroes_all_series(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(ch, window, state, cfg, mode="t", source_name="s", source_type="t")

        clear_chart_data(ch)

        for opts in (
            ch.opts_target_raw, ch.opts_reference_raw,
            ch.opts_target_filtered, ch.opts_target_dt, ch.opts_reference_dt,
        ):
            assert _series_data(opts) == []
        for series in ch.opts_overlay["series"]:
            assert series["data"] == []
        for i in range(N_XY_BUCKETS):
            assert _series_data(ch.opts_xy, i) == []

    def test_clear_removes_marklines(self, cfg):
        ch = build_chart_handles(cfg)
        # Manually inject a markLine to verify clear removes it
        ch.opts_target_raw["series"][0]["markLine"] = {"data": [{"xAxis": -1.0}]}
        clear_chart_data(ch)
        assert "markLine" not in ch.opts_target_raw["series"][0]

    def test_clear_resets_xy_axis_bounds(self, cfg):
        ch = build_chart_handles(cfg)
        state = ViewerState(xy_lock_max_span=True)
        window = DualWindow(target=_make_target(n=50), reference=_make_reference(n=250))
        update_charts(ch, window, state, cfg, mode="t", source_name="s", source_type="t")

        clear_chart_data(ch)
        assert "min" not in ch.opts_xy["xAxis"]
        assert "max" not in ch.opts_xy["xAxis"]


# ---------------------------------------------------------------------------
# TestMarkerIntegration
# ---------------------------------------------------------------------------

class TestMarkerIntegration:
    def test_no_markers_when_disabled(self, cfg):
        """update_charts with markers disabled → markLine data empty."""
        ch = build_chart_handles(cfg)
        state = ViewerState()
        window = DualWindow(target=_make_target(n=20), reference=None)
        update_charts(ch, window, state, cfg, mode="t", source_name="s", source_type="t")
        ml = ch.opts_target_raw["series"][0].get("markLine", {})
        assert ml.get("data", []) == []

    def test_refresh_cache_clears_events_when_disabled(self, cfg):
        """
        refresh_marker_cache respects enabled=False by clearing injected events.

        This verifies the cache-guard semantics: state.marker_events injected
        externally are always cleared on the next render cycle when markers are
        disabled, preventing stale display.
        """
        from lsl_viewer.viz.markers import refresh_marker_cache

        state = ViewerState()
        state.marker_events = [{"event": "hold_start", "lsl_ts": 1.0, "payload": {}}]
        refresh_marker_cache(state, cfg)   # cfg has enabled=False
        assert state.marker_events == []

    def test_get_marker_x_positions_pure(self, cfg):
        """get_marker_x_positions is pure: returns relative x for in-window events."""
        from lsl_viewer.viz.markers import get_marker_x_positions

        state = ViewerState()
        t_end = 10.0
        # Two events: one in window, one outside
        state.marker_events = [
            {"event": "hold_start", "lsl_ts": t_end - 2.0, "payload": {}},
            {"event": "hold_end", "lsl_ts": t_end - 999.0, "payload": {}},  # too old
        ]
        positions = get_marker_x_positions(state, cfg, t_end)
        assert len(positions) == 1
        assert positions[0] == pytest.approx(-2.0, abs=1e-9)

    def test_apply_markline_attaches_to_series(self, cfg):
        """_apply_markline writes xAxis entries to series[0]['markLine']."""
        from lsl_viewer.viz.charts import _apply_markline

        ch = build_chart_handles(cfg)
        _apply_markline(ch.opts_target_raw, [-1.0, -3.5])
        ml = ch.opts_target_raw["series"][0]["markLine"]
        assert len(ml["data"]) == 2
        assert ml["data"][0]["xAxis"] == pytest.approx(-1.0)
        assert ml["data"][1]["xAxis"] == pytest.approx(-3.5)

    def test_update_charts_applies_marklines_via_monkeypatch(self, cfg, monkeypatch):
        """
        Integration path: update_charts passes marker positions to _apply_markline.

        refresh_marker_cache is patched to a no-op so injected events survive
        the cache guard and reach _apply_markline.
        """
        import lsl_viewer.viz.charts as charts_mod

        monkeypatch.setattr(charts_mod, "refresh_marker_cache", lambda s, c: None)

        ch = build_chart_handles(cfg)
        state = ViewerState()
        target = _make_target(n=20)
        t_end = float(target.timestamps_s[-1])
        state.marker_events = [{"event": "hold_start", "lsl_ts": t_end - 2.0, "payload": {}}]

        window = DualWindow(target=target, reference=None)
        update_charts(ch, window, state, cfg, mode="t", source_name="s", source_type="t")

        ml = ch.opts_target_raw["series"][0].get("markLine", {})
        assert len(ml.get("data", [])) == 1
        assert ml["data"][0]["xAxis"] == pytest.approx(-2.0, abs=0.01)
