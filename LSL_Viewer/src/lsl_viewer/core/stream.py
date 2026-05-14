"""LSL stream connection and live window fetching.

This module is part of the **imperative shell**: it performs real I/O
(network connections to LSL streams, data reads from the mne-lsl buffer).

The layout-from-config helpers and label validation are also here because
they depend on the config structure rather than on any pure math.
"""
from __future__ import annotations

import logging

import numpy as np
from omegaconf import DictConfig

from lsl_viewer.types import (
    DualWindow,
    ReferenceWindow,
    StreamLayout,
    TargetWindow,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def target_layout_from_cfg(cfg: DictConfig) -> StreamLayout:
    """Build a StreamLayout from the channels.target config section."""
    return StreamLayout(
        clock_label=str(cfg.channels.target.clock_label),
        raw_label=str(cfg.channels.target.raw_label),
        filtered_label=str(cfg.channels.target.filtered_label),
    )


def reference_layout_from_cfg(cfg: DictConfig) -> StreamLayout:
    """Build a StreamLayout from the channels.reference config section."""
    return StreamLayout(
        clock_label=str(cfg.channels.reference.clock_label),
        raw_label=str(cfg.channels.reference.raw_label),
        filtered_label=None,
    )


def validate_labels(ch_names: list[str], layout: StreamLayout, role: str) -> None:
    """Raise if any required channel label is absent from the stream."""
    missing = [label for label in layout.picks if label not in ch_names]
    if missing:
        raise RuntimeError(f"{role} stream is missing required channels {missing}. Available channels: {ch_names}")


# ---------------------------------------------------------------------------
# Stream connection
# ---------------------------------------------------------------------------


def build_streams(cfg: DictConfig):
    """Connect to the target and reference LSL streams.

    Requires mne-lsl; raises a clear ``RuntimeError`` if not installed so the
    error is shown before any LSL network activity starts.

    Returns
    -------
    (target_stream, reference_stream, target_layout, reference_layout)
    """
    try:
        from mne_lsl.stream import StreamLSL  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "mne-lsl is required for live streaming. "
            "Install it with: pip install lsl-viewer[live]"
        ) from exc

    target_cfg = cfg.streams.target
    reference_cfg = cfg.streams.reference

    target = StreamLSL(
        bufsize=target_cfg.buffer_samples,
        name=str(target_cfg.name),
        stype=str(target_cfg.stype),
        source_id=None if target_cfg.source_id is None else str(target_cfg.source_id),
    )
    reference = StreamLSL(
        bufsize=reference_cfg.buffer_seconds,
        name=str(reference_cfg.name),
        stype=str(reference_cfg.stype),
        source_id=None
        if reference_cfg.source_id is None
        else str(reference_cfg.source_id),
    )

    target.connect(
        acquisition_delay=target_cfg.acquisition_delay,
        timeout=target_cfg.timeout,
    )
    reference.connect(
        acquisition_delay=reference_cfg.acquisition_delay,
        timeout=reference_cfg.timeout,
    )

    target_layout = target_layout_from_cfg(cfg)
    reference_layout = reference_layout_from_cfg(cfg)
    validate_labels(list(target.ch_names), target_layout, "Target")
    validate_labels(list(reference.ch_names), reference_layout, "Reference")

    log.info(
        "Connected target stream: name=%s type=%s source_id=%s sfreq=%s ch_names=%s",
        target.name,
        target.stype,
        target.source_id,
        target.info["sfreq"],
        target.ch_names,
    )
    log.info(
        "Connected reference stream: name=%s type=%s source_id=%s sfreq=%s ch_names=%s",
        reference.name,
        reference.stype,
        reference.source_id,
        reference.info["sfreq"],
        reference.ch_names,
    )

    if float(target.info["sfreq"]) != 0.0:
        log.warning(
            "Target stream should normally be irregular (sfreq=0). Current sfreq=%s",
            target.info["sfreq"],
        )
    if abs(float(reference.info["sfreq"]) - reference_cfg.expected_rate_hz) > 5.0:
        log.warning(
            "Reference stream sfreq=%s differs from expected_rate_hz=%s.",
            reference.info["sfreq"],
            reference_cfg.expected_rate_hz,
        )

    return target, reference, target_layout, reference_layout


