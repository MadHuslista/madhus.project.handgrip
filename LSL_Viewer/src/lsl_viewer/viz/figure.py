"""Matplotlib figure initialisation and axis utility functions.

All public functions receive ``cfg`` (the Hydra config) and/or explicit
parameters so that no module-level globals are needed for visual constants.
Colors and style values come from ``cfg.viewer.style``.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from lsl_viewer.types import FigureHandles
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from omegaconf import DictConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Axis limit helpers  (pure — no side effects)
# ---------------------------------------------------------------------------

def _finite_xy(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def _compute_axis_limits(
    x: np.ndarray, y: np.ndarray, margin_ratio: float = 0.05
) -> tuple[float, float, float, float] | None:
    x, y = _finite_xy(
        np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    )
    if y.size == 0 or x.size == 0:
        return None

    ymin = float(np.nanmin(y))
    ymax = float(np.nanmax(y))
    if math.isclose(ymin, ymax):
        span = max(1.0, abs(ymin) * 0.05)
        ymin -= span
        ymax += span
    else:
        margin = (ymax - ymin) * margin_ratio
        ymin -= margin
        ymax += margin

    xmin = float(np.nanmin(x))
    xmax = float(np.nanmax(x))
    if math.isclose(xmin, xmax):
        span = max(1.0, abs(xmin) * 0.05)
        xmin -= span
        xmax += span
    else:
        margin = (xmax - xmin) * margin_ratio
        xmin -= margin
        xmax += margin

    return xmin, xmax, ymin, ymax


# ---------------------------------------------------------------------------
# Axis update helpers  (side effects: calls ax.set_xlim / set_ylim)
# ---------------------------------------------------------------------------

def update_axis(ax: Any, x: np.ndarray, y: np.ndarray, margin_ratio: float = 0.05) -> None:
    """Set axis limits to fit (x, y) data with a proportional margin."""
    limits = _compute_axis_limits(x, y, margin_ratio=margin_ratio)
    if limits is None:
        return
    xmin, xmax, ymin, ymax = limits
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)


def update_axis_expand_only(
    ax: Any,
    x: np.ndarray,
    y: np.ndarray,
    state: dict[str, Any],
    state_key: str,
    margin_ratio: float = 0.05,
) -> None:
    """Set axis limits that only grow — never shrink — across calls.

    Used for the XY lock-max-span mode: once a large range has been
    seen it is preserved until the user presses the clear key.
    """
    limits = _compute_axis_limits(x, y, margin_ratio=margin_ratio)
    if limits is None:
        return
    xmin, xmax, ymin, ymax = limits
    axis_limits = state.setdefault("axis_expand_only_limits", {})
    previous = axis_limits.get(state_key)
    if previous is None:
        locked = {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax}
    else:
        locked = {
            "xmin": min(float(previous["xmin"]), xmin),
            "xmax": max(float(previous["xmax"]), xmax),
            "ymin": min(float(previous["ymin"]), ymin),
            "ymax": max(float(previous["ymax"]), ymax),
        }
    axis_limits[state_key] = locked
    ax.set_xlim(locked["xmin"], locked["xmax"])
    ax.set_ylim(locked["ymin"], locked["ymax"])


# ---------------------------------------------------------------------------
# Artist reset
# ---------------------------------------------------------------------------

def clear_plot_artists(handles: FigureHandles, reset_axes: bool = True) -> None:
    """Clear all plot artists and optionally reset axis limits."""
    for artist in handles.artists.values():
        if isinstance(artist, LineCollection):
            artist.set_segments([])
            artist.set_colors([])
        elif hasattr(artist, "set_data"):
            artist.set_data([], [])
    handles.state.setdefault("axis_expand_only_limits", {}).clear()
    if reset_axes:
        for key, ax in handles.axes.items():
            if key == "info":
                continue
            ax.set_xlim(0.0, 1.0)
            ax.set_ylim(-1.0, 1.0)
    if hasattr(handles.fig, "canvas"):
        handles.fig.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Figure initialisation
# ---------------------------------------------------------------------------

def init_figure(cfg: DictConfig) -> FigureHandles:
    """Create the 8-panel matplotlib figure and wire up keyboard callbacks.

    Panel layout (5 rows × 2 columns):
    ┌──────────────────────────────────┐
    │ row 0: info text (full width)    │
    ├──────────────┬───────────────────┤
    │ row 1L: target raw  │ 1R: ref raw│
    ├──────────────┼───────────────────┤
    │ row 2L: tgt filtered│ 2R: overlay│
    ├──────────────┼───────────────────┤
    │ row 3L: tgt dt │ 3R: ref dt     │
    ├──────────────┴───────────────────┤
    │ row 4: XY scatter (full width)   │
    └──────────────────────────────────┘
    """
    style = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    dt_unit = cfg.viewer.dt_unit_label
    grid_alpha = style.grid_alpha

    fig = plt.figure(figsize=(14, 13), constrained_layout=False)
    gs = fig.add_gridspec(
        5,
        2,
        height_ratios=[1.15, 2.0, 2.0, 2.0, 2.4],
        hspace=0.58,
        wspace=0.30,
    )
    axes: dict[str, Any] = {
        "info": fig.add_subplot(gs[0, :]),
        "target_raw": fig.add_subplot(gs[1, 0]),
        "reference_raw": fig.add_subplot(gs[1, 1]),
        "target_filtered": fig.add_subplot(gs[2, 0]),
        "overlay": fig.add_subplot(gs[2, 1]),
        "target_dt": fig.add_subplot(gs[3, 0]),
        "reference_dt": fig.add_subplot(gs[3, 1]),
        "xy": fig.add_subplot(gs[4, :]),
    }

    artists: dict[str, Any] = {}
    axes["info"].axis("off")
    (artists["target_raw"],) = axes["target_raw"].plot(
        [], [], color=style.raw_color, lw=1.0, label="target raw"
    )
    (artists["reference_raw"],) = axes["reference_raw"].plot(
        [], [], color=style.reference_color, lw=1.0, label="reference raw"
    )
    (artists["target_filtered"],) = axes["target_filtered"].plot(
        [], [], color=style.filtered_color, lw=1.2, label="target filtered"
    )
    (artists["overlay_target"],) = axes["overlay"].plot(
        [], [], color=style.raw_color, lw=1.0, label="target raw"
    )
    (artists["overlay_reference"],) = axes["overlay"].plot(
        [], [], color=style.reference_color, linestyle="--", lw=1.0, label="reference raw"
    )
    (artists["target_dt"],) = axes["target_dt"].plot(
        [], [], color=style.timing_color, lw=1.0, label="target dt"
    )
    (artists["reference_dt"],) = axes["reference_dt"].plot(
        [], [], color=style.timing_color, lw=1.0, label="reference dt"
    )
    artists["xy"] = LineCollection(
        [], linewidths=style.xy_line_width, label="current window"
    )
    axes["xy"].add_collection(artists["xy"])

    # Axis labels and titles
    axes["target_raw"].set_title("Target raw ADC counts - native irregular samples")
    axes["reference_raw"].set_title("Reference force - native RS485 samples")
    axes["target_filtered"].set_title("Target filtered/current units - display only")
    axes["overlay"].set_title(
        "Time-synchronized engineering-unit overlay on common LSL time axis"
    )
    axes["target_dt"].set_title("Target LSL sample interval")
    axes["reference_dt"].set_title("Reference LSL sample interval")
    axes["xy"].set_title("Sensor curve: reference force vs target raw count")

    for key in ["target_raw", "reference_raw", "target_filtered", "overlay"]:
        axes[key].set_ylabel(f"Force ({force_unit})")
    axes["target_dt"].set_ylabel(f"Interval ({dt_unit})")
    axes["reference_dt"].set_ylabel(f"Interval ({dt_unit})")
    for key in ["target_raw", "reference_raw", "target_filtered", "overlay",
                "target_dt", "reference_dt"]:
        axes[key].set_xlabel("Relative LSL time (s)")
    axes["xy"].set_xlabel(f"Reference force at target timestamps ({force_unit})")
    axes["xy"].set_ylabel(cfg.viewer.target_raw_unit_label)

    for key, ax in axes.items():
        if key == "info":
            continue
        ax.grid(True, alpha=grid_alpha)
        ax.legend(loc="upper right", fontsize=8)

    # Mutable render state
    state: dict[str, Any] = {
        "axis_expand_only_limits": {},
        "xy_lock_max_span": cfg.viewer.xy_correlation.lock_max_span,
        "xy_lock_toggle_key": cfg.viewer.xy_correlation.toggle_key.strip(),
        "clear_plots_key": cfg.viewer.controls.clear_key.strip(),
        "pause_live_key": cfg.viewer.controls.pause_key.strip(),
        "live_paused": False,
        "live_reset_from_latest_window": False,
        "target_live_cutoff_timestamp_s": None,
        "reference_live_cutoff_timestamp_s": None,
        "xy_reference_time_shift_s": 0.0,
        "xy_reference_tail_delta_s": 0.0,
        "xy_reference_shift_clipped": False,
    }
    handles = FigureHandles(fig=fig, axes=axes, artists=artists, state=state)

    # Keyboard callbacks
    def on_key(event: Any) -> None:
        if event.key is None:
            return
        if event.key == state.get("xy_lock_toggle_key"):
            state["xy_lock_max_span"] = not bool(state.get("xy_lock_max_span", False))
            state.setdefault("axis_expand_only_limits", {}).pop("xy", None)
            log.info("XY max-span lock toggled: %s", state["xy_lock_max_span"])
        elif event.key == state.get("clear_plots_key"):
            clear_plot_artists(handles)
            state["live_reset_from_latest_window"] = True
            log.info(
                "Manual plot clear requested; buffered samples will be "
                "dropped on next live update."
            )
        elif event.key == state.get("pause_live_key"):
            state["live_paused"] = not bool(state.get("live_paused", False))
            if not state["live_paused"]:
                clear_plot_artists(handles)
                state["live_reset_from_latest_window"] = True
            log.info("Live pause toggled: %s", state["live_paused"])

    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.subplots_adjust(top=0.96, bottom=0.06, left=0.07, right=0.97, hspace=0.58, wspace=0.30)
    return handles
