# @file
# @brief Shared data types for the handgrip realtime viewer.
##
# All dataclasses here are pure data containers with no side effects or I/O.
# They are imported by every layer (core, viz, runners) to avoid circular imports.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class StreamLayout:
    # @brief Channel name mapping for a single LSL stream.

    clock_label: str
    raw_label: str
    filtered_label: str | None = None

    @property
    def picks(self) -> list[str]:
        # @brief Ordered list of channel labels to pass to StreamLSL.get_data().
        # @return Ordered list of channel labels.
        out = [self.clock_label, self.raw_label]
        if self.filtered_label is not None:
            out.append(self.filtered_label)
        return out


@dataclass(slots=True)
class TargetWindow:
    # @brief A time-windowed snapshot of the target (handgrip) stream.

    timestamps_s: np.ndarray  # LSL timestamps in seconds
    device_clock_us: np.ndarray  # on-device monotonic clock in microseconds
    raw: np.ndarray  # raw ADC counts
    filtered: np.ndarray  # filtered / engineering-unit signal


@dataclass(slots=True)
class ReferenceWindow:
    # @brief A time-windowed snapshot of the reference (RS485) stream.

    timestamps_s: np.ndarray  # LSL timestamps in seconds
    rs485_clock: np.ndarray  # RS485 board clock (seconds, LSL epoch)
    raw: np.ndarray  # reference force in engineering units


@dataclass(slots=True)
class DualWindow:
    # @brief Paired target and reference windows for a single render cycle.

    target: TargetWindow | None
    reference: ReferenceWindow | None


@dataclass(slots=True)
class DualReplayData:
    # @brief Complete pre-loaded dataset for CSV or XDF replay modes.

    target_timestamps_s: np.ndarray
    target_device_clock_us: np.ndarray
    target_raw: np.ndarray
    target_filtered: np.ndarray
    reference_timestamps_s: np.ndarray
    reference_clock_s: np.ndarray
    reference_raw: np.ndarray
    source_name: str
    source_type: str
    target_labels: list[str]
    reference_labels: list[str]

    @property
    def duration_s(self) -> float:
        # @brief Total span of the replay dataset in seconds.
        # @return Duration in seconds.
        values: list[float] = []
        if self.target_timestamps_s.size:
            values.append(float(np.nanmax(self.target_timestamps_s)))
        if self.reference_timestamps_s.size:
            values.append(float(np.nanmax(self.reference_timestamps_s)))
        return max(values) if values else 0.0


@dataclass(slots=True)
class FigureHandles:
    # @brief Legacy container kept for backward compatibility with core/alignment.py.
    ##
    # The state dict is still consumed by compute_xy_reference_time_shift_s().
    # New code should use ViewerState directly.

    fig: Any
    axes: dict[str, Any]
    artists: dict[str, Any]
    state: dict[str, Any]


@dataclass
class ViewerState:
    # @brief Mutable render state for the NiceGUI viewer.
    ##
    # Replaces the handles.state dict from FigureHandles.
    # All fields are typed; no dict-key typos possible.

    # XY axis lock-max-span
    xy_lock_max_span: bool = False
    xy_max_span: dict[str, dict[str, float]] = field(default_factory=dict)  # xmin/xmax/ymin/ymax
    xy_reference_time_shift_s: float = 0.0
    xy_reference_tail_delta_s: float = 0.0
    xy_reference_shift_clipped: bool = False

    # XY pairing diagnostics (set by update_charts, read by diagnostics recorder)
    xy_pair_count: int = 0
    xy_t_min_s: float = float("nan")
    xy_t_max_s: float = float("nan")
    xy_alignment_mode: str = ""

    # Live mode control
    live_paused: bool = False
    live_reset_from_latest_window: bool = False
    target_cutoff_s: float | None = None
    reference_cutoff_s: float | None = None

    # Replay mode
    replay_progress: str = ""
    replay_paused: bool = False
    replay_finished: bool = False

    # Calibration markers (cached to avoid per-frame file reads)
    marker_events: list[dict[str, Any]] = field(default_factory=list)
    marker_file_mtime: float = 0.0

    def to_handles_state(self) -> dict[str, Any]:
        # @brief Return a dict compatible with core.alignment's FigureHandles.state.
        # @return Adapter dict used by compute_xy_reference_time_shift_s().
        return {
            "xy_reference_time_shift_s": self.xy_reference_time_shift_s,
            "xy_reference_tail_delta_s": self.xy_reference_tail_delta_s,
            "xy_reference_shift_clipped": self.xy_reference_shift_clipped,
        }

    def sync_from_handles_state(self, state_dict: dict[str, Any]) -> None:
        # @brief Copy alignment results back from a FigureHandles.state dict.
        # @param state_dict Source dict from compute_xy_reference_time_shift_s().
        self.xy_reference_time_shift_s = float(state_dict.get("xy_reference_time_shift_s", 0.0))
        self.xy_reference_tail_delta_s = float(state_dict.get("xy_reference_tail_delta_s", 0.0))
        self.xy_reference_shift_clipped = bool(state_dict.get("xy_reference_shift_clipped", False))
