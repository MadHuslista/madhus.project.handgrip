# @file
# @brief XY correlation time-alignment and reference interpolation for the viewer.
#
# Pure functions only: no I/O, no global state mutation, no stream-buffer edits.
# Time shifts here are display-only and affect XY rendering logic, not acquisition.

from __future__ import annotations

import logging

import numpy as np

from lsl_viewer.types import FigureHandles, ReferenceWindow, TargetWindow

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _latest_finite_timestamp(values: np.ndarray) -> float:
    # @brief Return the latest finite timestamp from an array.
    # @param values Input timestamp array.
    # @return Last finite value, or nan when no finite value exists.
    arr = np.asarray(values, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    return float(finite[-1]) if finite.size else float("nan")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_xy_reference_time_shift_s(
    handles: FigureHandles,
    target: TargetWindow | None,
    reference: ReferenceWindow | None,
    *,
    alignment_mode: str,
    window_seconds: float,
    manual_reference_shift_s: float,
    max_auto_shift_s: float | None,
    min_auto_shift_s: float,
    snap_threshold_s: float,
    smoothing_alpha: float,
) -> tuple[float, str]:
    # @brief Compute the display-only reference time shift for live XY rendering.
    # @param handles Mutable state container for shift diagnostics.
    # @param target Current target window, or None when not yet available.
    # @param reference Current reference window, or None when not yet available.
    # @param alignment_mode One of: raw_lsl/off/none, manual, tail_aligned_lsl/auto_tail/auto.
    # @param window_seconds Viewer window duration used as default auto-shift clip.
    # @param manual_reference_shift_s Fixed shift applied when mode is manual.
    # @param max_auto_shift_s Maximum absolute auto shift; None means window_seconds.
    # @param min_auto_shift_s Dead-band below which shifts are forced to zero.
    # @param snap_threshold_s Change threshold for snap vs smoothed updates.
    # @param smoothing_alpha EWMA smoothing factor in [0, 1].
    # @return (shift_s, mode_label), where mode_label is one of:
    #         raw_lsl, manual, tail_aligned_hold, tail_aligned_snap, tail_aligned_lsl.
    mode = alignment_mode.strip().lower()

    if mode in {"off", "none", "raw_lsl"}:
        handles.state["xy_reference_time_shift_s"] = 0.0
        handles.state["xy_reference_tail_delta_s"] = 0.0
        return 0.0, "raw_lsl"

    if mode == "manual":
        handles.state["xy_reference_time_shift_s"] = manual_reference_shift_s
        handles.state["xy_reference_tail_delta_s"] = manual_reference_shift_s
        return manual_reference_shift_s, "manual"

    if mode not in {"tail_aligned_lsl", "auto_tail", "auto"}:
        log.warning("Unsupported time_alignment.mode=%r; falling back to raw_lsl", mode)
        handles.state["xy_reference_time_shift_s"] = 0.0
        handles.state["xy_reference_tail_delta_s"] = 0.0
        return 0.0, "raw_lsl"

    # ── Tail-aligned auto-correction ─────────────────────────────────────
    if target is None or reference is None or target.timestamps_s.size == 0 or reference.timestamps_s.size == 0:
        previous = float(handles.state.get("xy_reference_time_shift_s", 0.0))
        return previous, "tail_aligned_hold"

    target_tail = _latest_finite_timestamp(target.timestamps_s)
    reference_tail = _latest_finite_timestamp(reference.timestamps_s)
    if not np.isfinite(target_tail) or not np.isfinite(reference_tail):
        previous = float(handles.state.get("xy_reference_time_shift_s", 0.0))
        return previous, "tail_aligned_hold"

    measured_shift = float(target_tail - reference_tail)
    handles.state["xy_reference_tail_delta_s"] = measured_shift

    max_shift = abs(float(max_auto_shift_s)) if max_auto_shift_s is not None else float(window_seconds)
    if max_shift > 0 and abs(measured_shift) > max_shift:
        clipped_shift = float(np.clip(measured_shift, -max_shift, max_shift))
        handles.state["xy_reference_shift_clipped"] = True
    else:
        clipped_shift = measured_shift
        handles.state["xy_reference_shift_clipped"] = False

    if abs(clipped_shift) < abs(float(min_auto_shift_s)):
        clipped_shift = 0.0

    previous = float(handles.state.get("xy_reference_time_shift_s", clipped_shift))
    alpha = float(np.clip(smoothing_alpha, 0.0, 1.0))

    if abs(clipped_shift - previous) >= float(snap_threshold_s):
        shift = clipped_shift
        mode_label = "tail_aligned_snap"
    else:
        shift = previous + alpha * (clipped_shift - previous)
        mode_label = "tail_aligned_lsl"

    handles.state["xy_reference_time_shift_s"] = float(shift)
    return float(shift), mode_label


def interpolate_reference_to_target(
    target: TargetWindow | None,
    reference: ReferenceWindow | None,
    max_reference_gap_s: float,
    *,
    reference_time_shift_s: float = 0.0,
    target_signal: str = "raw",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # @brief Build XY pairs by interpolating reference samples on target timestamps.
    #
    # Output convention:
    # - x: interpolated reference signal
    # - y: target signal (raw or filtered)
    # - t: target timestamps used for pairing/fading
    #
    # @param target Current target window, or None.
    # @param reference Current reference window, or None.
    # @param max_reference_gap_s Maximum nearest-neighbor gap allowed for valid XY points.
    # @param reference_time_shift_s Display-only shift applied to reference timestamps.
    # @param target_signal Target channel selector: raw or filtered.
    # @return (x, y, t) float64 arrays; returns empty arrays on invalid or non-overlapping data.
    _empty = (
        np.array([], dtype=np.float64),
        np.array([], dtype=np.float64),
        np.array([], dtype=np.float64),
    )

    if target is None or reference is None:
        return _empty
    if target.timestamps_s.size == 0 or reference.timestamps_s.size < 2:
        return _empty

    ref_t = np.asarray(reference.timestamps_s, dtype=np.float64) + float(reference_time_shift_s)
    ref_y = np.asarray(reference.raw, dtype=np.float64)
    target_t = np.asarray(target.timestamps_s, dtype=np.float64)
    target_y = (
        np.asarray(target.filtered, dtype=np.float64)
        if str(target_signal).strip().lower() == "filtered"
        else np.asarray(target.raw, dtype=np.float64)
    )

    valid_ref = np.isfinite(ref_t) & np.isfinite(ref_y)
    ref_t = ref_t[valid_ref]
    ref_y = ref_y[valid_ref]
    if ref_t.size < 2:
        return _empty

    order = np.argsort(ref_t)
    ref_t = ref_t[order]
    ref_y = ref_y[order]
    unique_mask = np.concatenate([[True], np.diff(ref_t) > 0])
    ref_t = ref_t[unique_mask]
    ref_y = ref_y[unique_mask]
    if ref_t.size < 2:
        return _empty

    inside = (
        (target_t >= ref_t[0])
        & (target_t <= ref_t[-1])
        & np.isfinite(target_y)
        & np.isfinite(target_t)
    )
    if not np.any(inside):
        return _empty

    candidate_t = target_t[inside]
    candidate_target_y = target_y[inside]
    nearest_right = np.searchsorted(ref_t, candidate_t, side="left")
    nearest_right = np.clip(nearest_right, 0, ref_t.size - 1)
    nearest_left = np.clip(nearest_right - 1, 0, ref_t.size - 1)
    nearest_gap = np.minimum(
        np.abs(candidate_t - ref_t[nearest_left]),
        np.abs(ref_t[nearest_right] - candidate_t),
    )
    valid_gap = nearest_gap <= float(max_reference_gap_s)
    if not np.any(valid_gap):
        return _empty

    selected_t = candidate_t[valid_gap]
    selected_target_y = candidate_target_y[valid_gap]
    ref_at_target = np.interp(selected_t, ref_t, ref_y)
    finite = (
        np.isfinite(ref_at_target)
        & np.isfinite(selected_target_y)
        & np.isfinite(selected_t)
    )
    return ref_at_target[finite], selected_target_y[finite], selected_t[finite]
