# @file
# @brief ECharts option builders and per-frame chart updaters.
##
# Replaces the Plotly implementation with Apache ECharts via NiceGUI's
# ui.echart() element. The architectural change is a charting backend swap
# only - the module boundary, ChartHandles interface, and update_charts() /
# clear_chart_data() signatures are unchanged from the caller's perspective.
##
# Why ECharts over Plotly for real-time streaming:
# - Canvas rendering keeps repaints cheap for high-rate live time-series lines.
# - The NiceGUI ui.echart element is the authoritative mutable chart sink.
# - Render budgeting keeps raw acquisition windows intact.
# - animation: False eliminates transition overhead for real-time updates.
##
# Correctness-first ECharts policy:
# - large mode is intentionally disabled by default.
# - Explicit downsampling limits browser payload size first.
# - Marker overlays use markLine entries on the first series of each panel.
# - XY correlation uses pre-allocated line-path buckets without None separators.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from omegaconf import DictConfig

from lsl_viewer.core.alignment import (
    compute_xy_reference_time_shift_s,
    interpolate_reference_to_target,
)
from lsl_viewer.core.timing import clock_validation_metrics, lsl_interval_ms
from lsl_viewer.types import DualWindow, FigureHandles, ViewerState
from lsl_viewer.viz.dashboard import render_info_text
from lsl_viewer.viz.markers import get_marker_x_positions, refresh_marker_cache
from lsl_viewer.viz.state import update_xy_span

log = logging.getLogger(__name__)

# Number of pre-allocated XY bucket series — constant across updates
N_XY_BUCKETS: int = 20


# ---------------------------------------------------------------------------
# CSS colour utility (unchanged from v0.3.0)
# ---------------------------------------------------------------------------

_CSS_NAMED: dict[str, tuple[int, int, int]] = {
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "lime": (0, 255, 0),
    "blue": (0, 0, 255),
    "purple": (128, 0, 128),
    "orange": (255, 165, 0),
    "cyan": (0, 255, 255),
    "aqua": (0, 255, 255),
    "magenta": (255, 0, 255),
    "fuchsia": (255, 0, 255),
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "darkblue": (0, 0, 139),
    "darkgreen": (0, 100, 0),
    "darkred": (139, 0, 0),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "maroon": (128, 0, 0),
    "olive": (128, 128, 0),
    "silver": (192, 192, 192),
    "yellow": (255, 255, 0),
}


def _css_to_rgb(color: str) -> tuple[int, int, int]:
    # @brief Convert a CSS color string to RGB.
    # @param color CSS color value.
    # @return RGB tuple.
    color = color.strip()
    if color.startswith("#"):
        h = color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return _CSS_NAMED.get(color.lower(), (128, 128, 128))


def _rgba(color: str, alpha: float) -> str:
    # @brief Convert a CSS color string to rgba().
    # @param color CSS color value.
    # @param alpha Alpha channel in [0, 1].
    # @return rgba() CSS string.
    r, g, b = _css_to_rgb(color)
    return f"rgba({r},{g},{b},{alpha:.3f})"


# ---------------------------------------------------------------------------
# ECharts option helpers
# ---------------------------------------------------------------------------


def _datazoom(type: str = "inside") -> list | dict:
    # @brief Build a preset ECharts dataZoom configuration.
    # @param type Preset selector.
    # @return dataZoom config object.
    if type == "inside":
        return {
            "type": "inside",
            "xAxisIndex": [0],
            "filterMode": "none",
            "throttle": 100,
        }
    if type == "slider":
        return [
            {
                "type": "slider",
                "show": True,
                "xAxisIndex": [0],
            },
            {
                "type": "slider",
                "show": True,
                "yAxisIndex": [0],
            },
            {
                "type": "inside",
                "xAxisIndex": [0],
                "filterMode": "none",
                "throttle": 100,
            },
            {
                "type": "inside",
                "yAxisIndex": [0],
                "filterMode": "none",
                "throttle": 100,
            },
        ]
    if type == "slider-time":
        return [
            {
                "type": "slider",
                "show": True,
                "xAxisIndex": [0],
            },
            {
                "type": "slider",
                "show": True,
                "yAxisIndex": [0],
            },
            {
                "type": "inside",
                "xAxisIndex": [0],
                "filterMode": "none",
                "throttle": 100,
            },
        ]
    raise ValueError(f"Unsupported dataZoom type: {type}")


