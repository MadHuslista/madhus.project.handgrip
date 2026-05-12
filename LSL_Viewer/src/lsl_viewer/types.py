"""Shared data types for the handgrip realtime viewer.

All dataclasses here are pure data containers with no side effects or I/O.
They are imported by every layer (core, viz, runners) to avoid circular imports.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(slots=True)
class StreamLayout:
    """Channel name mapping for a single LSL stream."""

    clock_label: str
    raw_label: str
    filtered_label: str | None = None

    @property
    def picks(self) -> list[str]:
        """Ordered list of channel labels to pass to StreamLSL.get_data()."""
        out = [self.clock_label, self.raw_label]
        if self.filtered_label is not None:
            out.append(self.filtered_label)
        return out


@dataclass(slots=True)
class TargetWindow:
    """A time-windowed snapshot of the target (handgrip) stream."""

    timestamps_s: np.ndarray       # LSL timestamps in seconds
    device_clock_us: np.ndarray    # on-device monotonic clock in microseconds
    raw: np.ndarray                 # raw ADC counts
    filtered: np.ndarray            # filtered / engineering-unit signal


@dataclass(slots=True)
class ReferenceWindow:
    """A time-windowed snapshot of the reference (RS485) stream."""

    timestamps_s: np.ndarray    # LSL timestamps in seconds
    rs485_clock: np.ndarray     # RS485 board clock (seconds, LSL epoch)
    raw: np.ndarray             # reference force in engineering units


@dataclass(slots=True)
class DualWindow:
    """Paired target + reference windows for a single render cycle."""

    target: TargetWindow | None
    reference: ReferenceWindow | None


@dataclass(slots=True)
class DualReplayData:
    """Complete pre-loaded dataset for CSV or XDF replay modes."""

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
        """Total span of the replay dataset in seconds."""
        values: list[float] = []
        if self.target_timestamps_s.size:
            values.append(float(np.nanmax(self.target_timestamps_s)))
        if self.reference_timestamps_s.size:
            values.append(float(np.nanmax(self.reference_timestamps_s)))
        return max(values) if values else 0.0


@dataclass(slots=True)
class FigureHandles:
    """Container for all matplotlib figure objects and mutable render state."""

    fig: Any
    axes: dict[str, Any]
    artists: dict[str, Any]
    state: dict[str, Any]
