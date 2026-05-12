"""XY correlation time-alignment and reference-interpolation logic.

All functions are **pure**: they operate only on numpy arrays and dicts.
No side effects, no I/O.  The ``FigureHandles.state`` dict is accepted as a
parameter (not imported) so the unit tests need not construct a real figure.
"""
from __future__ import annotations

import logging

import numpy as np

from lsl_viewer.types import FigureHandles, ReferenceWindow, TargetWindow

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _latest_finite_timestamp(values: np.ndarray) -> float:
    """Return the last finite value in *values*, or nan."""
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
    """Return the display-only reference time shift for the live XY plot.

    The native stream buffers and LSL/XDF timestamps are never modified.
    This function only determines the timebase used by the *live* XY panel.

    Parameters
    ----------
    handles:
        Figure state container (mutated: ``xy_reference_time_shift_s``,
        ``xy_reference_tail_delta_s``, ``xy_reference_shift_clipped``).
    target / reference:
        Current window data; may be ``None`` if a stream has no data yet.
    alignment_mode:
        One of ``"raw_lsl"``, ``"off"``, ``"none"``, ``"manual"``,
        ``"tail_aligned_lsl"``, ``"auto_tail"``, ``"auto"``.
    window_seconds:
        Viewer window duration; used as the default ``max_auto_shift_s``.
    manual_reference_shift_s:
        Fixed shift applied when ``alignment_mode == "manual"``.
    max_auto_shift_s:
        Clip magnitude of auto-computed shift; ``None`` means use ``window_seconds``.
    min_auto_shift_s:
        Shifts smaller than this are rounded to zero (dead-band).
    snap_threshold_s:
        If the correction changes by more than this amount, snap immediately
        instead of smoothing (avoids seconds-long tail-alignment lag).
    smoothing_alpha:
        EWA smoothing coefficient in ``[0, 1]``.  ``1.0`` = no smoothing.

    Returns
    -------
    (shift_s, mode_label):
        ``shift_s`` is the seconds to add to reference LSL timestamps for
        display purposes; ``mode_label`` is a short diagnostic string.
    """
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
    if (
        target is None
        or reference is None
        or target.timestamps_s.size == 0
        or reference.timestamps_s.size == 0
    ):
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
    """Return XY samples with reference interpolated onto target timestamps.

    Output layout (matching original viewer convention):
    ``x`` = reference/RS485 force at target timestamps (interpolated);
    ``y`` = target handgrip signal (raw or filtered);
    ``t`` = target timestamps used for XY pairing (for time-fading the LineCollection).

    ``reference_time_shift_s`` is a display-only correction applied to the
    reference LSL timestamps before interpolation.  Native buffers are unchanged.

    Parameters
    ----------
    target / reference:
        Current window data.
    max_reference_gap_s:
        Maximum gap in the reference stream before a target point is excluded
        from the XY scatter.
    reference_time_shift_s:
        Seconds to add to reference timestamps for alignment purposes.
    target_signal:
        Which target channel to use on the y-axis: ``"raw"`` or ``"filtered"``.

    Returns
    -------
    (x, y, t):
        Three 1-D float64 arrays of identical length.  Empty on any error or
        when no overlapping data exists.
    """
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
