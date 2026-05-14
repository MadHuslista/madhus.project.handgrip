"""Info-panel text rendering for the NiceGUI viewer.

All functions here are **pure**: they accept data and return strings.
No side effects, no I/O.  The output is consumed by ``viz/panels.py``
which calls ``info_label.set_text()``.

The 4-column monospace layout (SOURCE/MODE | TARGET | REFERENCE | METRICS)
is preserved exactly from the original ``viz/plots.py`` implementation.
"""
from __future__ import annotations

import numpy as np
from omegaconf import DictConfig

from lsl_viewer.types import DualWindow, ViewerState

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _format_latest(value: float, suffix: str = "", precision: int = 3) -> str:
    if not np.isfinite(value):
        return "nan"
    return f"{value:.{precision}f}{suffix}"


def _zip_columns(*columns: str, pad: int = 3) -> str:
    """Horizontally concatenate multi-line text columns."""
    split_cols = [col.splitlines() for col in columns]
    widths = [max((len(line) for line in lines), default=0) for lines in split_cols]
    height = max((len(lines) for lines in split_cols), default=0)
    rows: list[str] = []
    for row_idx in range(height):
        row_parts = []
        for lines, width in zip(split_cols, widths, strict=False):
            text = lines[row_idx] if row_idx < len(lines) else ""
            row_parts.append(text.ljust(width + pad))
        rows.append("".join(row_parts).rstrip())
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_info_text(
    window: DualWindow,
    state: ViewerState,
    cfg: DictConfig,
    *,
    mode: str,
    source_name: str,
    source_type: str,
    xy_reference_shift_s: float,
    xy_alignment_mode: str,
    marker_count: int,
    target_rate_hz: float,
    reference_rate_hz: float,
    target_clock_metrics: dict[str, float],
    reference_clock_metrics: dict[str, float],
    xy_pair_count: int,
    target_new_samples: int | None = None,
    reference_new_samples: int | None = None,
    replay_progress_text: str | None = None,
) -> str:
    """Render the 4-column info panel text.

    Pure function — returns a formatted string suitable for ``<pre>`` rendering.
    All parameters are passed explicitly; no global state is read.
    """
    target = window.target
    reference = window.reference
    force_unit = cfg.viewer.force_unit_label

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

    live_state_label = "paused" if state.live_paused else "running"
    xy_lock_label = "max-span lock" if state.xy_lock_max_span else "adaptive"
    xy_toggle_key = str(cfg.viewer.xy_correlation.toggle_key).strip()
    toggle_hint = f" | press '{xy_toggle_key}' to toggle" if xy_toggle_key else ""
    clipped_suffix = "; clipped" if state.xy_reference_shift_clipped else ""

    col_source = (
        "SOURCE/MODE\n"
        f"source : {source_name}\n"
        f"type   : {source_type}\n"
        f"mode   : {mode}\n"
        f"state  : {live_state_label}\n"
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
        "clk-LSL: "
        f"{_format_latest(float(reference_clock_metrics.get('median_clock_minus_lsl_s', float('nan'))), ' s', 4)}\n"
        "spanerr: "
        f"{_format_latest(float(reference_clock_metrics.get('clock_vs_lsl_span_error_ms', float('nan'))), ' ms', 2)}\n"
        f"pairs  : {xy_pair_count}"
    )
    col_metrics = (
        f"METRICS\n"
        f"XY     : {xy_lock_label}{toggle_hint}\n"
        f"align  : {xy_alignment_mode}{clipped_suffix}\n"
        f"xy sh. : {xy_reference_shift_s:+.3f} s\n"
        f"tail \u0394 : {state.xy_reference_tail_delta_s:+.3f} s\n"
        f"clip   : {state.xy_reference_shift_clipped}\n"
        f"window : {cfg.viewer.window_seconds:.1f} s\n"
        f"marks  : {marker_count}\n"
        f"keys   : clear={cfg.viewer.controls.clear_key} "
        f"pause={cfg.viewer.controls.pause_key} "
        f"xy={xy_toggle_key}"
    )
    if target_new_samples is not None or reference_new_samples is not None:
        col_metrics += f"\nnew tgt: {target_new_samples}\nnew ref: {reference_new_samples}"
    elif replay_progress_text:
        col_metrics += "\n" + replay_progress_text

    return _zip_columns(col_source, col_target, col_reference, col_metrics)
