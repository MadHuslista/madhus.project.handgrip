"""Per-frame plot update logic and info-panel rendering.

``update_plots()`` is the central render function called once per refresh
cycle.  It delegates to helpers in :mod:`lsl_viewer.core.timing`,
:mod:`lsl_viewer.core.alignment`, and :mod:`lsl_viewer.viz.markers`.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from lsl_viewer.core.alignment import (
    compute_xy_reference_time_shift_s,
    interpolate_reference_to_target,
)
from lsl_viewer.core.timing import clock_validation_metrics, lsl_interval_ms
from lsl_viewer.types import DualWindow, FigureHandles, ReferenceWindow, TargetWindow
from lsl_viewer.viz.figure import update_axis, update_axis_expand_only
from lsl_viewer.viz.markers import draw_marker_overlays
from matplotlib import colors as mcolors
from matplotlib.collections import LineCollection
from omegaconf import DictConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _format_latest(value: float, suffix: str = "", precision: int = 3) -> str:
    if not np.isfinite(value):
        return "nan"
    return f"{value:.{precision}f}{suffix}"


def _zip_columns(*columns: str, pad: int = 3) -> str:
    """Horizontally concatenate multi-line text columns for the info panel."""
    split_cols = [col.splitlines() for col in columns]
    widths = [max((len(line) for line in lines), default=0) for lines in split_cols]
    height = max((len(lines) for lines in split_cols), default=0)
    rows: list[str] = []
    for row_idx in range(height):
        row_parts = []
        for lines, width in zip(split_cols, widths):
            text = lines[row_idx] if row_idx < len(lines) else ""
            row_parts.append(text.ljust(width + pad))
        rows.append("".join(row_parts).rstrip())
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Info-panel rendering
# ---------------------------------------------------------------------------

def _render_info_panel(handles: FigureHandles, text: str) -> None:
    ax = handles.axes["info"]
    for artist in list(ax.texts):
        artist.remove()
    ax.axis("off")
    ax.text(
        0.02, 0.94, text,
        va="top", ha="left",
        family="monospace", fontsize=8,
        transform=ax.transAxes,
    )


# ---------------------------------------------------------------------------
# XY LineCollection renderer
# ---------------------------------------------------------------------------

def _update_xy_line_collection(
    line_collection: LineCollection,
    x: np.ndarray,
    y: np.ndarray,
    timestamps_s: np.ndarray,
    *,
    window_seconds: float,
    color: str,
    alpha_old: float,
    alpha_new: float,
) -> None:
    """Render the XY correlation as connected, time-faded line segments."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    t = np.asarray(timestamps_s, dtype=np.float64)
    if x.size < 2 or y.size < 2 or t.size < 2:
        line_collection.set_segments([])
        line_collection.set_colors([])
        return

    order = np.argsort(t)
    x = x[order]
    y = y[order]
    t = t[order]
    points = np.column_stack([x, y])
    segments = np.stack([points[:-1], points[1:]], axis=1)

    rgba = np.tile(mcolors.to_rgba(color), (segments.shape[0], 1))
    if np.isfinite(window_seconds) and window_seconds > 0 and np.isfinite(t[-1]):
        segment_t = t[1:]
        age_s = np.clip(t[-1] - segment_t, 0.0, float(window_seconds))
        freshness = 1.0 - (age_s / float(window_seconds))
        rgba[:, 3] = float(alpha_old) + freshness * (float(alpha_new) - float(alpha_old))
    else:
        rgba[:, 3] = np.linspace(float(alpha_old), float(alpha_new), segments.shape[0])

    line_collection.set_segments(segments)
    line_collection.set_colors(rgba)


# ---------------------------------------------------------------------------
# Main per-frame update
# ---------------------------------------------------------------------------

