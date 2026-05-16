"""Plotly figure construction for the live signal plot.

Dependency chain: state, core/signals, core/sampling
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import plotly.graph_objects as go

from rs485_gui.core.sampling import downsample_points_for_render
from rs485_gui.core.signals import (
    extract_signal_value,
    get_plot_signal_key,
    get_plot_signal_label,
)

if TYPE_CHECKING:
    from rs485_gui.state import AppState

try:
    import numpy as np  # type: ignore[import]
except Exception:
    np = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


# @brief Build plot figure.
#
#  @param app_state Parameter description.
#  @return Constructed object for this operation.
def build_plot_figure(app_state: AppState) -> go.Figure:
    """Build a Plotly Figure from the current frame history in *app_state*."""
    fig = go.Figure()
    cfg = app_state.cfg
    signal_key = get_plot_signal_key(cfg)

    with app_state.frame_lock:
        frames = list(app_state.frame_history)

    points: list[tuple[float, float]] = []
    for frame in frames:
        value = extract_signal_value(frame, signal_key)
        if value is not None:
            points.append((frame.host_ts, value))

    if app_state.mode == "active_send":
        factor = int(cfg.ui.active_send_render_downsample_factor)
    else:
        factor = int(cfg.ui.modbus_rtu_render_downsample_factor)

    max_render_points = int(cfg.ui.max_render_plot_points)
    render_points = downsample_points_for_render(
        points, factor=factor, max_points=max_render_points
    )

    if render_points:
        if np is not None:
            arr = np.asarray(render_points, dtype=np.float64)
            t0 = float(arr[0, 0])
            xs = (arr[:, 0] - t0).tolist()
            ys = arr[:, 1].tolist()
        else:
            t0 = render_points[0][0]
            xs = [ts - t0 for ts, _ in render_points]
            ys = [val for _, val in render_points]

        trace_type = str(cfg.ui.plot_trace_type).lower()
        trace_cls = (
            go.Scattergl if trace_type == "scattergl" and hasattr(go, "Scattergl") else go.Scatter
        )
        label = get_plot_signal_label(cfg)
        fig.add_trace(
            trace_cls(
                x=xs,
                y=ys,
                mode="lines",
                name=label,
                hovertemplate="t=%{x:.6f}s<br>%{fullData.name}=%{y:.6g}<extra></extra>",
            )
        )

    label = get_plot_signal_label(cfg)
    fig.update_layout(
        title=f"Live signal ({label})",
        xaxis_title="Seconds since current plot window start",
        yaxis_title=label,
        margin=dict(l=20, r=20, t=40, b=20),
        height=int(cfg.ui.plot_height_px),
        template="plotly_white",
        uirevision="plot-x-window",
        transition={"duration": 0},
    )
    fig.update_xaxes(uirevision="plot-x-window")
    fig.update_yaxes(uirevision=f"plot-y:{signal_key}")
    return fig
