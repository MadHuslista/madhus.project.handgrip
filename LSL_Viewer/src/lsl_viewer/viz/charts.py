"""
ECharts option builders and per-frame chart updaters.

Replaces the Plotly implementation (v0.3.0) with Apache ECharts via
NiceGUI's ``ui.echart()`` element.  The architectural change is a charting
*backend* swap only — the module boundary, ``ChartHandles`` interface, and
``update_charts`` / ``clear_chart_data`` signatures are unchanged from the
callers' perspective.

Why ECharts over Plotly for real-time streaming
------------------------------------------------
* **Canvas rendering** — ECharts renders to an HTML5 canvas pixel buffer by
  default.  Plotly uses SVG (one DOM node per visible data point), which is
  3–10× slower to repaint for 1,000-point time-series lines.
* **``large`` mode** — when ``large: True`` and point count exceeds
  ``largeThreshold``, ECharts automatically applies a line-sampling algorithm
  so 10,000 points render as fast as 500 visually.
* **``animation: False``** — eliminates all transition overhead for real-time
  updates; essential for sub-100 ms refresh cycles.
* **No differential overhead** — ``setOption()`` replaces data directly.
  Plotly's ``Plotly.react()`` computed a JSON diff first, then applied it.

Marker overlays
---------------
Calibration event markers are rendered as ECharts ``markLine`` entries
attached to the first series of each time-domain panel — no separate shape
layer needed.

XY faded-line collection
------------------------
The N_XY_BUCKETS=20 pre-allocated series approach is preserved verbatim from
the Plotly implementation.  Only the data container changes: ECharts paired
``[[x, y], [x, y], None, ...]`` lists replace Plotly's ``Scatter.x`` /
``Scatter.y`` arrays.
"""
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
from lsl_viewer.viz.state import update_xy_max_span

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
    color = color.strip()
    if color.startswith("#"):
        h = color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return _CSS_NAMED.get(color.lower(), (128, 128, 128))


def _rgba(color: str, alpha: float) -> str:
    r, g, b = _css_to_rgb(color)
    return f"rgba({r},{g},{b},{alpha:.3f})"


# ---------------------------------------------------------------------------
# ECharts option helpers
# ---------------------------------------------------------------------------


def _grid() -> dict:
    return {"left": 58, "right": 18, "top": 48, "bottom": 48}


def _split_line() -> dict:
    return {"lineStyle": {"color": "rgba(200,200,200,0.55)"}}


def _mk_series(name: str, color: str, width: float = 1.0, dash: str = "solid") -> dict:
    """Single ECharts line series with real-time optimisations enabled."""
    return {
        "type": "line",
        "name": name,
        "data": [],
        "showSymbol": False,
        "lineStyle": {"color": color, "width": width, "type": dash},
        "large": True,
        "largeThreshold": 100,
        "animation": False,
    }


def _mk_time_opts(title: str, y_label: str, series: list[dict]) -> dict:
    """Base ECharts options for a time-domain panel."""
    return {
        "animation": False,
        "title": {"text": title, "textStyle": {"fontSize": 11}},
        "grid": _grid(),
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "xAxis": {
            "type": "value",
            "name": "Relative LSL time (s)",
            "nameLocation": "middle",
            "nameGap": 28,
            "axisLine": {"show": True},
            "splitLine": _split_line(),
        },
        "yAxis": {
            "type": "value",
            "name": y_label,
            "axisLine": {"show": True},
            "splitLine": _split_line(),
        },
        "series": series,
    }


# ---------------------------------------------------------------------------
# ChartHandles dataclass
# ---------------------------------------------------------------------------


@dataclass
class ChartHandles:
    """
    Holds all ECharts option dicts and their NiceGUI ui.echart elements.

    Option dicts are mutated in-place on each render cycle.  The ``chart_*``
    and ``info_label`` attributes are ``None`` until ``viz/panels.py``
    creates the page and fills them in.
    """

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
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return _mk_time_opts(
        "Target raw ADC counts — native irregular samples",
        f"Count / {force_unit}",
        [_mk_series("target raw", s.raw_color)],
    )


def _build_reference_raw_opts(cfg: DictConfig) -> dict:
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return _mk_time_opts(
        "Reference force — native RS485 samples",
        f"Force ({force_unit})",
        [_mk_series("reference raw", s.reference_color)],
    )


def _build_target_filtered_opts(cfg: DictConfig) -> dict:
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    return _mk_time_opts(
        "Target filtered/current units — display only",
        f"Force ({force_unit})",
        [_mk_series("target filtered", s.filtered_color, width=1.2)],
    )