def update_plots(
    handles: FigureHandles,
    window: DualWindow,
    cfg: DictConfig,
    *,
    mode: str,
    source_name: str,
    source_type: str,
    target_new_samples: int | None = None,
    reference_new_samples: int | None = None,
    replay_progress_text: str | None = None,
) -> None:
    """Update all plot artists for one render cycle.

    Parameters
    ----------
    handles:
        Figure handles returned by :func:`~lsl_viewer.viz.figure.init_figure`.
    window:
        Current data window (live fetch or replay slice).
    cfg:
        Hydra config; accessed for unit labels, style, alignment settings, etc.
    mode:
        One of the mode strings used for the info panel (e.g. ``"live"``,
        ``"csv_replay"``).
    source_name / source_type:
        Descriptive strings shown in the info panel.
    target_new_samples / reference_new_samples:
        Live-mode new-sample counters; shown in the metrics column.
    replay_progress_text:
        Replay-mode progress string (e.g. ``"time : 3.14/10.00 s"``).
    """
    target: TargetWindow | None = window.target
    reference: ReferenceWindow | None = window.reference
    style = cfg.viewer.style
    force_unit = cfg.viewer.force_unit_label
    dt_unit = cfg.viewer.dt_unit_label

    # ── Compute t_end for relative time axis ─────────────────────────────
    latest_ts: list[float] = []
    if target is not None and target.timestamps_s.size:
        latest_ts.append(float(np.nanmax(target.timestamps_s)))
    if reference is not None and reference.timestamps_s.size:
        latest_ts.append(float(np.nanmax(reference.timestamps_s)))
    t_end = max(latest_ts) if latest_ts else 0.0

    # ── Target plots ──────────────────────────────────────────────────────
    target_rate_hz = float("nan")
    target_mean_dt_ms = float("nan")
    if target is not None and target.timestamps_s.size:
        target_t_rel = target.timestamps_s - t_end
        handles.artists["target_raw"].set_data(target_t_rel, target.raw)
        handles.artists["target_filtered"].set_data(target_t_rel, target.filtered)
        handles.artists["overlay_target"].set_data(target_t_rel, target.filtered)
        update_axis(handles.axes["target_raw"], target_t_rel, target.raw)
        update_axis(handles.axes["target_filtered"], target_t_rel, target.filtered)
        dt_idx, dt_ms, target_rate_hz, target_mean_dt_ms = lsl_interval_ms(
            target.timestamps_s
        )
        if dt_ms.size:
            handles.artists["target_dt"].set_data(
                target_t_rel[dt_idx.astype(int)], dt_ms
            )
            update_axis(
                handles.axes["target_dt"], target_t_rel[dt_idx.astype(int)], dt_ms
            )
    else:
        handles.artists["target_raw"].set_data([], [])
        handles.artists["target_filtered"].set_data([], [])
        handles.artists["overlay_target"].set_data([], [])
        handles.artists["target_dt"].set_data([], [])

    # ── Reference plots ───────────────────────────────────────────────────
    reference_rate_hz = float("nan")
    reference_mean_dt_ms = float("nan")
    if reference is not None and reference.timestamps_s.size:
        ref_t_rel = reference.timestamps_s - t_end
        handles.artists["reference_raw"].set_data(ref_t_rel, reference.raw)
        handles.artists["overlay_reference"].set_data(ref_t_rel, reference.raw)
        update_axis(handles.axes["reference_raw"], ref_t_rel, reference.raw)
        dt_idx, dt_ms, reference_rate_hz, reference_mean_dt_ms = lsl_interval_ms(
            reference.timestamps_s
        )
        if dt_ms.size:
            handles.artists["reference_dt"].set_data(
                ref_t_rel[dt_idx.astype(int)], dt_ms
            )
            update_axis(
                handles.axes["reference_dt"],
                ref_t_rel[dt_idx.astype(int)],
                dt_ms,
            )
    else:
        handles.artists["reference_raw"].set_data([], [])
        handles.artists["overlay_reference"].set_data([], [])
        handles.artists["reference_dt"].set_data([], [])

    # ── Overlay axis limits ───────────────────────────────────────────────
    overlay_x: list[np.ndarray] = []
    overlay_y: list[np.ndarray] = []
    if target is not None and target.timestamps_s.size:
        target_t_rel = target.timestamps_s - t_end
        valid = np.isfinite(target_t_rel) & np.isfinite(target.raw)
        overlay_x.append(target_t_rel[valid])
        overlay_y.append(target.filtered[valid])
    if reference is not None and reference.timestamps_s.size:
        ref_t_rel = reference.timestamps_s - t_end
        valid = np.isfinite(ref_t_rel) & np.isfinite(reference.raw)
        overlay_x.append(ref_t_rel[valid])
        overlay_y.append(reference.raw[valid])
    if overlay_x and overlay_y:
        update_axis(
            handles.axes["overlay"],
            np.concatenate(overlay_x),
            np.concatenate(overlay_y),
        )

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
        if reference is not None
        and reference.timestamps_s.size
        and reference.rs485_clock.size
        else {}
    )

    # ── XY correlation ────────────────────────────────────────────────────
    ta = cfg.viewer.xy_correlation.time_alignment
    xy_reference_shift_s, xy_alignment_mode = compute_xy_reference_time_shift_s(
        handles,
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
    xy_x, xy_y, xy_t = interpolate_reference_to_target(
        target,
        reference,
        cfg.alignment.max_reference_gap_s,
        reference_time_shift_s=xy_reference_shift_s,
        target_signal=cfg.viewer.xy_correlation.target_signal,
    )
    _update_xy_line_collection(
        handles.artists["xy"],
        xy_x,
        xy_y,
        xy_t,
        window_seconds=cfg.viewer.window_seconds,
        color=style.xy_color,
        alpha_old=style.xy_alpha_old,
        alpha_new=style.xy_alpha_new,
    )

    xy_lock_max_span = bool(handles.state.get("xy_lock_max_span", False))
    xy_mode = "max-span lock" if xy_lock_max_span else "adaptive"
    xy_toggle_key = str(handles.state.get("xy_lock_toggle_key", "")).strip()
    xy_toggle_hint = f" | press '{xy_toggle_key}' to toggle" if xy_toggle_key else ""
    clipped_suffix = (
        "; clipped" if bool(handles.state.get("xy_reference_shift_clipped", False)) else ""
    )
    handles.axes["xy"].set_title(
        f"Sensor curve: reference force vs target raw count "
        f"[{xy_mode}; align={xy_alignment_mode}{clipped_suffix}; "
        f"ref_shift={xy_reference_shift_s:+.3f}s{xy_toggle_hint}]"
    )
    if xy_x.size:
        if xy_lock_max_span:
            update_axis_expand_only(
                handles.axes["xy"], xy_x, xy_y, handles.state, "xy"
            )
        else:
            handles.state.setdefault("axis_expand_only_limits", {}).pop("xy", None)
            update_axis(handles.axes["xy"], xy_x, xy_y)

    # ── Calibration markers ───────────────────────────────────────────────
    marker_count = draw_marker_overlays(handles, cfg, t_end)

    # ── Info panel ────────────────────────────────────────────────────────
    live_state = "paused" if bool(handles.state.get("live_paused", False)) else "running"
    latest_target_raw = (
        float(target.raw[-1]) if target is not None and target.raw.size else float("nan")
    )
    latest_target_filtered = (
        float(target.filtered[-1])
        if target is not None and target.filtered.size
        else float("nan")
    )
    latest_target_clock = (
        float(target.device_clock_us[-1])
        if target is not None and target.device_clock_us.size
        else float("nan")
    )
    latest_reference_raw = (
        float(reference.raw[-1])
        if reference is not None and reference.raw.size
        else float("nan")
    )
    latest_reference_clock = (
        float(reference.rs485_clock[-1])
        if reference is not None and reference.rs485_clock.size
        else float("nan")
    )

    col_source = (
        "SOURCE/MODE\n"
        f"source : {source_name}\n"
        f"type   : {source_type}\n"
        f"mode   : {mode}\n"
        f"state  : {live_state}\n"
        "sync   : native streams + LSL timestamps\n"
        "XY     : ref\u2192target interpolation"
    )
    col_target = (
        f"TARGET (raw=count, filt={force_unit})\n"
        f"raw    : {_format_latest(latest_target_raw)}\n"
        f"filt   : {_format_latest(latest_target_filtered)}\n"
        f"clock  : {_format_latest(latest_target_clock, ' us', 0)}\n"
        f"LSL Hz : {_format_latest(target_rate_hz, ' Hz', 2)}\n"
        f"dev Hz : {_format_latest(float(target_clock_metrics.get('clock_rate_hz', float('nan'))), ' Hz', 2)}\n"
        f"dt err : {_format_latest(float(target_clock_metrics.get('median_dt_error_ms', float('nan'))), ' ms', 3)}"
    )
    col_reference = (
        f"REFERENCE ({force_unit})\n"
        f"raw    : {_format_latest(latest_reference_raw)}\n"
        f"clock  : {_format_latest(latest_reference_clock, ' s', 6)}\n"
        f"LSL Hz : {_format_latest(reference_rate_hz, ' Hz', 2)}\n"
        f"clk Hz : {_format_latest(float(reference_clock_metrics.get('clock_rate_hz', float('nan'))), ' Hz', 2)}\n"
        f"clk-LSL: {_format_latest(float(reference_clock_metrics.get('median_clock_minus_lsl_s', float('nan'))), ' s', 4)}\n"
        f"spanerr: {_format_latest(float(reference_clock_metrics.get('clock_vs_lsl_span_error_ms', float('nan'))), ' ms', 2)}\n"
        f"pairs  : {xy_x.size}"
    )
    col_metrics = "METRICS\n"
    if target_new_samples is not None or reference_new_samples is not None:
        col_metrics += f"new tgt: {target_new_samples}\nnew ref: {reference_new_samples}\n"
    elif replay_progress_text:
        col_metrics += replay_progress_text + "\n"
    col_metrics += (
        f"window : {cfg.viewer.window_seconds:.1f} s\n"
        f"xy sh. : {xy_reference_shift_s:+.3f} s\n"
        f"tail \u0394 : {float(handles.state.get('xy_reference_tail_delta_s', 0.0)):+.3f} s\n"
        f"clip   : {bool(handles.state.get('xy_reference_shift_clipped', False))}\n"
        f"marks  : {marker_count}\n"
        f"keys   : clean={handles.state.get('clear_plots_key') or 'off'} "
        f"pause={handles.state.get('pause_live_key') or 'off'} "
        f"xy={handles.state.get('xy_lock_toggle_key') or 'off'}"
    )

    _render_info_panel(
        handles, _zip_columns(col_source, col_target, col_reference, col_metrics)
    )
    handles.fig.canvas.draw_idle()
