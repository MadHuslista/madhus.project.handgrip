"""Data transfer objects for the RS485 acquisition board GUI.

All dataclasses here are pure data containers with no I/O or side effects.
``MeasurementFrame`` is the primary unit of data flowing through the system:
  transport → worker → AppState → (logger, publisher, UI)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
# @brief Represents the SerialSettings component.
class SerialSettings:
    """Snapshot of active serial-port parameters."""

    port: str = ""
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout: float = 0.2


@dataclass
# @brief Represents the MeasurementFrame component.
class MeasurementFrame:
    """One decoded measurement snapshot from the acquisition board.

    ``raw_transport`` preserves the wire-level bytes/registers so that the
    file logger can write a fully auditable raw record.

    ``interpreted`` holds all decoded engineering values (gross/net/peak,
    unit label, status flags, reconstructed timestamps) and is the primary
    source for IPC publication, UI display, and the GUI CSV log.

    ``board_profile`` is intentionally copied into every IPC frame because
    ZeroMQ PUB/SUB subscribers may start late and miss an initial
    announcement.
    """

    host_ts: float
    host_ts_iso: str
    mode: str
    raw_transport: dict[str, Any]
    interpreted: dict[str, Any]
    session_id: str = ""
    board_profile: dict[str, Any] = field(default_factory=dict)


@dataclass
# @brief Represents the PortInfo component.
class PortInfo:
    """Metadata for a discovered serial port, with a relevance score."""

    device: str
    description: str
    hwid: str
    vid: int | None = None
    pid: int | None = None
    #: Number of port-hint substring matches — higher is more likely to be the RS485 adapter.
    score: int = 0


@dataclass
# @brief Represents the ActiveSendStats component.
class ActiveSendStats:
    """Running counters for the active-send binary parser.

    Reset on each ``connect()`` call.  Thread-safe only when accessed
    from the acquisition worker thread; the UI reads a snapshot via
    ``AppState.active_send_stats`` under ``AppState.frame_lock``.
    """

    bytes_received: int = 0
    chunks_received: int = 0
    frames_ok: int = 0
    frames_delivered: int = 0
    frames_dropped_backlog: int = 0
    timeouts: int = 0
    crc_failures: int = 0
    header_resyncs: int = 0
    discarded_bytes: int = 0
    buffer_overflow_events: int = 0
    buffer_overflow_bytes: int = 0
    max_buffer_len: int = 0
    max_in_waiting: int = 0
    warning_events_total: int = 0
    warning_suppressed: int = 0
    last_warning_emit_monotonic: float = 0.0
    last_good_frame_hex: str = ""
    last_bad_candidate_hex: str = ""
    timestamp_reanchors: int = 0
    timestamp_drift_reanchors: int = 0
    timestamp_parser_reanchors: int = 0
    monotonic_adjust_events: int = 0
    monotonic_adjust_total_s: float = 0.0
    #: Batches squeezed by the bounded chain-lead relax (see active_send.max_chain_lead_s).
    chain_relax_events: int = 0
    #: Cumulative lead bled by squeezes, in seconds: sum of n*(dt - spacing) per relax.
    chain_relax_total_s: float = 0.0
    recovery_events: int = 0
    last_recovery_monotonic: float = 0.0
    last_recovery_warning_count: int = 0