def _grid() -> dict:
    # @brief Return the common chart grid geometry.
    # @return ECharts grid configuration.
    return {"left": 58, "right": 18, "top": 48, "bottom": 48}


def _split_line() -> dict:
    # @brief Return the shared axis split-line styling.
    # @return ECharts splitLine configuration.
    return {"lineStyle": {"color": "rgba(200,200,200,0.55)"}}


def _mk_series(name: str, color: str, width: float = 1.0, dash: str = "solid") -> dict:
    # @brief Build a single ECharts line series with realtime defaults.
    # @param name Series name.
    # @param color Series color.
    # @param width Line width.
    # @param dash Line dash style.
    # @return ECharts series dict.
    return {
        "type": "line",
        "name": name,
        "data": [],
        "showSymbol": False,
        "connectNulls": False,
        "lineStyle": {"color": color, "width": width, "type": dash},
        "animation": False,
    }


def _mk_time_opts(title: str, y_label: str, series: list[dict]) -> dict:
    # @brief Build base ECharts options for a time-domain panel.
    # @param title Panel title.
    # @param y_label Y-axis label.
    # @param series Series list.
    # @return ECharts option dict.
    return {
        "animation": False,
        "title": {"text": title, "textStyle": {"fontSize": 11}},
        "grid": _grid(),
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "dataZoom": _datazoom("slider-time"),
        "xAxis": {
            "type": "value",
            "name": "Relative LSL time (s)",
            "nameLocation": "middle",
            "nameGap": 28,
            "axisLine": {"show": True},
            "splitLine": _split_line(),
            "minorTick": {"show": True},
        },
        "yAxis": {
            "type": "value",
            "name": y_label,
            "axisLine": {"show": True},
            "splitLine": _split_line(),
            "scale": True,
            "minorTick": {"show": True},
        },
        "series": series,
    }


# ---------------------------------------------------------------------------
# ChartHandles dataclass
# ---------------------------------------------------------------------------


@dataclass
class ChartHandles:
    # @brief Hold all ECharts option dicts and their NiceGUI ui.echart elements.
    ##
    # Option dicts are mutated in-place on each render cycle. The chart_*
    # and info_label attributes are None until viz/panels.py creates the page.

    opts_target_raw: dict
    opts_reference_raw: dict
    opts_target_filtered: dict
    opts_overlay: dict
    opts_target_dt: dict
    opts_reference_dt: dict
    opts_xy: dict

    # NiceGUI ui.echart elements — assigned by panels.py
    chart_target_raw: Any = field(default=None)
    chart_reference_raw: Any = field(default=None)
    chart_target_filtered: Any = field(default=None)
    chart_overlay: Any = field(default=None)
    chart_target_dt: Any = field(default=None)
    chart_reference_dt: Any = field(default=None)
    chart_xy: Any = field(default=None)

    # NiceGUI ui.label for the info panel — assigned by panels.py
    info_label: Any = field(default=None)


# ---------------------------------------------------------------------------
# Option-dict factories
# ---------------------------------------------------------------------------


def _build_target_raw_opts(cfg: DictConfig) -> dict:
    # @brief Build options for the target raw panel.
    # @param cfg Hydra configuration.
    # @return ECharts option dict.
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return _mk_time_opts(
        "Target raw ADC counts — native irregular samples",
        f"Count / {force_unit}",
        [_mk_series("target raw", s.raw_color)],
    )


def _build_reference_raw_opts(cfg: DictConfig) -> dict:
    # @brief Build options for the reference raw panel.
    # @param cfg Hydra configuration.
    # @return ECharts option dict.
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return _mk_time_opts(
        "Reference force — native RS485 samples",
        f"Force ({force_unit})",
        [_mk_series("reference raw", s.reference_color)],
    )


def _build_target_filtered_opts(cfg: DictConfig) -> dict:
    # @brief Build options for the target filtered panel.
    # @param cfg Hydra configuration.
    # @return ECharts option dict.
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return _mk_time_opts(
        "Target filtered/current units — display only",
        f"Force ({force_unit})",
        [_mk_series("target filtered", s.filtered_color, width=1.2)],
    )


