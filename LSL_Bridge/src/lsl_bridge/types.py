"""
Shared data contracts for the LSL Bridge.

All types in this module are pure dataclasses or Protocols with no external
dependencies beyond the standard library.  Every other module imports from
here rather than defining its own data shapes, ensuring a single source of
truth for the inter-module API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class Processor(Protocol):
    """
    Minimal interface implemented by filter-module processors.

    The bridge imports the processing module at runtime via importlib and
    checks that the returned object satisfies this protocol.
    """

    def process(self, value: float, sample_time_s: float) -> float:
        ...


# ---------------------------------------------------------------------------
# Target stream data types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FirmwareMetadata:
    """Metadata reported by the target firmware M2 boot frame."""

    payload_schema: int | None = None
    firmware_version: str | None = None
    git_sha: str | None = None
    hx711_rate_hz: float | None = None
    scale_factor: float | None = None
    scale_offset: float | None = None
    unit: str | None = None
    last_seen_lsl_ts: float | None = None


@dataclass(slots=True)
class ParsedTargetSample:
    """Canonical target sample parsed from a strict D2 UART line."""

    sequence: int
    device_clock_us: int
    target_raw_count: float
    target_current_units: float
    target_status: int
    lsl_timestamp: float
    host_unix_time_ns: int
    raw_line: str


# ---------------------------------------------------------------------------
# Reference stream data type
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ReferenceSample:
    """Canonical reference sample decoded from RS485_GUI IPC."""

    sequence: int
    mode: str
    signal_key: str
    reference_force_N: float
    reference_clock_s: float
    host_lsl_ts: float
    host_unix_ts: float
    received_lsl_ts: float
    clock_source: str
    unit_label: str
    status: int
    timestamp_source: str
    configured_frequency_hz: float
    session_id: str | None = None
    board_profile: dict[str, Any] = field(default_factory=dict)