def _build_overlay_opts(cfg: DictConfig) -> dict:
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
    s = cfg.viewer.style
    dt_unit = cfg.viewer.dt_unit_label
    return _mk_time_opts(
        "Target LSL sample interval",
        f"Interval ({dt_unit})",
        [_mk_series("target dt", s.timing_color)],
    )


def _build_reference_dt_opts(cfg: DictConfig) -> dict:
    s = cfg.viewer.style
    dt_unit = cfg.viewer.dt_unit_label
    return _mk_time_opts(
        "Reference LSL sample interval",
        f"Interval ({dt_unit})",
        [_mk_series("reference dt", s.timing_color)],
    )


def _build_xy_opts(cfg: DictConfig) -> dict:
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
        "xAxis": {
            "type": "value",
            "name": f"Reference force ({force_unit})",
            "nameLocation": "middle",
            "nameGap": 28,
            "splitLine": _split_line(),
        },
        "yAxis": {
            "type": "value",
            "name": cfg.viewer.target_raw_unit_label,
            "splitLine": _split_line(),
        },
        # N_XY_BUCKETS pre-allocated series — data and colour updated each frame
        "series": [
            {
                "type": "line",
                "data": [],
                "showSymbol": False,
                "lineStyle": {
                    "color": _rgba(s.xy_color, 0.0),
                    "width": float(s.xy_line_width),
                },
                "large": True,
                "largeThreshold": 50,
                "animation": False,
            }
            for _ in range(N_XY_BUCKETS)
        ],
    }


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_chart_handles(cfg: DictConfig) -> ChartHandles:
    """
    Create all ECharts option dicts with pre-allocated series.

    Called *before* the NiceGUI page is built.  ``viz/panels.py`` fills in
    the ``chart_*`` element references once ``ui.echart()`` is called.
    """
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
# Marker overlay helpers
# ---------------------------------------------------------------------------


def _apply_markline(opts: dict, x_positions: list[float]) -> None:
    """Attach calibration-marker vertical lines to the first series."""
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


