"""Plotly figure builders and per-frame chart updaters.

This module replaces ``viz/figure.py`` and ``viz/plots.py`` from the
Matplotlib implementation.  All chart state lives in :class:`ChartHandles`;
the NiceGUI ``ui.plotly`` element references are stored there too after
``viz/panels.py`` creates the page.

Architecture
------------
* ``build_chart_handles(cfg)``  — creates all :class:`plotly.graph_objects.Figure`
  objects with pre-allocated traces.  Called *before* the NiceGUI page is built.
* ``update_charts(ch, ...)``    — called once per timer tick to push new data into
  the figures and call ``ui.plotly.update()`` on each element.

XY panel
--------
The time-faded line collection from the Matplotlib implementation is reproduced
using N_XY_BUCKETS pre-allocated Scatter traces.  Each bucket covers a freshness
range; its line colour carries the corresponding alpha value.  The bucket approach
keeps the trace count constant (no add/remove on each frame) which is critical for
``Plotly.react``'s diffing efficiency.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import plotly.graph_objects as go
from omegaconf import DictConfig

from lsl_viewer.core.alignment import (
    compute_xy_reference_time_shift_s,
    interpolate_reference_to_target,
)
from lsl_viewer.core.timing import clock_validation_metrics, lsl_interval_ms
from lsl_viewer.types import DualWindow, FigureHandles, ViewerState
from lsl_viewer.viz.dashboard import render_info_text
from lsl_viewer.viz.markers import get_marker_shapes, refresh_marker_cache
from lsl_viewer.viz.state import compute_axis_limits, update_xy_max_span

log = logging.getLogger(__name__)

# Number of pre-allocated XY bucket traces (constant across updates)
N_XY_BUCKETS: int = 20

# Trace indices in the main figure (must match add_trace call order in _build_*_figure)
TRACE_TARGET_RAW: int = 0
TRACE_REFERENCE_RAW: int = 0
TRACE_TARGET_FILTERED: int = 0
TRACE_OVERLAY_TARGET: int = 0
TRACE_OVERLAY_REFERENCE: int = 1
TRACE_TARGET_DT: int = 0
TRACE_REFERENCE_DT: int = 0
TRACE_XY_START: int = 0  # traces 0..N_XY_BUCKETS-1 in fig_xy


# ---------------------------------------------------------------------------
# CSS colour utility
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
    """Convert a CSS color name or hex string to an integer (R, G, B) tuple."""
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
# ChartHandles dataclass
# ---------------------------------------------------------------------------

@dataclass
class ChartHandles:
    """Holds all Plotly figures and the NiceGUI ui.plotly element references.

    Figures are created in ``build_chart_handles()`` before the page is built.
    The ``plot_*`` and ``info_label`` attributes are filled in by
    ``viz/panels.py`` when it creates the NiceGUI page elements.
    """

    fig_target_raw: go.Figure
    fig_reference_raw: go.Figure
    fig_target_filtered: go.Figure
    fig_overlay: go.Figure
    fig_target_dt: go.Figure
    fig_reference_dt: go.Figure
    fig_xy: go.Figure

    # NiceGUI ui.plotly elements — assigned by panels.py
    plot_target_raw: Any = field(default=None)
    plot_reference_raw: Any = field(default=None)
    plot_target_filtered: Any = field(default=None)
    plot_overlay: Any = field(default=None)
    plot_target_dt: Any = field(default=None)
    plot_reference_dt: Any = field(default=None)
    plot_xy: Any = field(default=None)

    # NiceGUI ui.label for the info panel — assigned by panels.py
    info_label: Any = field(default=None)


# ---------------------------------------------------------------------------
# Individual figure builders
# ---------------------------------------------------------------------------

_LAYOUT_DEFAULTS = dict(
    margin=dict(l=55, r=15, t=40, b=45),
    paper_bgcolor="white",
    plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0, font=dict(size=9)),
)

_GRID_STYLE = dict(showgrid=True, gridwidth=1, gridcolor="rgba(200,200,200,0.5)")


def _base_time_figure(title: str, y_label: str, force_unit: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title_text=title,
        title_font=dict(size=11),
        xaxis_title="Relative LSL time (s)",
        yaxis_title=y_label,
        showlegend=True,
        **_LAYOUT_DEFAULTS,
    )
    fig.update_xaxes(**_GRID_STYLE)
    fig.update_yaxes(**_GRID_STYLE)
    return fig


def _build_target_raw_figure(cfg: DictConfig) -> go.Figure:
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    fig = _base_time_figure(
        "Target raw ADC counts — native irregular samples",
        f"Force ({force_unit})",
        force_unit,
    )
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(color=s.raw_color, width=1.0),
        name="target raw",
    ))
    return fig


def _build_reference_raw_figure(cfg: DictConfig) -> go.Figure:
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    fig = _base_time_figure(
        "Reference force — native RS485 samples",
        f"Force ({force_unit})",
        force_unit,
    )
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(color=s.reference_color, width=1.0),
        name="reference raw",
    ))
    return fig


def _build_target_filtered_figure(cfg: DictConfig) -> go.Figure:
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    fig = _base_time_figure(
        "Target filtered/current units — display only",
        f"Force ({force_unit})",
        force_unit,
    )
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(color=s.filtered_color, width=1.2),
        name="target filtered",
    ))
    return fig


def _build_overlay_figure(cfg: DictConfig) -> go.Figure:
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    fig = _base_time_figure(
        "Time-synchronised engineering-unit overlay on common LSL time axis",
        f"Force ({force_unit})",
        force_unit,
    )
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(color=s.raw_color, width=1.0),
        name="target raw",
    ))
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(color=s.reference_color, width=1.0, dash="dash"),
        name="reference raw",
    ))
    return fig


def _build_target_dt_figure(cfg: DictConfig) -> go.Figure:
    s = cfg.viewer.style
    dt_unit = cfg.viewer.dt_unit_label
    fig = _base_time_figure(
        "Target LSL sample interval",
        f"Interval ({dt_unit})",
        "",
    )
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(color=s.timing_color, width=1.0),
        name="target dt",
    ))
    return fig


def _build_reference_dt_figure(cfg: DictConfig) -> go.Figure:
    s = cfg.viewer.style
    dt_unit = cfg.viewer.dt_unit_label
    fig = _base_time_figure(
        "Reference LSL sample interval",
        f"Interval ({dt_unit})",
        "",
    )
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(color=s.timing_color, width=1.0),
        name="reference dt",
    ))
    return fig


def _build_xy_figure(cfg: DictConfig) -> go.Figure:
    s = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    fig = go.Figure()
    fig.update_layout(
        title_text="Sensor curve: reference force vs target raw count",
        title_font=dict(size=11),
        xaxis_title=f"Reference force at target timestamps ({force_unit})",
        yaxis_title=cfg.viewer.target_raw_unit_label,
        showlegend=False,
        **_LAYOUT_DEFAULTS,
    )
    fig.update_xaxes(**_GRID_STYLE)
    fig.update_yaxes(**_GRID_STYLE)

    # Pre-allocate N_XY_BUCKETS traces — data and colour updated in-place each frame
    for _ in range(N_XY_BUCKETS):
        fig.add_trace(go.Scatter(
            x=[], y=[], mode="lines",
            line=dict(color=_rgba(s.xy_color, 0.0), width=float(s.xy_line_width)),
            showlegend=False,
        ))
    return fig


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def build_chart_handles(cfg: DictConfig) -> ChartHandles:
    """Create all Plotly figures with pre-allocated traces.

    Must be called *before* the NiceGUI page is built.  The returned
    :class:`ChartHandles` object is passed to ``viz/panels.py`` which
    fills in the ``plot_*`` and ``info_label`` attributes.
    """
    return ChartHandles(
        fig_target_raw=_build_target_raw_figure(cfg),
        fig_reference_raw=_build_reference_raw_figure(cfg),
        fig_target_filtered=_build_target_filtered_figure(cfg),
        fig_overlay=_build_overlay_figure(cfg),
        fig_target_dt=_build_target_dt_figure(cfg),
        fig_reference_dt=_build_reference_dt_figure(cfg),
        fig_xy=_build_xy_figure(cfg),
    )


# ---------------------------------------------------------------------------
# Per-panel data updaters (imperative side of the functional core)
# ---------------------------------------------------------------------------

def _set_trace(fig: go.Figure, idx: int, x: Any, y: Any) -> None:
    """Update x/y data on a single trace in-place."""
    fig.data[idx].x = x if len(x) else []
    fig.data[idx].y = y if len(y) else []


def _update_time_panel(
    fig: go.Figure,
    trace_idx: int,
    t_rel: np.ndarray | None,
    y: np.ndarray | None,
    shapes: list[dict] | None = None,
) -> None:
    if t_rel is not None and t_rel.size > 0 and y is not None and y.size > 0:
        _set_trace(fig, trace_idx, t_rel, y)
    else:
        _set_trace(fig, trace_idx, [], [])
    if shapes is not None:
        fig.update_layout(shapes=shapes)


def _update_xy_traces(
    fig: go.Figure,
    x: np.ndarray,
    y: np.ndarray,
    t: np.ndarray,
    *,
    window_seconds: float,
    color: str,
    alpha_old: float,
    alpha_new: float,
) -> None:
    """Fill XY bucket traces with faded line segments.

    Reproduces the Matplotlib LineCollection per-segment alpha approach using
    N_XY_BUCKETS pre-allocated Scatter traces.  Each bucket covers a freshness
    band; its alpha is the midpoint of that band.
    """
    if x.size < 2:
        for i in range(N_XY_BUCKETS):
            _set_trace(fig, i, [], [])
        return

    order = np.argsort(t)
    x, y, t = x[order], y[order], t[order]

    # Freshness: 0.0 (oldest) → 1.0 (newest) for each segment endpoint
    ages = np.clip(t[-1] - t[1:], 0.0, float(window_seconds))
    freshness = 1.0 - ages / float(window_seconds)
    bucket_indices = np.floor(freshness * N_XY_BUCKETS).astype(int).clip(0, N_XY_BUCKETS - 1)

    # Build segment lists per bucket using NaN separators
    bx: list[list[float]] = [[] for _ in range(N_XY_BUCKETS)]
    by: list[list[float]] = [[] for _ in range(N_XY_BUCKETS)]
    n_segs = len(t) - 1
    for i in range(n_segs):
        bkt = int(bucket_indices[i])
        bx[bkt] += [float(x[i]), float(x[i + 1]), None]
        by[bkt] += [float(y[i]), float(y[i + 1]), None]

    # Update each bucket trace with appropriate alpha
    for bkt in range(N_XY_BUCKETS):
        mid_freshness = (bkt + 0.5) / N_XY_BUCKETS
        alpha = float(alpha_old) + mid_freshness * (float(alpha_new) - float(alpha_old))
        color_str = _rgba(color, alpha) if bx[bkt] else _rgba(color, 0.0)
        fig.data[bkt].x = bx[bkt] if bx[bkt] else []
        fig.data[bkt].y = by[bkt] if by[bkt] else []
        fig.data[bkt].line.color = color_str


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
    """Update all Plotly figures for one render cycle and push to browser.

    Mirrors the signature of the original ``viz/plots.py:update_plots()``.
    """
    target = window.target
    reference = window.reference
    style = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label

    # ── Compute t_end for relative time axis ─────────────────────────────
    latest_ts: list[float] = []
    if target is not None and target.timestamps_s.size:
        latest_ts.append(float(np.nanmax(target.timestamps_s)))
    if reference is not None and reference.timestamps_s.size:
        latest_ts.append(float(np.nanmax(reference.timestamps_s)))
    t_end = max(latest_ts) if latest_ts else 0.0

    # ── Calibration marker shapes (cached) ───────────────────────────────
    refresh_marker_cache(state, cfg)
    # xref names for the 4 time-domain panels (each is its own figure)
    # Since each panel is a separate go.Figure, shapes use default refs ('x', 'y')
    time_domain_shapes = get_marker_shapes(state, cfg, t_end, xaxis_refs=["x"])

    # ── Target time-domain plots ──────────────────────────────────────────
    target_rate_hz = float("nan")
    target_mean_dt_ms = float("nan")
    target_t_rel: np.ndarray | None = None
    if target is not None and target.timestamps_s.size:
        target_t_rel = target.timestamps_s - t_end
        _update_time_panel(ch.fig_target_raw, 0, target_t_rel, target.raw, time_domain_shapes)
        _update_time_panel(ch.fig_target_filtered, 0, target_t_rel, target.filtered, time_domain_shapes)
        # Overlay: target trace (index 0)
        _set_trace(ch.fig_overlay, 0, target_t_rel, target.filtered)

        dt_idx, dt_ms, target_rate_hz, target_mean_dt_ms = lsl_interval_ms(target.timestamps_s)
        if dt_ms.size:
            dt_t_rel = target_t_rel[dt_idx.astype(int)]
            _update_time_panel(ch.fig_target_dt, 0, dt_t_rel, dt_ms)
        else:
            _update_time_panel(ch.fig_target_dt, 0, None, None)
    else:
        _update_time_panel(ch.fig_target_raw, 0, None, None, time_domain_shapes)
        _update_time_panel(ch.fig_target_filtered, 0, None, None, time_domain_shapes)
        _set_trace(ch.fig_overlay, 0, [], [])
        _update_time_panel(ch.fig_target_dt, 0, None, None)

    # ── Reference time-domain plots ───────────────────────────────────────
    reference_rate_hz = float("nan")
    ref_t_rel: np.ndarray | None = None
    if reference is not None and reference.timestamps_s.size:
        ref_t_rel = reference.timestamps_s - t_end
        _update_time_panel(ch.fig_reference_raw, 0, ref_t_rel, reference.raw, time_domain_shapes)
        # Overlay: reference trace (index 1)
        _set_trace(ch.fig_overlay, 1, ref_t_rel, reference.raw)

        dt_idx, dt_ms, reference_rate_hz, _ = lsl_interval_ms(reference.timestamps_s)
        if dt_ms.size:
            dt_t_rel = ref_t_rel[dt_idx.astype(int)]
            _update_time_panel(ch.fig_reference_dt, 0, dt_t_rel, dt_ms)
        else:
            _update_time_panel(ch.fig_reference_dt, 0, None, None)
    else:
        _update_time_panel(ch.fig_reference_raw, 0, None, None, time_domain_shapes)
        _set_trace(ch.fig_overlay, 1, [], [])
        _update_time_panel(ch.fig_reference_dt, 0, None, None)

    # Overlay marker shapes
    ch.fig_overlay.update_layout(shapes=time_domain_shapes)

    # ── Clock validation metrics ──────────────────────────────────────────
    target_clock_metrics = (
        clock_validation_metrics(
            target.timestamps_s, target.device_clock_us, clock_scale_to_s=1e-6
        )
        if target is not None and target.timestamps_s.size and target.device_clock_us.size
        else {}
    )
    reference_clock_metrics = (
        clock_validation_metrics(
            reference.timestamps_s, reference.rs485_clock, clock_scale_to_s=1.0
        )
        if reference is not None and reference.timestamps_s.size and reference.rs485_clock.size
        else {}
    )

    # ── XY correlation ────────────────────────────────────────────────────
    ta = cfg.viewer.xy_correlation.time_alignment

    # Use FigureHandles adapter to keep core/alignment.py unchanged
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

    _update_xy_traces(
        ch.fig_xy,
        xy_x, xy_y, xy_t,
        window_seconds=cfg.viewer.window_seconds,
        color=style.xy_color,
        alpha_old=style.xy_alpha_old,
        alpha_new=style.xy_alpha_new,
    )

    # XY axis range
    if xy_x.size > 0:
        if state.xy_lock_max_span:
            state.xy_max_span = update_xy_max_span(state.xy_max_span, xy_x, xy_y)
            span = state.xy_max_span
            ch.fig_xy.update_xaxes(range=[span["xmin"], span["xmax"]], autorange=False)
            ch.fig_xy.update_yaxes(range=[span["ymin"], span["ymax"]], autorange=False)
        else:
            state.xy_max_span = {}
            ch.fig_xy.update_xaxes(autorange=True)
            ch.fig_xy.update_yaxes(autorange=True)

    xy_lock_label = "max-span lock" if state.xy_lock_max_span else "adaptive"
    clipped = "; clipped" if state.xy_reference_shift_clipped else ""
    ch.fig_xy.update_layout(
        title_text=(
            f"Sensor curve: reference force vs target raw count "
            f"[{xy_lock_label}; align={xy_alignment_mode}{clipped}; "
            f"ref_shift={xy_reference_shift_s:+.3f}s]"
        )
    )

    # ── Info panel ────────────────────────────────────────────────────────
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

    # ── Push all chart updates to the browser ─────────────────────────────
    for plot_el, _fig in (
        (ch.plot_target_raw, ch.fig_target_raw),
        (ch.plot_reference_raw, ch.fig_reference_raw),
        (ch.plot_target_filtered, ch.fig_target_filtered),
        (ch.plot_overlay, ch.fig_overlay),
        (ch.plot_target_dt, ch.fig_target_dt),
        (ch.plot_reference_dt, ch.fig_reference_dt),
        (ch.plot_xy, ch.fig_xy),
    ):
        if plot_el is not None:
            plot_el.update()


def clear_chart_data(ch: ChartHandles) -> None:
    """Clear all trace data and reset figure titles/ranges.

    Called when the user presses the clear key or resumes from pause.
    """
    for fig in (
        ch.fig_target_raw,
        ch.fig_reference_raw,
        ch.fig_target_filtered,
        ch.fig_target_dt,
        ch.fig_reference_dt,
    ):
        for trace in fig.data:
            trace.x = []
            trace.y = []
        fig.update_layout(shapes=[])

    # Overlay
    for trace in ch.fig_overlay.data:
        trace.x = []
        trace.y = []
    ch.fig_overlay.update_layout(shapes=[])

    # XY
    for trace in ch.fig_xy.data:
        trace.x = []
        trace.y = []
    ch.fig_xy.update_xaxes(autorange=True)
    ch.fig_xy.update_yaxes(autorange=True)

    # Push to browser
    for plot_el in (
        ch.plot_target_raw,
        ch.plot_reference_raw,
        ch.plot_target_filtered,
        ch.plot_overlay,
        ch.plot_target_dt,
        ch.plot_reference_dt,
        ch.plot_xy,
    ):
        if plot_el is not None:
            plot_el.update()