def _build_overlay_opts(cfg: DictConfig) -> dict:
    # @brief Build options for the overlay panel.
    # @param cfg Hydra configuration.
    # @return ECharts option dict.
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return _mk_time_opts(
        "Time-synchronised overlay on common LSL time axis",
        f"Force ({force_unit})",
        [
            _mk_series("target raw", s.raw_color),
            _mk_series("reference raw", s.reference_color, dash="dashed"),
        ],
    )


def _build_target_dt_opts(cfg: DictConfig) -> dict:
    # @brief Build options for the target timing panel.
    # @param cfg Hydra configuration.
    # @return ECharts option dict.
    s = cfg.viewer.style
    dt_unit = cfg.viewer.dt_unit_label
    return _mk_time_opts(
        "Target LSL sample interval",
        f"Interval ({dt_unit})",
        [_mk_series("target dt", s.timing_color)],
    )


def _build_reference_dt_opts(cfg: DictConfig) -> dict:
    # @brief Build options for the reference timing panel.
    # @param cfg Hydra configuration.
    # @return ECharts option dict.
    s = cfg.viewer.style
    dt_unit = cfg.viewer.dt_unit_label
    return _mk_time_opts(
        "Reference LSL sample interval",
        f"Interval ({dt_unit})",
        [_mk_series("reference dt", s.timing_color)],
    )


def _build_xy_opts(cfg: DictConfig) -> dict:
    # @brief Build options for the XY correlation panel.
    # @param cfg Hydra configuration.
    # @return ECharts option dict.
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return {
        "animation": False,
        "title": {
            "text": "Sensor curve: reference force vs target raw count",
            "textStyle": {"fontSize": 11},
        },
        "grid": _grid(),
        "tooltip": {"trigger": "axis"},
        "dataZoom": _datazoom("slider"),
        "xAxis": {
            "type": "value",
            "name": f"Reference force ({force_unit})",
            "nameLocation": "middle",
            "nameGap": 28,
            "splitLine": _split_line(),
            "minorTick": {"show": True},
        },
        "yAxis": {
            "type": "value",
            "name": cfg.viewer.target_raw_unit_label,
            "splitLine": _split_line(),
            "minorTick": {"show": True},
        },
        # N_XY_BUCKETS pre-allocated line series — data and colour updated each frame.
        "series": [
            {
                "type": "line",
                "name": f"age bucket {i + 1}",
                "data": [],
                "showSymbol": False,
                "connectNulls": False,
                "lineStyle": {
                    "color": _rgba(s.xy_color, 0.0),
                    "width": float(s.xy_line_width),
                },
                "animation": False,
            }
            for i in range(N_XY_BUCKETS)
        ],
    }


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_chart_handles(cfg: DictConfig) -> ChartHandles:
    # @brief Create all ECharts option dicts with pre-allocated series.
    # @param cfg Hydra configuration.
    # @return ChartHandles bundle with unbound option dicts.
    return ChartHandles(
        opts_target_raw=_build_target_raw_opts(cfg),
        opts_reference_raw=_build_reference_raw_opts(cfg),
        opts_target_filtered=_build_target_filtered_opts(cfg),
        opts_overlay=_build_overlay_opts(cfg),
        opts_target_dt=_build_target_dt_opts(cfg),
        opts_reference_dt=_build_reference_dt_opts(cfg),
        opts_xy=_build_xy_opts(cfg),
    )


# ---------------------------------------------------------------------------
# EChart sink helpers
# ---------------------------------------------------------------------------

_CHART_BINDINGS: tuple[tuple[str, str], ...] = (
    ("opts_target_raw", "chart_target_raw"),
    ("opts_reference_raw", "chart_reference_raw"),
    ("opts_target_filtered", "chart_target_filtered"),
    ("opts_overlay", "chart_overlay"),
    ("opts_target_dt", "chart_target_dt"),
    ("opts_reference_dt", "chart_reference_dt"),
    ("opts_xy", "chart_xy"),
)


def bind_chart_element(
    ch: ChartHandles,
    *,
    options_attr: str,
    chart_attr: str,
    chart_el: Any,
) -> Any:
    # @brief Bind one NiceGUI EChart element as the authoritative option owner.
    # @param ch Chart handle bundle.
    # @param options_attr Attribute name for the option dict.
    # @param chart_attr Attribute name for the NiceGUI chart element.
    # @param chart_el NiceGUI EChart element.
    # @return The bound chart element.
    if not hasattr(chart_el, "options"):
        raise TypeError(f"{chart_attr} must expose an .options mapping")
    setattr(ch, chart_attr, chart_el)
    setattr(ch, options_attr, chart_el.options)
    return chart_el


