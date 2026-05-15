"""Mutable runtime application state.

``AppState`` is the single source of truth shared between:
  - the acquisition worker thread (writes frames)
  - the NiceGUI UI refresh callback (reads frames)
  - the IPC publisher and file logger (receive frames from worker)

Thread safety: all reads/writes of ``frame_history``, ``latest_frame``, and
``frame_history_version`` must be performed under ``frame_lock``.

``RuntimeSettings`` holds the subset of configuration that the UI may change
at runtime (port, baud rate, mode, etc.) without mutating the immutable
OmegaConf ``DictConfig``.  This decouples the UI layer from the config object
and eliminates the ``cfg.device.slave_address = int(...)`` anti-pattern.

Dependency chain: models, core/*, io/*, transport/base
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from omegaconf import DictConfig

from rs485_gui.core.codec import truncate_text
from rs485_gui.models import ActiveSendStats, MeasurementFrame, SerialSettings

if TYPE_CHECKING:
    from rs485_gui.io.logger import SignalFileLogger
    from rs485_gui.io.publisher import MeasurementFramePublisher
    from rs485_gui.transport.base import BoardTransport

import logging

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Log-entry renderers (moved here to keep core/codec pure)
# ---------------------------------------------------------------------------

def _render_raw_log_entry(frame: MeasurementFrame, max_chars: int) -> str:
    import json
    raw = frame.raw_transport
    diagnostics = raw.get('diagnostics', {}) if isinstance(raw.get('diagnostics'), dict) else {}
    response_hex = raw.get('response_hex')
    request_hex = raw.get('request_hex')
    parts = [frame.host_ts_iso, frame.mode]
    if response_hex:
        parts.append(f'rx={truncate_text(str(response_hex), max(32, max_chars // 2))}')
    if request_hex:
        parts.append(f'tx={truncate_text(str(request_hex), max(32, max_chars // 3))}')
    if 'frame_length_bytes' in raw:
        parts.append(f'len={raw["frame_length_bytes"]}')
    if diagnostics:
        parts.append(
            'diag='
            f'parsed:{diagnostics.get("frames_ok", "?")},'
            f'delivered:{diagnostics.get("frames_delivered", "?")},'
            f'dropped:{diagnostics.get("frames_dropped_backlog", "?")},'
            f'resync:{diagnostics.get("header_resyncs", "?")},'
            f'discard:{diagnostics.get("discarded_bytes", "?")}'
        )
    if len(parts) == 2:
        parts.append(truncate_text(json.dumps(raw, ensure_ascii=False, separators=(',', ':')), max_chars))
    return truncate_text(' | '.join(parts), max_chars)


## @brief Render interpreted log entry.
#
#  @param frame Parameter description.
#  @param max_chars Parameter description.
#  @return Result produced by this function.
def _render_interpreted_log_entry(frame: MeasurementFrame, max_chars: int) -> str:
    import json
    interpreted = frame.interpreted
    summary = {
        'ts': frame.host_ts_iso,
        'mode': frame.mode,
        'gross': interpreted.get('gross_value'),
        'net': interpreted.get('net_value'),
        'peak': interpreted.get('peak_value'),
        'raw': interpreted.get('raw_value'),
        'unit': interpreted.get('unit_label'),
        'status': interpreted.get('status_flags'),
        'parsed_from': interpreted.get('parsed_from'),
    }
    return truncate_text(json.dumps(summary, ensure_ascii=False, separators=(',', ':')), max_chars)


# ---------------------------------------------------------------------------
# RuntimeSettings — UI-writable config subset
# ---------------------------------------------------------------------------

@dataclass
## @brief Represents the RuntimeSettings component.
class RuntimeSettings:
    """Holds the subset of settings that the UI may change after startup.

    This prevents UI callbacks from mutating the OmegaConf ``DictConfig``
    (which triggers structural warnings in strict mode and makes the runtime
    state invisible to the logger / IPC publisher unless they re-read config
    on every frame).
    """
    slave_address: int = 1
    active_send_frequency_code: int = 8
    plot_signal_key: str = 'net_value'
    clear_plot_on_connect: bool = True


# ---------------------------------------------------------------------------
# AppState
# ---------------------------------------------------------------------------

@dataclass
## @brief Represents the AppState component.
class AppState:
    """Central mutable runtime state shared between worker, UI, and I/O subsystems."""

    cfg: DictConfig
    serial_cfg: SerialSettings
    mode: str
    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)
    connected: bool = False
    connection_label: str = 'DISCONNECTED'
    status_text: str = 'Idle'
    stop_event: threading.Event = field(default_factory=threading.Event)
    worker_thread: threading.Thread | None = None
    transport: BoardTransport | None = None
    frame_lock: threading.Lock = field(default_factory=threading.Lock)
    latest_frame: MeasurementFrame | None = None
    raw_log: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    interpreted_log: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    event_log: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    frame_history: deque[MeasurementFrame] = field(default_factory=lambda: deque(maxlen=5000))
    parse_profile: str = 'modbus_rtu_response_11regs'
    signal_logger: SignalFileLogger | None = None
    ipc_publisher: MeasurementFramePublisher | None = None
    active_send_stats: ActiveSendStats = field(default_factory=ActiveSendStats)
    sampling_stats: SamplingStats = field(default_factory=lambda: _make_sampling_stats())
    display_sampling_stats: SamplingStats = field(default_factory=lambda: _make_sampling_stats())
    _last_ui_frame_ts: float | None = None
    _last_max_rate_frame_ts: float | None = None
    frame_history_version: int = 0

    # ------------------------------------------------------------------
    # Helpers called from transports / UI
    # ------------------------------------------------------------------

    def get_session_id(self) -> str:
        """Return the optional calibration session identifier."""
        try:
            return str(getattr(self.cfg.session, 'session_id', '') or '')
        except Exception:
            return ''

    ## @brief Build board profile snapshot.
    #
    #  @param self Parameter description.
    #  @return Constructed object for this operation.
    def build_board_profile_snapshot(self) -> dict[str, Any]:
        """Build a compact board/config snapshot for calibration manifests."""
        cfg = self.cfg
        rt = self.runtime
        return {
            'schema': 'rs485_board_profile.v2',
            'device_name': 'HighSpeedAcquisitionInstrument',
            'reference_role': 'calibration_reference',
            'recommended_unit': 'N',
            'serial': {
                'port': str(self.serial_cfg.port),
                'baudrate': int(self.serial_cfg.baudrate),
                'parity': str(self.serial_cfg.parity),
                'stopbits': int(self.serial_cfg.stopbits),
                'bytesize': int(self.serial_cfg.bytesize),
            },
            'device': {
                'mode': str(self.mode),
                'slave_address': int(rt.slave_address),
                'active_send_frequency_code': int(rt.active_send_frequency_code),
                'poll_interval_s': float(cfg.device.poll_interval_s),
            },
            'active_send': {
                'timestamp_policy': str(cfg.active_send.timestamp_policy),
                'parser_profile': str(cfg.active_send.default_parser_profile),
                'frame_register_count': int(cfg.active_send.frame_register_count),
                'delivery_window_s': float(cfg.active_send.delivery_window_s),
                'max_frames_per_delivery': int(cfg.active_send.max_frames_per_delivery),
            },
            'ipc': {
                'topic': str(cfg.ipc.topic),
                'signal_key': str(cfg.ipc.signal_key),
                'publish_after_max_rate_filter': bool(cfg.ipc.publish_after_max_rate_filter),
            },
        }

    ## @brief Push event.
    #
    #  @param self Parameter description.
    #  @param message Parameter description.
    def push_event(self, message: str) -> None:
        """Append a timestamped event to the event log and propagate to I/O subsystems."""
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line = f'[{ts}] {message}'
        self.event_log.appendleft(line)
        if self.signal_logger is not None and self.signal_logger.enabled:
            self.signal_logger.write_event(line)
        if self.ipc_publisher is not None:
            self.ipc_publisher.publish_event(message)
        LOGGER.info(message)

    ## @brief Clear signal trace.
    #
    #  @param self Parameter description.
    #  @param reason Parameter description.
    #  @param reset_session_counters Parameter description.
    def clear_signal_trace(self, *, reason: str, reset_session_counters: bool = False) -> None:
        """Clear the plot history and reset sampling rate windows."""
        window_size = int(self.cfg.ui.sampling_rate_window_samples)
        with self.frame_lock:
            self.frame_history.clear()
            self.frame_history_version += 1
            self._last_ui_frame_ts = None
        self._last_max_rate_frame_ts = None
        if reset_session_counters:
            self.sampling_stats.reset_all(window_size)
            self.display_sampling_stats.reset_all(window_size)
        else:
            self.sampling_stats.reset_window(window_size)
            self.display_sampling_stats.reset_window(window_size)
        self.push_event(f'Cleared plotted signal trace ({reason})')

    ## @brief Filter frames by max sampling rate.
    #
    #  @param self Parameter description.
    #  @param frames Parameter description.
    #  @return Result produced by this function.
    def filter_frames_by_max_sampling_rate(
        self, frames: list[MeasurementFrame]
    ) -> list[MeasurementFrame]:
        """Drop frames that exceed the configured acquisition max rate."""
        if not frames:
            return frames
        self.sampling_stats.record_received_samples(len(frames))
        max_hz = float(self.cfg.ui.max_signal_samples_per_second or 0.0)
        if max_hz <= 0:
            return frames
        min_dt = 1.0 / max_hz
        kept: list[MeasurementFrame] = []
        last_ts = self._last_max_rate_frame_ts
        dropped = 0
        for frame in frames:
            if last_ts is not None and frame.host_ts < (last_ts - min_dt):
                last_ts = None
            if last_ts is None or (frame.host_ts - last_ts) >= min_dt:
                kept.append(frame)
                last_ts = frame.host_ts
            else:
                dropped += 1
        self._last_max_rate_frame_ts = last_ts
        self.sampling_stats.add_dropped_samples(dropped)
        return kept

    ## @brief Record acquisition frames.
    #
    #  @param self Parameter description.
    #  @param frames Parameter description.
    def record_acquisition_frames(self, frames: list[MeasurementFrame]) -> None:
        """Record full-rate acquisition timing before GUI display throttling."""
        for frame in frames:
            self.sampling_stats.record_processed_frame(frame.host_ts)

    ## @brief Filter frames for ui.
    #
    #  @param self Parameter description.
    #  @param frames Parameter description.
    #  @return Result produced by this function.
    def filter_frames_for_ui(
        self, frames: list[MeasurementFrame]
    ) -> list[MeasurementFrame]:
        """Return a display-rate-limited subset for browser/UI rendering only."""
        if not frames:
            return frames
        max_hz = float(self.cfg.ui.display_max_samples_per_second or 0.0)
        if max_hz <= 0:
            return frames
        min_dt = 1.0 / max_hz
        kept: list[MeasurementFrame] = []
        last_ts = self._last_ui_frame_ts
        for frame in frames:
            if last_ts is None or (frame.host_ts - last_ts) >= min_dt:
                kept.append(frame)
                last_ts = frame.host_ts
        self._last_ui_frame_ts = last_ts
        if not kept:
            latest = frames[-1]
            if self._last_ui_frame_ts is None or (
                latest.host_ts - self._last_ui_frame_ts
            ) >= min_dt * 0.5:
                kept.append(latest)
                self._last_ui_frame_ts = latest.host_ts
        return kept

    ## @brief Push frames.
    #
    #  @param self Parameter description.
    #  @param frames Parameter description.
    def push_frames(self, frames: list[MeasurementFrame]) -> None:
        """Store frames in history and append rendered entries to UI log queues."""
        if not frames:
            return
        latest_frame = frames[-1]
        with self.frame_lock:
            self.latest_frame = latest_frame
            for frame in frames:
                self.frame_history.append(frame)
            self.frame_history_version += len(frames)
        ui_entry_chars = int(self.cfg.ui.max_ui_entry_chars)
        self.raw_log.appendleft(_render_raw_log_entry(latest_frame, ui_entry_chars))
        self.interpreted_log.appendleft(_render_interpreted_log_entry(latest_frame, ui_entry_chars))
        for frame in frames:
            self.display_sampling_stats.record_processed_frame(frame.host_ts)

    ## @brief Push frame.
    #
    #  @param self Parameter description.
    #  @param frame Parameter description.
    def push_frame(self, frame: MeasurementFrame) -> None:
        """Store a single frame (convenience wrapper)."""
        self.push_frames([frame])


# ---------------------------------------------------------------------------
# Internal factory helper (avoids forward-reference issues with dataclass fields)
# ---------------------------------------------------------------------------

def _make_sampling_stats() -> SamplingStats:
    from rs485_gui.core.sampling import SamplingStats
    return SamplingStats()


# Re-export for use by AppState type hints
from rs485_gui.core.sampling import SamplingStats  # noqa: E402
