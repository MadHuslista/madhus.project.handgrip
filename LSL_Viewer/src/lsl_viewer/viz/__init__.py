# @file
# @brief Visualisation layer - NiceGUI + Apache ECharts (v0.5.0).
##
# Replaces the Matplotlib/PyQt5 stack and the NiceGUI+Plotly stack. Public
# surface is intentionally minimal; callers import the runner functions from
# viz.app directly.
from lsl_viewer.viz.app import run_live_mode_nicegui, run_replay_mode_nicegui
from lsl_viewer.viz.charts import ChartHandles, build_chart_handles, update_charts
from lsl_viewer.viz.state import compute_axis_limits, update_xy_span

__all__ = [
    "run_live_mode_nicegui",
    "run_replay_mode_nicegui",
    "ChartHandles",
    "build_chart_handles",
    "update_charts",
    "compute_axis_limits",
    "update_xy_span",
]