def chart_options(ch: ChartHandles, options_attr: str, chart_attr: str) -> dict:
    # @brief Return the authoritative mutable options for a chart slot.
    # @param ch Chart handle bundle.
    # @param options_attr Attribute name for the option dict.
    # @param chart_attr Attribute name for the chart element.
    # @return Mutable option dict.
    chart_el = getattr(ch, chart_attr)
    if chart_el is None:
        return getattr(ch, options_attr)
    options = chart_el.options
    setattr(ch, options_attr, options)
    return options


def iter_chart_elements(ch: ChartHandles) -> tuple[Any, ...]:
    # @brief Return all bound chart elements in stable visual order.
    # @param ch Chart handle bundle.
    # @return Tuple of chart elements.
    return tuple(getattr(ch, chart_attr) for _, chart_attr in _CHART_BINDINGS)


def push_chart_updates(ch: ChartHandles) -> None:
    # @brief Push all bound chart option changes to the browser.
    # @param ch Chart handle bundle.
    for chart_el in iter_chart_elements(ch):
        if chart_el is not None:
            chart_el.update()


# ---------------------------------------------------------------------------
# Marker overlay helpers
# ---------------------------------------------------------------------------


def _apply_markline(opts: dict, x_positions: list[float]) -> None:
    # @brief Attach calibration-marker vertical lines to the first series.
    # @param opts ECharts option dict.
    # @param x_positions Relative x-axis positions for marker lines.
    markline: dict = {
        "silent": True,
        "symbol": "none",
        "animation": False,
        "lineStyle": {"color": "#888", "type": "dashed", "width": 0.8, "opacity": 0.45},
        "data": [{"xAxis": x} for x in x_positions],
    }
    opts["series"][0]["markLine"] = markline


# ---------------------------------------------------------------------------
# Per-panel data updaters
# ---------------------------------------------------------------------------


def _render_downsample_enabled(cfg: DictConfig) -> bool:
    # @brief Return whether display-only downsampling is enabled in config.
    # @param cfg Hydra configuration.
    # @return True when render downsampling is enabled.
    try:
        return bool(cfg.viewer.render.downsample_enabled)
    except Exception:
        return True


def _render_max_points(cfg: DictConfig, key: str, default: int) -> int | None:
    # @brief Read a positive render budget, or return None when disabled.
    # @param cfg Hydra configuration.
    # @param key Render-budget field name.
    # @param default Fallback budget.
    # @return Positive point budget or None.
    if not _render_downsample_enabled(cfg):
        return None
    try:
        value = int(getattr(cfg.viewer.render, key))
    except Exception:
        value = default
    return max(2, value)


def downsample_for_render(
    x: np.ndarray,
    y: np.ndarray,
    *,
    max_points: int | None,
) -> tuple[np.ndarray, np.ndarray]:
    # @brief Return an optionally bounded display-only subset of paired data.
    # @param x X values.
    # @param y Y values.
    # @param max_points Maximum number of points to keep, or None.
    # @return Downsampled x and y arrays.
    if max_points is None or x.size <= max_points:
        return x, y
    idx = np.linspace(0, x.size - 1, max_points, dtype=np.int64)
    return x[idx], y[idx]


