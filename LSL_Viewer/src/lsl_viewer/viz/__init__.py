"""Visualisation layer for the handgrip realtime viewer.

NiceGUI + Plotly implementation — replaces the Matplotlib/PyQt5 stack.
The public surface is intentionally minimal; callers (cli.py) import
the runner functions from ``viz.app``.
"""
from lsl_viewer.viz.app import run_live_mode_nicegui, run_replay_mode_nicegui
from lsl_viewer.viz.charts import ChartHandles, build_chart_handles, update_charts
from lsl_viewer.viz.state import compute_axis_limits, update_xy_max_span

__all__ = [
    "run_live_mode_nicegui",
    "run_replay_mode_nicegui",
    "ChartHandles",
    "build_chart_handles",
    "update_charts",
    "compute_axis_limits",
    "update_xy_max_span",
]