def _set_time_series(opts: dict, series_idx: int, t_rel: np.ndarray | None, y: np.ndarray | None) -> None:
    """Replace the data for one time-domain series with paired [t, y] entries."""
    if t_rel is not None and t_rel.size > 0 and y is not None and y.size > 0:
        opts["series"][series_idx]["data"] = np.column_stack([t_rel, y]).tolist()
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
) -> None:
    """
    Fill the N_XY_BUCKETS pre-allocated series with faded line segments.

    Data format: ``[[x0, y0], [x1, y1], None, [x2, y2], ...]``
    ``None`` entries break the line between non-consecutive segments,
    equivalent to the NaN-separator approach used in the Plotly version.
    """
    if x.size < 2:
        for i in range(N_XY_BUCKETS):
            opts["series"][i]["data"] = []
        return

    order = np.argsort(t)
    x, y, t = x[order], y[order], t[order]
    n_segs = len(t) - 1

    ages = np.clip(t[-1] - t[1:], 0.0, float(window_seconds))
    freshness = 1.0 - ages / float(window_seconds)
    bucket_idx = np.floor(freshness * N_XY_BUCKETS).astype(int).clip(0, N_XY_BUCKETS - 1)

    # Accumulate segment pairs per bucket (with None breaks)
    bucket_data: list[list] = [[] for _ in range(N_XY_BUCKETS)]
    for i in range(n_segs):
        bkt = int(bucket_idx[i])
        bucket_data[bkt].append([float(x[i]), float(y[i])])
        bucket_data[bkt].append([float(x[i + 1]), float(y[i + 1])])
        bucket_data[bkt].append(None)  # break between non-consecutive segments

    r, g, b = _css_to_rgb(color)
    for bkt in range(N_XY_BUCKETS):
        mid_freshness = (bkt + 0.5) / N_XY_BUCKETS
        alpha = float(alpha_old) + mid_freshness * (float(alpha_new) - float(alpha_old))
        color_str = f"rgba({r},{g},{b},{alpha:.3f})" if bucket_data[bkt] else f"rgba({r},{g},{b},0)"
        opts["series"][bkt]["data"] = bucket_data[bkt] if bucket_data[bkt] else []
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
    """Update all ECharts option dicts for one render cycle, then push to browser."""
    target = window.target
    reference = window.reference
    style = cfg.viewer.style

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
        _set_time_series(ch.opts_target_raw, 0, t_rel, target.raw)
        _set_time_series(ch.opts_target_filtered, 0, t_rel, target.filtered)
        _set_time_series(ch.opts_overlay, 0, t_rel, target.filtered)
        _apply_markline(ch.opts_target_raw, marker_x)
        _apply_markline(ch.opts_target_filtered, marker_x)
        _apply_markline(ch.opts_overlay, marker_x)

        dt_idx, dt_ms, target_rate_hz, _ = lsl_interval_ms(target.timestamps_s)
        if dt_ms.size:
            _set_time_series(ch.opts_target_dt, 0, t_rel[dt_idx.astype(int)], dt_ms)
        else:
            ch.opts_target_dt["series"][0]["data"] = []

        if target.device_clock_us.size:
            target_clock_metrics = clock_validation_metrics(
                target.timestamps_s, target.device_clock_us, clock_scale_to_s=1e-6
            )
    else:
        for opts in (ch.opts_target_raw, ch.opts_target_filtered, ch.opts_overlay):
            opts["series"][0]["data"] = []
            _apply_markline(opts, marker_x)
        ch.opts_target_dt["series"][0]["data"] = []

    # ── Reference time-domain panels ──────────────────────────────────────
    reference_rate_hz = float("nan")
    reference_clock_metrics: dict = {}

    if reference is not None and reference.timestamps_s.size:
        ref_t_rel = reference.timestamps_s - t_end
        _set_time_series(ch.opts_reference_raw, 0, ref_t_rel, reference.raw)
        _set_time_series(ch.opts_overlay, 1, ref_t_rel, reference.raw)
        _apply_markline(ch.opts_reference_raw, marker_x)

        dt_idx, dt_ms, reference_rate_hz, _ = lsl_interval_ms(reference.timestamps_s)
        if dt_ms.size:
            _set_time_series(ch.opts_reference_dt, 0, ref_t_rel[dt_idx.astype(int)], dt_ms)
        else:
            ch.opts_reference_dt["series"][0]["data"] = []

        if reference.rs485_clock.size:
            reference_clock_metrics = clock_validation_metrics(
                reference.timestamps_s, reference.rs485_clock, clock_scale_to_s=1.0
            )
    else:
        ch.opts_reference_raw["series"][0]["data"] = []
        _apply_markline(ch.opts_reference_raw, marker_x)
        ch.opts_overlay["series"][1]["data"] = []
        ch.opts_reference_dt["series"][0]["data"] = []

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
        ch.opts_xy,
        xy_x,
        xy_y,
        xy_t,
        window_seconds=cfg.viewer.window_seconds,
        color=style.xy_color,
        alpha_old=style.xy_alpha_old,
        alpha_new=style.xy_alpha_new,
    )

    # XY axis range (lock-max-span)
    if xy_x.size > 0 and state.xy_lock_max_span:
        state.xy_max_span = update_xy_max_span(state.xy_max_span, xy_x, xy_y)
        span = state.xy_max_span
        ch.opts_xy["xAxis"].update({"min": span["xmin"], "max": span["xmax"]})
        ch.opts_xy["yAxis"].update({"min": span["ymin"], "max": span["ymax"]})
    elif not state.xy_lock_max_span:
        state.xy_max_span = {}
        ch.opts_xy["xAxis"].pop("min", None)
        ch.opts_xy["xAxis"].pop("max", None)
        ch.opts_xy["yAxis"].pop("min", None)
        ch.opts_xy["yAxis"].pop("max", None)

    xy_lock_label = "max-span lock" if state.xy_lock_max_span else "adaptive"
    clipped = "; clipped" if state.xy_reference_shift_clipped else ""
    ch.opts_xy["title"]["text"] = (
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
    for chart_el in (
        ch.chart_target_raw,
        ch.chart_reference_raw,
        ch.chart_target_filtered,
        ch.chart_overlay,
        ch.chart_target_dt,
        ch.chart_reference_dt,
        ch.chart_xy,
    ):
        if chart_el is not None:
            chart_el.update()


def clear_chart_data(ch: ChartHandles) -> None:
    """Clear all series data and reset XY axis bounds."""
    for opts in (
        ch.opts_target_raw,
        ch.opts_reference_raw,
        ch.opts_target_filtered,
        ch.opts_target_dt,
        ch.opts_reference_dt,
    ):
        for series in opts["series"]:
            series["data"] = []
            series.pop("markLine", None)

    for series in ch.opts_overlay["series"]:
        series["data"] = []
        series.pop("markLine", None)

    for series in ch.opts_xy["series"]:
        series["data"] = []

    # Reset XY axis to auto-scale
    for axis in ("xAxis", "yAxis"):
        ch.opts_xy[axis].pop("min", None)
        ch.opts_xy[axis].pop("max", None)

    for chart_el in (
        ch.chart_target_raw,
        ch.chart_reference_raw,
        ch.chart_target_filtered,
        ch.chart_overlay,
        ch.chart_target_dt,
        ch.chart_reference_dt,
        ch.chart_xy,
    ):
        if chart_el is not None:
            chart_el.update()