def downsample_xy_for_render(
    x: np.ndarray,
    y: np.ndarray,
    t: np.ndarray,
    *,
    max_points: int | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # @brief Return an optionally bounded display-only subset of XY points/timestamps.
    # @param x X values.
    # @param y Y values.
    # @param t Timestamp values.
    # @param max_points Maximum number of points to keep, or None.
    # @return Downsampled x, y, and t arrays.
    if max_points is None or x.size <= max_points:
        return x, y, t
    idx = np.linspace(0, x.size - 1, max_points, dtype=np.int64)
    return x[idx], y[idx], t[idx]


def _set_time_series(
    opts: dict,
    series_idx: int,
    t_rel: np.ndarray | None,
    y: np.ndarray | None,
    *,
    max_points: int | None,
) -> None:
    # @brief Replace one time-domain series with optionally bounded [t, y] entries.
    # @param opts ECharts option dict.
    # @param series_idx Series index to update.
    # @param t_rel Relative timestamps.
    # @param y Series values.
    # @param max_points Maximum number of points to keep, or None.
    if t_rel is not None and t_rel.size > 0 and y is not None and y.size > 0:
        plot_t, plot_y = downsample_for_render(t_rel, y, max_points=max_points)
        opts["series"][series_idx]["data"] = np.column_stack([plot_t, plot_y]).tolist()
    else:
        opts["series"][series_idx]["data"] = []


def _update_xy_series(
    opts: dict,
    x: np.ndarray,
    y: np.ndarray,
    t: np.ndarray,
    *,
    window_seconds: float,
    color: str,
    alpha_old: float,
    alpha_new: float,
    max_points: int | None,
) -> None:
    # @brief Fill the N_XY_BUCKETS pre-allocated line series with faded path segments.
    # @param opts ECharts option dict.
    # @param x X values.
    # @param y Y values.
    # @param t Timestamp values.
    # @param window_seconds XY fade window in seconds.
    # @param color Base series color.
    # @param alpha_old Alpha for oldest bucket.
    # @param alpha_new Alpha for newest bucket.
    # @param max_points Maximum number of points to keep, or None.
    if x.size == 0:
        for i in range(N_XY_BUCKETS):
            opts["series"][i]["data"] = []
            opts["series"][i]["lineStyle"]["color"] = _rgba(color, 0.0)
        return

    order = np.argsort(t)
    x, y, t = x[order], y[order], t[order]
    x, y, t = downsample_xy_for_render(x, y, t, max_points=max_points)

    ages = np.clip(t[-1] - t, 0.0, float(window_seconds))
    freshness = 1.0 - ages / float(window_seconds)
    bucket_idx = np.floor(freshness * N_XY_BUCKETS).astype(int).clip(0, N_XY_BUCKETS - 1)

    # Each bucket is one ECharts line series.  To avoid visible gaps between
    # freshness buckets, a bucket that starts after a previous bucket inherits
    # the immediately preceding point as its first point.  This preserves a
    # continuous-looking path without using renderer-specific None separators.
    bucket_data: list[list[list[float]]] = [[] for _ in range(N_XY_BUCKETS)]
    previous_point: list[float] | None = None
    previous_bucket: int | None = None
    for i, bkt_raw in enumerate(bucket_idx):
        bkt = int(bkt_raw)
        point = [float(x[i]), float(y[i])]
        if not bucket_data[bkt] and previous_point is not None and previous_bucket != bkt:
            bucket_data[bkt].append(previous_point)
        bucket_data[bkt].append(point)
        previous_point = point
        previous_bucket = bkt

    r, g, b = _css_to_rgb(color)
    for bkt in range(N_XY_BUCKETS):
        mid_freshness = (bkt + 0.5) / N_XY_BUCKETS
        alpha = float(alpha_old) + mid_freshness * (float(alpha_new) - float(alpha_old))
        color_str = f"rgba({r},{g},{b},{alpha:.3f})" if len(bucket_data[bkt]) >= 2 else f"rgba({r},{g},{b},0)"
        opts["series"][bkt]["data"] = bucket_data[bkt]
        opts["series"][bkt]["lineStyle"]["color"] = color_str


# ---------------------------------------------------------------------------
# Main per-frame update entry point
# ---------------------------------------------------------------------------


def update_charts(
    ch: ChartHandles,
    window: DualWindow,
    state: ViewerState,
    cfg: DictConfig,
    *,
    mode: str,
    source_name: str,
    source_type: str,
    target_new_samples: int | None = None,
    reference_new_samples: int | None = None,
    replay_progress_text: str | None = None,
) -> None:
    # @brief Update all ECharts option dicts for one render cycle.
    # @param ch Chart handle bundle.
    # @param window Current dual window.
    # @param state Viewer state.
    # @param cfg Hydra configuration.
    # @param mode Current mode string.
    # @param source_name Data source name.
    # @param source_type Data source type.
    # @param target_new_samples Optional target sample count since last tick.
    # @param reference_new_samples Optional reference sample count since last tick.
    # @param replay_progress_text Optional replay progress text.
    target = window.target
    reference = window.reference
    style = cfg.viewer.style
    time_max_points = _render_max_points(cfg, "max_points_time_series", 1200)
    xy_max_points = _render_max_points(cfg, "max_points_xy", 1500)

    opts_target_raw = chart_options(ch, "opts_target_raw", "chart_target_raw")
    opts_reference_raw = chart_options(ch, "opts_reference_raw", "chart_reference_raw")
    opts_target_filtered = chart_options(ch, "opts_target_filtered", "chart_target_filtered")
    opts_overlay = chart_options(ch, "opts_overlay", "chart_overlay")
    opts_target_dt = chart_options(ch, "opts_target_dt", "chart_target_dt")
    opts_reference_dt = chart_options(ch, "opts_reference_dt", "chart_reference_dt")
    opts_xy = chart_options(ch, "opts_xy", "chart_xy")

    # ── t_end for relative time axis ─────────────────────────────────────
    latest_ts: list[float] = []
    if target is not None and target.timestamps_s.size:
        latest_ts.append(float(np.nanmax(target.timestamps_s)))
    if reference is not None and reference.timestamps_s.size:
        latest_ts.append(float(np.nanmax(reference.timestamps_s)))
    t_end = max(latest_ts) if latest_ts else 0.0

    # ── Calibration markers (cached read) ─────────────────────────────────
    refresh_marker_cache(state, cfg)
    marker_x = get_marker_x_positions(state, cfg, t_end)

    # ── Target time-domain panels ─────────────────────────────────────────
    target_rate_hz = float("nan")
    target_clock_metrics: dict = {}
    t_rel: np.ndarray | None = None

    if target is not None and target.timestamps_s.size:
        t_rel = target.timestamps_s - t_end
        _set_time_series(opts_target_raw, 0, t_rel, target.raw, max_points=time_max_points)
        _set_time_series(opts_target_filtered, 0, t_rel, target.filtered, max_points=time_max_points)
        _set_time_series(opts_overlay, 0, t_rel, target.filtered, max_points=time_max_points)
        _apply_markline(opts_target_raw, marker_x)
        _apply_markline(opts_target_filtered, marker_x)
        _apply_markline(opts_overlay, marker_x)

        dt_idx, dt_ms, target_rate_hz, _ = lsl_interval_ms(target.timestamps_s)
        if dt_ms.size:
            _set_time_series(opts_target_dt, 0, t_rel[dt_idx.astype(int)], dt_ms, max_points=time_max_points)
        else:
            opts_target_dt["series"][0]["data"] = []

        if target.device_clock_us.size:
            target_clock_metrics = clock_validation_metrics(
                target.timestamps_s, target.device_clock_us, clock_scale_to_s=1e-6
            )
    else:
        for opts in (opts_target_raw, opts_target_filtered, opts_overlay):
            opts["series"][0]["data"] = []
            _apply_markline(opts, marker_x)
        opts_target_dt["series"][0]["data"] = []

    # ── Reference time-domain panels ──────────────────────────────────────
    reference_rate_hz = float("nan")
    reference_clock_metrics: dict = {}

    if reference is not None and reference.timestamps_s.size:
        ref_t_rel = reference.timestamps_s - t_end
        _set_time_series(opts_reference_raw, 0, ref_t_rel, reference.raw, max_points=time_max_points)
        _set_time_series(opts_overlay, 1, ref_t_rel, reference.raw, max_points=time_max_points)
        _apply_markline(opts_reference_raw, marker_x)

        dt_idx, dt_ms, reference_rate_hz, _ = lsl_interval_ms(reference.timestamps_s)
        if dt_ms.size:
            _set_time_series(opts_reference_dt, 0, ref_t_rel[dt_idx.astype(int)], dt_ms, max_points=time_max_points)
        else:
            opts_reference_dt["series"][0]["data"] = []

        if reference.rs485_clock.size:
            reference_clock_metrics = clock_validation_metrics(
                reference.timestamps_s, reference.rs485_clock, clock_scale_to_s=1.0
            )
    else:
        opts_reference_raw["series"][0]["data"] = []
        _apply_markline(opts_reference_raw, marker_x)
        opts_overlay["series"][1]["data"] = []
        opts_reference_dt["series"][0]["data"] = []

    # ── XY correlation ────────────────────────────────────────────────────
    ta = cfg.viewer.xy_correlation.time_alignment
    _handles_state = state.to_handles_state()
    _handles_proxy = FigureHandles(fig=None, axes={}, artists={}, state=_handles_state)
    xy_reference_shift_s, xy_alignment_mode = compute_xy_reference_time_shift_s(
        _handles_proxy,
        target,
        reference,
        alignment_mode=ta.mode,
        window_seconds=cfg.viewer.window_seconds,
        manual_reference_shift_s=ta.manual_reference_shift_s,
        max_auto_shift_s=ta.max_auto_shift_s,
        min_auto_shift_s=ta.min_auto_shift_s,
        snap_threshold_s=ta.snap_threshold_s,
        smoothing_alpha=ta.smoothing_alpha,
    )
    state.sync_from_handles_state(_handles_state)

    xy_x, xy_y, xy_t = interpolate_reference_to_target(
        target,
        reference,
        cfg.alignment.max_reference_gap_s,
        reference_time_shift_s=xy_reference_shift_s,
        target_signal=cfg.viewer.xy_correlation.target_signal,
    )

    _update_xy_series(
        opts_xy,
        xy_x,
        xy_y,
        xy_t,
        window_seconds=cfg.viewer.window_seconds,
        color=style.xy_color,
        alpha_old=style.xy_alpha_old,
        alpha_new=style.xy_alpha_new,
        max_points=xy_max_points,
    )

    # XY axis range (lock-max-span)
    if xy_x.size > 0:
        span = update_xy_span(state.xy_max_span, xy_x, xy_y, state.xy_lock_max_span)
        opts_xy.update(span)
        state.xy_max_span = span if state.xy_lock_max_span else {}

    xy_lock_label = "max-span lock" if state.xy_lock_max_span else "adaptive"
    clipped = "; clipped" if state.xy_reference_shift_clipped else ""
    opts_xy["title"]["text"] = (
        f"Sensor curve: reference force vs target raw count  "
        f"[{xy_lock_label}  align={xy_alignment_mode}{clipped}  "
        f"ref_shift={xy_reference_shift_s:+.3f}s]"
    )

    # ── Info panel ─────────────────────────────────────────────────────────
    info_text = render_info_text(
        window=window,
        state=state,
        cfg=cfg,
        mode=mode,
        source_name=source_name,
        source_type=source_type,
        xy_reference_shift_s=xy_reference_shift_s,
        xy_alignment_mode=xy_alignment_mode,
        marker_count=len(state.marker_events),
        target_rate_hz=target_rate_hz,
        reference_rate_hz=reference_rate_hz,
        target_clock_metrics=target_clock_metrics,
        reference_clock_metrics=reference_clock_metrics,
        xy_pair_count=int(xy_x.size),
        target_new_samples=target_new_samples,
        reference_new_samples=reference_new_samples,
        replay_progress_text=replay_progress_text,
    )
    if ch.info_label is not None:
        ch.info_label.set_text(info_text)

    # ── Push all chart updates to the browser ──────────────────────────────
    push_chart_updates(ch)


def clear_chart_data(ch: ChartHandles) -> None:
    # @brief Clear all series data and reset XY axis bounds.
    # @param ch Chart handle bundle.
    opts_target_raw = chart_options(ch, "opts_target_raw", "chart_target_raw")
    opts_reference_raw = chart_options(ch, "opts_reference_raw", "chart_reference_raw")
    opts_target_filtered = chart_options(ch, "opts_target_filtered", "chart_target_filtered")
    opts_overlay = chart_options(ch, "opts_overlay", "chart_overlay")
    opts_target_dt = chart_options(ch, "opts_target_dt", "chart_target_dt")
    opts_reference_dt = chart_options(ch, "opts_reference_dt", "chart_reference_dt")
    opts_xy = chart_options(ch, "opts_xy", "chart_xy")

    for opts in (
        opts_target_raw,
        opts_reference_raw,
        opts_target_filtered,
        opts_target_dt,
        opts_reference_dt,
    ):
        for series in opts["series"]:
            series["data"] = []
            series.pop("markLine", None)

    for series in opts_overlay["series"]:
        series["data"] = []
        series.pop("markLine", None)

    for series in opts_xy["series"]:
        series["data"] = []

    # Reset XY axis to auto-scale.
    for axis in ("xAxis", "yAxis"):
        opts_xy[axis].pop("min", None)
        opts_xy[axis].pop("max", None)

    push_chart_updates(ch)