# ---------------------------------------------------------------------------
# Window fetching
# ---------------------------------------------------------------------------

def _stream_data_to_window(
    data: np.ndarray, ts: np.ndarray, role: str
) -> TargetWindow | ReferenceWindow | None:
    """Validate shape and wrap raw stream arrays into a typed window object."""
    if ts.size == 0:
        return None
    timestamps = np.asarray(ts, dtype=np.float64)
    matrix = np.asarray(data, dtype=np.float64)
    if matrix.ndim != 2:
        log.warning(
            "%s stream: unexpected data ndim=%d (expected 2); skipping window",
            role,
            matrix.ndim,
        )
        return None
    if role == "target":
        if matrix.shape[0] < 3:
            log.warning(
                "Target stream: expected ≥3 channels, got %d; skipping window",
                matrix.shape[0],
            )
            return None
        return TargetWindow(
            timestamps_s=timestamps,
            device_clock_us=matrix[0],
            raw=matrix[1],
            filtered=matrix[2],
        )
    # reference
    if matrix.shape[0] < 2:
        log.warning(
            "Reference stream: expected ≥2 channels, got %d; skipping window",
            matrix.shape[0],
        )
        return None
    return ReferenceWindow(
        timestamps_s=timestamps,
        rs485_clock=matrix[0],
        raw=matrix[1],
    )


def _slice_target_window(window: TargetWindow, t_start: float) -> TargetWindow | None:
    mask = np.asarray(window.timestamps_s) >= float(t_start)
    if not np.any(mask):
        return None
    return TargetWindow(
        timestamps_s=window.timestamps_s[mask],
        device_clock_us=window.device_clock_us[mask],
        raw=window.raw[mask],
        filtered=window.filtered[mask],
    )


def _slice_reference_window(
    window: ReferenceWindow, t_start: float
) -> ReferenceWindow | None:
    mask = np.asarray(window.timestamps_s) >= float(t_start)
    if not np.any(mask):
        return None
    return ReferenceWindow(
        timestamps_s=window.timestamps_s[mask],
        rs485_clock=window.rs485_clock[mask],
        raw=window.raw[mask],
    )


def fetch_live_window(
    target_stream,
    reference_stream,
    cfg: DictConfig,
    target_layout: StreamLayout,
    reference_layout: StreamLayout,
) -> DualWindow | None:
    """Read the current buffer from both LSL streams and return a DualWindow.

    The two streams are sampled independently.  The returned window covers
    the common visible interval ``[t_end - window_seconds, t_end]`` aligned
    on the latest timestamp seen across both streams.
    """
    target_data, target_ts = target_stream.get_data(
        winsize=cfg.viewer.target_window_samples,
        picks=target_layout.picks,
    )
    reference_data, reference_ts = reference_stream.get_data(
        winsize=cfg.viewer.window_seconds + cfg.viewer.reference_window_extra_s,
        picks=reference_layout.picks,
    )

    target_window = _stream_data_to_window(target_data, target_ts, "target")
    reference_window = _stream_data_to_window(reference_data, reference_ts, "reference")
    if target_window is None and reference_window is None:
        return None

    latest_values: list[float] = []
    if target_window is not None and target_window.timestamps_s.size:
        latest_values.append(float(np.nanmax(target_window.timestamps_s)))
    if reference_window is not None and reference_window.timestamps_s.size:
        latest_values.append(float(np.nanmax(reference_window.timestamps_s)))

    if latest_values:
        t_end = max(latest_values)
        t_start = t_end - cfg.viewer.window_seconds
        target_window = (
            _slice_target_window(target_window, t_start)
            if target_window is not None
            else None
        )
        reference_window = (
            _slice_reference_window(reference_window, t_start)
            if reference_window is not None
            else None
        )

    return DualWindow(target=target_window, reference=reference_window)
