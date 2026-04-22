from __future__ import annotations

import csv
import json
import logging
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, TextIO, Tuple

import sys
from nicegui import app, ui
from omegaconf import DictConfig, OmegaConf
import plotly.graph_objects as go
try:
    import numpy as np
except Exception:  # pragma: no cover - optional acceleration
    np = None
import serial
from serial.tools import list_ports

LOGGER = logging.getLogger('acquisition_board_gui')


# ---------- Configuration / constants ----------

BAUD_CODE_TO_VALUE: Dict[int, int] = {
    1: 2400,
    2: 4800,
    3: 9600,
    4: 19200,
    5: 22800,
    6: 38400,
    7: 57600,
    8: 115200,
    9: 128000,
    10: 230400,
    11: 256000,
    12: 460800,
    13: 500000,
    14: 512000,
    15: 600000,
}

ACTIVE_SEND_FREQ_CODE_TO_VALUE: Dict[int, int] = {
    0: 1,
    1: 2,
    2: 5,
    3: 10,
    4: 20,
    5: 25,
    6: 60,
    7: 100,
    8: 500,
    9: 1000,
}

PARITY_CODE_TO_VALUE: Dict[int, str] = {
    0: 'N',
    1: 'E',
    2: 'O',
}

UNIT_CODE_TO_LABEL: Dict[int, str] = {
    0: 'none',
    1: 'g',
    2: 'kg',
    3: 't',
    4: 'N',
    5: 'pa',
    6: 'kPa',
    7: 'MPa',
    8: 'N·m',
    9: 'kN',
}

DECIMAL_CODE_TO_DIGITS: Dict[int, int] = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
}

STATUS_FLAGS: Dict[int, str] = {
    0: 'data_valid',
    1: 'peak_detecting',
    2: 'rom_fault',
    3: 'adc_fault',
    4: 'adc_signal_too_large',
    5: 'gross_overload',
    6: 'power_on_zero_failed',
    7: 'tare_condition_not_met',
    8: 'zero_range_exceeded',
    9: 'relay1_active',
    10: 'relay2_active',
    11: 'relay3_active',
}

COMMAND_REGISTER = 11  # 0x000B / PLC 40012
READ_START_REGISTER = 0  # 0x0000 / PLC 40001
READ_REGISTER_COUNT = 11

COMMANDS: Dict[str, int] = {
    'tare_temp': 1,
    'tare_save': 2,
    'cancel_tare': 3,
    'zero_temp': 4,
    'zero_save': 5,
    'clear_peak': 6,
    'calibration': 7,
    'factory_reset': 9,
}

DEFAULT_PORT_HINTS = [
    'USB',
    'RS485',
    'FTDI',
    'CH340',
    'CP210',
    'PL2303',
    'ttyUSB',
    'ttyACM',
]


# ---------- Utility dataclasses ----------

@dataclass
class SerialSettings:
    port: str = ''
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = 'N'
    stopbits: int = 1
    timeout: float = 0.2


@dataclass
class MeasurementFrame:
    host_ts: float
    host_ts_iso: str
    mode: str
    raw_transport: Dict[str, Any]
    interpreted: Dict[str, Any]


@dataclass
class PortInfo:
    device: str
    description: str
    hwid: str
    vid: Optional[int] = None
    pid: Optional[int] = None
    score: int = 0


@dataclass
class ActiveSendStats:
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
    last_good_frame_hex: str = ''
    last_bad_candidate_hex: str = ''



@dataclass
class SamplingStats:
    window_dts_s: Deque[float] = field(default_factory=lambda: deque(maxlen=128))
    received_samples: int = 0
    dropped_samples_max_rate: int = 0
    last_processed_ts: Optional[float] = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset_window(self, window_size: int) -> None:
        with self._lock:
            self.window_dts_s = deque(maxlen=max(2, int(window_size)))
            self.last_processed_ts = None

    def reset_all(self, window_size: int) -> None:
        with self._lock:
            self.window_dts_s = deque(maxlen=max(2, int(window_size)))
            self.received_samples = 0
            self.dropped_samples_max_rate = 0
            self.last_processed_ts = None

    def record_received_samples(self, count: int) -> None:
        with self._lock:
            self.received_samples += int(count)

    def add_dropped_samples(self, count: int) -> None:
        with self._lock:
            self.dropped_samples_max_rate += int(count)

    def get_last_processed_ts(self) -> Optional[float]:
        with self._lock:
            return self.last_processed_ts

    def record_processed_frame(self, host_ts: float) -> None:
        with self._lock:
            if self.last_processed_ts is not None:
                dt = host_ts - self.last_processed_ts
                if dt > 0:
                    self.window_dts_s.append(dt)
            self.last_processed_ts = host_ts

    def snapshot(self) -> Tuple[Optional[float], Optional[float], int, int, int]:
        with self._lock:
            dts = list(self.window_dts_s)
            received = self.received_samples
            dropped = self.dropped_samples_max_rate
        if not dts:
            return None, None, 0, received, dropped
        rates = [1.0 / dt for dt in dts if dt > 0]
        if not rates:
            return None, None, len(dts), received, dropped
        mean = sum(rates) / len(rates)
        if len(rates) < 2:
            std = 0.0
        else:
            variance = sum((rate - mean) ** 2 for rate in rates) / len(rates)
            std = math.sqrt(variance)
        return mean, std, len(dts), received, dropped


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    keep = max(16, max_chars - 24)
    omitted = len(text) - keep
    return f'{text[:keep]} ... (+{omitted} chars)'


def build_log_text(items: List[str], separator: str, max_total_chars: int) -> str:
    if max_total_chars <= 0:
        return separator.join(items)
    selected: List[str] = []
    used = 0
    total_items = len(items)
    for idx, item in enumerate(items):
        extra = len(item) + (len(separator) if selected else 0)
        if used + extra > max_total_chars:
            remaining = total_items - idx
            selected.append(f'... truncated, {remaining} older entr{"y" if remaining == 1 else "ies"} hidden ...')
            break
        selected.append(item)
        used += extra
    return separator.join(selected)




SIGNAL_DEFINITIONS: Dict[str, Dict[str, str]] = {
    'gross_value': {
        'label': 'gross_value',
        'description': 'Gross interpreted engineering value after applying the board decimal scaling.',
        'unit_hint': 'Board-selected engineering unit.',
        'source': 'gross_raw_value + decimal_code',
    },
    'net_value': {
        'label': 'net_value',
        'description': 'Net interpreted engineering value after tare/zero handling and decimal scaling.',
        'unit_hint': 'Board-selected engineering unit.',
        'source': 'net_raw_value + decimal_code',
    },
    'peak_value': {
        'label': 'peak_value',
        'description': 'Peak interpreted engineering value after decimal scaling.',
        'unit_hint': 'Board-selected engineering unit.',
        'source': 'peak_raw_value + decimal_code',
    },
    'gross_raw_value': {
        'label': 'gross_raw_value',
        'description': 'Raw signed 32-bit gross reading straight from the Modbus register pair.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'registers 40001/40002',
    },
    'net_raw_value': {
        'label': 'net_raw_value',
        'description': 'Raw signed 32-bit net reading straight from the Modbus register pair.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'registers 40003/40004',
    },
    'peak_raw_value': {
        'label': 'peak_raw_value',
        'description': 'Raw signed 32-bit peak reading straight from the Modbus register pair.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'registers 40005/40006',
    },
    'internal_code_raw_value': {
        'label': 'internal_code_raw_value',
        'description': 'Raw internal ADC code / internal measurement code exposed by the board.',
        'unit_hint': 'Internal board code; not an engineering unit.',
        'source': 'registers 40007/40008',
    },
    'raw_value': {
        'label': 'raw_value',
        'description': 'Compatibility alias for the primary raw plotted value. In Modbus decoding it maps to gross_raw_value.',
        'unit_hint': 'Depends on parser profile; often raw board integer.',
        'source': 'parser-dependent primary numeric output',
    },
    'gross_raw': {
        'label': 'gross_raw',
        'description': 'Alias of gross_raw_value.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'gross_raw_value',
    },
    'net_raw': {
        'label': 'net_raw',
        'description': 'Alias of net_raw_value.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'net_raw_value',
    },
    'peak_raw': {
        'label': 'peak_raw',
        'description': 'Alias of peak_raw_value.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'peak_raw_value',
    },
}

COMMAND_METADATA: List[Dict[str, str]] = [
    {
        'name': 'tare_temp',
        'title': 'Temporary tare',
        'description': 'Applies tare without retaining it across power loss.',
        'manual_equivalent': 'tPEEL / long-press tare key',
    },
    {
        'name': 'tare_save',
        'title': 'Saved tare',
        'description': 'Applies tare and preserves it across power cycles.',
        'manual_equivalent': 'SPEEL',
    },
    {
        'name': 'cancel_tare',
        'title': 'Cancel tare',
        'description': 'Clears the currently stored tare value.',
        'manual_equivalent': 'CPEEL',
    },
    {
        'name': 'zero_temp',
        'title': 'Temporary zero',
        'description': 'Performs a temporary zero action without saving it after power loss.',
        'manual_equivalent': 'SZEro / long-press zero key',
    },
    {
        'name': 'zero_save',
        'title': 'Saved zero calibration',
        'description': 'Stores the current zero point persistently.',
        'manual_equivalent': 'CZEro / 200.ZE',
    },
    {
        'name': 'clear_peak',
        'title': 'Clear peak',
        'description': 'Clears the captured peak value.',
        'manual_equivalent': 'REMAX / long-press ENT',
    },
    {
        'name': 'calibration',
        'title': 'Enter calibration flow',
        'description': 'Triggers the calibration command pathway exposed by the board.',
        'manual_equivalent': 'C2.CAL / calibration interface',
    },
    {
        'name': 'factory_reset',
        'title': 'Factory reset',
        'description': 'Restores factory-default parameters on the instrument.',
        'manual_equivalent': '116.FA Restore factory settings',
    },
]


def get_plot_signal_key(cfg: DictConfig) -> str:
    default_key = str(getattr(cfg.ui, 'default_plot_signal_key', getattr(cfg.ui, 'plot_signal_key', 'net_value')))
    return str(getattr(cfg.ui, 'plot_signal_key', default_key))


def get_plot_signal_label(cfg: DictConfig) -> str:
    signal_key = get_plot_signal_key(cfg)
    meta = SIGNAL_DEFINITIONS.get(signal_key, {})
    return str(meta.get('label', getattr(cfg.ui, 'plot_signal_label', signal_key)))


def get_plot_signal_options() -> Dict[str, str]:
    return {key: meta.get('label', key) for key, meta in SIGNAL_DEFINITIONS.items()}


def extract_signal_value(frame: MeasurementFrame, signal_key: str) -> Optional[float]:
    value = frame.interpreted.get(signal_key)
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def extract_plot_value(frame: MeasurementFrame, cfg: DictConfig) -> Optional[float]:
    return extract_signal_value(frame, get_plot_signal_key(cfg))


def get_target_sampling_rate_hz(cfg: DictConfig, mode: str) -> Optional[float]:
    if mode == 'active_send':
        return float(ACTIVE_SEND_FREQ_CODE_TO_VALUE.get(int(cfg.device.active_send_frequency_code), 0) or 0)
    poll_interval_s = float(getattr(cfg.device, 'poll_interval_s', 0.0) or 0.0)
    if poll_interval_s <= 0:
        return None
    return 1.0 / poll_interval_s


def format_rate(value: Optional[float]) -> str:
    if value is None:
        return 'n/a'
    if value <= 0:
        return 'unlimited'
    return f'{value:.3f} Hz'


def build_signal_metadata_text(app_state: 'AppState') -> str:
    signal_key = get_plot_signal_key(app_state.cfg)
    meta = SIGNAL_DEFINITIONS.get(
        signal_key,
        {'label': signal_key, 'description': 'No metadata available.', 'unit_hint': 'n/a', 'source': signal_key},
    )
    with app_state.frame_lock:
        latest_frame = app_state.latest_frame
        recent_frames = list(app_state.frame_history)
    selected_values = [extract_signal_value(frame, signal_key) for frame in recent_frames]
    selected_values = [value for value in selected_values if value is not None]
    if selected_values:
        value_min = min(selected_values)
        value_max = max(selected_values)
        value_range_line = f'Visible range: min={value_min:.6g}, max={value_max:.6g}'
    else:
        value_range_line = 'Visible range: n/a'

    lines = [
        f'Selected signal: {meta.get("label", signal_key)}',
        f'Description: {meta.get("description", "n/a")}',
        f'Calculation/source: {meta.get("source", signal_key)}',
        f'Unit hint: {meta.get("unit_hint", "n/a")}',
        value_range_line,
    ]
    if latest_frame is None:
        lines.append('Latest frame metadata: no samples received yet.')
        return '\n'.join(lines)

    interpreted = latest_frame.interpreted
    status_flags = interpreted.get('status_flags')
    if isinstance(status_flags, list):
        status_text = ', '.join(str(flag) for flag in status_flags) if status_flags else 'none'
    else:
        status_text = str(status_flags)

    lines.extend([
        'Latest frame metadata:',
        f'  decimal_code: {interpreted.get("decimal_code", "n/a")}  -> board decimal-point code used for engineering-value scaling',
        f'  unit_code: {interpreted.get("unit_code", "n/a")}  -> board engineering-unit code',
        f'  unit_label: {interpreted.get("unit_label", "n/a")}  -> decoded engineering unit label',
        f'  status_word: {interpreted.get("status_word", "n/a")}  -> raw board status bitfield',
        f'  status_flags: {status_text}  -> decoded status bits / relay / alarm states',
        f'  parsed_from: {interpreted.get("parsed_from", "n/a")}  -> decoder path used to build the plotted value',
        f'  timestamp_source: {interpreted.get("timestamp_source", "n/a")}  -> origin of the assigned sample timestamp',
        f'  timestamp_host_iso: {interpreted.get("timestamp_host_iso", "n/a")}  -> latest assigned host timestamp',
    ])
    return '\n'.join(lines)


def downsample_points_for_render(points: List[Tuple[float, float]], factor: int, max_points: int) -> List[Tuple[float, float]]:
    if not points:
        return points
    factor = max(1, int(factor))
    if np is not None:
        arr = np.asarray(points, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != 2:
            return points
        last_idx = arr.shape[0] - 1
        if factor > 1:
            idx = np.arange(0, arr.shape[0], factor, dtype=np.int64)
            if idx.size == 0 or idx[-1] != last_idx:
                idx = np.append(idx, last_idx)
            arr = arr[idx]
            last_idx = arr.shape[0] - 1
        if max_points > 0 and arr.shape[0] > max_points:
            stride = max(1, math.ceil(arr.shape[0] / max_points))
            idx = np.arange(0, arr.shape[0], stride, dtype=np.int64)
            if idx.size == 0 or idx[-1] != last_idx:
                idx = np.append(idx, last_idx)
            arr = arr[idx]
        return [(float(x), float(y)) for x, y in arr]
    original_last = points[-1]
    if factor > 1:
        points = points[::factor]
        if points[-1] != original_last:
            points.append(original_last)
    if max_points > 0 and len(points) > max_points:
        stride = max(1, math.ceil(len(points) / max_points))
        points = points[::stride]
        if points[-1] != original_last:
            points.append(original_last)
    return points

def render_raw_log_entry(frame: MeasurementFrame, max_chars: int) -> str:
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
        parts.append(truncate_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), max_chars))
    return truncate_text(' | '.join(parts), max_chars)


def render_interpreted_log_entry(frame: MeasurementFrame, max_chars: int) -> str:
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
    return truncate_text(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), max_chars)


class SignalFileLogger:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.enabled = bool(getattr(cfg.logger, 'enabled', False))
        self.directory = Path(str(cfg.logger.directory)).expanduser()
        self.write_mode = str(cfg.logger.write_mode).lower()
        if self.write_mode not in {'append', 'overwrite'}:
            raise ValueError(f'logger.write_mode must be append or overwrite, got {self.write_mode}')

        self.raw_path = self.directory / str(cfg.logger.raw_signal_filename)
        self.interpreted_path = self.directory / str(cfg.logger.interpreted_signal_filename)
        self.gui_path = self.directory / str(cfg.logger.gui_signal_filename)
        self.event_path = self.directory / str(getattr(cfg.logger, 'event_log_filename', 'event.log'))

        self._raw_fp: Optional[TextIO] = None
        self._interpreted_fp: Optional[TextIO] = None
        self._gui_fp: Optional[TextIO] = None
        self._event_fp: Optional[TextIO] = None
        self._gui_writer: Optional[csv.writer] = None
        self._lock = threading.Lock()

    def open(self) -> None:
        if not self.enabled:
            return

        self.directory.mkdir(parents=True, exist_ok=True)
        file_mode = 'a' if self.write_mode == 'append' else 'w'
        self._raw_fp = self.raw_path.open(file_mode, encoding='utf-8', newline='')
        self._interpreted_fp = self.interpreted_path.open(file_mode, encoding='utf-8', newline='')

        gui_file_preexisting = self.gui_path.exists() and self.gui_path.stat().st_size > 0
        self._gui_fp = self.gui_path.open(file_mode, encoding='utf-8', newline='')
        self._event_fp = self.event_path.open(file_mode, encoding='utf-8', newline='')
        self._gui_writer = csv.writer(self._gui_fp)

        if self.write_mode == 'overwrite' or not gui_file_preexisting:
            self._gui_writer.writerow(['host_ts_epoch_s', 'host_ts_iso', 'mode', 'raw_value', 'plot_signal_key', 'plot_value'])
            self._gui_fp.flush()

    def close(self) -> None:
        with self._lock:
            for fp in (self._raw_fp, self._interpreted_fp, self._gui_fp, self._event_fp):
                if fp is not None and not fp.closed:
                    fp.flush()
                    fp.close()
            self._raw_fp = None
            self._interpreted_fp = None
            self._gui_fp = None
            self._event_fp = None
            self._gui_writer = None

    def write_frames(self, frames: List[MeasurementFrame]) -> None:
        if not self.enabled or not frames:
            return
        with self._lock:
            if self._raw_fp is None or self._interpreted_fp is None or self._gui_fp is None or self._gui_writer is None:
                raise RuntimeError('SignalFileLogger.write_frames called before open()')

            plot_signal_key = get_plot_signal_key(self.cfg)
            for frame in frames:
                raw_record = {
                    'host_ts_epoch_s': frame.host_ts,
                    'host_ts_iso': frame.host_ts_iso,
                    'mode': frame.mode,
                    'raw_transport': frame.raw_transport,
                }
                interpreted_record = {
                    'host_ts_epoch_s': frame.host_ts,
                    'host_ts_iso': frame.host_ts_iso,
                    'mode': frame.mode,
                    'interpreted': frame.interpreted,
                }
                self._raw_fp.write(json.dumps(raw_record, ensure_ascii=False) + '\n')
                self._interpreted_fp.write(json.dumps(interpreted_record, ensure_ascii=False) + '\n')

                raw_value = frame.interpreted.get('raw_value')
                plot_value = extract_plot_value(frame, self.cfg)
                self._gui_writer.writerow([frame.host_ts, frame.host_ts_iso, frame.mode, raw_value, plot_signal_key, plot_value])

            self._raw_fp.flush()
            self._interpreted_fp.flush()
            self._gui_fp.flush()

    def write_frame(self, frame: MeasurementFrame) -> None:
        self.write_frames([frame])

    def write_event(self, line: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._event_fp is None:
                return
            self._event_fp.write(line + '\n')
            self._event_fp.flush()


@dataclass
class AppState:
    cfg: DictConfig
    serial_cfg: SerialSettings
    mode: str
    connected: bool = False
    connection_label: str = 'DISCONNECTED'
    status_text: str = 'Idle'
    stop_event: threading.Event = field(default_factory=threading.Event)
    worker_thread: Optional[threading.Thread] = None
    transport: Optional['BoardTransport'] = None
    frame_lock: threading.Lock = field(default_factory=threading.Lock)
    latest_frame: Optional[MeasurementFrame] = None
    raw_log: Deque[str] = field(default_factory=lambda: deque(maxlen=500))
    interpreted_log: Deque[str] = field(default_factory=lambda: deque(maxlen=500))
    event_log: Deque[str] = field(default_factory=lambda: deque(maxlen=500))
    frame_history: Deque[MeasurementFrame] = field(default_factory=lambda: deque(maxlen=5000))
    parse_profile: str = 'line_ascii_auto'
    parse_numeric_index: int = 0
    hex_word_endianness: str = 'big'
    signal_logger: Optional[SignalFileLogger] = None
    active_send_stats: ActiveSendStats = field(default_factory=ActiveSendStats)
    sampling_stats: SamplingStats = field(default_factory=SamplingStats)

    def push_event(self, message: str) -> None:
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line = f'[{ts}] {message}'
        self.event_log.appendleft(line)
        if self.signal_logger is not None and self.signal_logger.enabled:
            self.signal_logger.write_event(line)
        LOGGER.info(message)

    def clear_signal_trace(self, *, reason: str, reset_session_counters: bool = False) -> None:
        window_size = int(getattr(self.cfg.ui, 'sampling_rate_window_samples', 128))
        with self.frame_lock:
            self.latest_frame = None if not self.frame_history else self.latest_frame
            self.frame_history.clear()
        if reset_session_counters:
            self.sampling_stats.reset_all(window_size)
        else:
            self.sampling_stats.reset_window(window_size)
        self.push_event(f'Cleared plotted signal trace ({reason})')

    def filter_frames_by_max_sampling_rate(self, frames: List[MeasurementFrame]) -> List[MeasurementFrame]:
        if not frames:
            return frames
        self.sampling_stats.record_received_samples(len(frames))
        max_hz = float(getattr(self.cfg.ui, 'max_signal_samples_per_second', 0.0) or 0.0)
        if max_hz <= 0:
            return frames
        min_dt = 1.0 / max_hz
        kept: List[MeasurementFrame] = []
        last_ts = self.sampling_stats.get_last_processed_ts()
        dropped = 0
        for frame in frames:
            if last_ts is None or (frame.host_ts - last_ts) >= min_dt:
                kept.append(frame)
                last_ts = frame.host_ts
            else:
                dropped += 1
        self.sampling_stats.add_dropped_samples(dropped)
        return kept

    def push_frames(self, frames: List[MeasurementFrame]) -> None:
        if not frames:
            return
        latest_frame = frames[-1]
        with self.frame_lock:
            self.latest_frame = latest_frame
            for frame in frames:
                self.frame_history.append(frame)
        ui_entry_chars = int(getattr(self.cfg.ui, 'max_ui_entry_chars', 600))
        self.raw_log.appendleft(render_raw_log_entry(latest_frame, ui_entry_chars))
        self.interpreted_log.appendleft(render_interpreted_log_entry(latest_frame, ui_entry_chars))
        for frame in frames:
            self.sampling_stats.record_processed_frame(frame.host_ts)

    def push_frame(self, frame: MeasurementFrame) -> None:
        self.push_frames([frame])


# ---------- Port discovery ----------

def enumerate_ports(port_hints: List[str]) -> List[PortInfo]:
    ports: List[PortInfo] = []
    for p in list_ports.comports():
        haystack = ' '.join(filter(None, [p.device, p.description, p.hwid])).upper()
        score = 0
        for hint in port_hints:
            if hint.upper() in haystack:
                score += 1
        ports.append(
            PortInfo(
                device=p.device,
                description=p.description or '',
                hwid=p.hwid or '',
                vid=p.vid,
                pid=p.pid,
                score=score,
            )
        )
    ports.sort(key=lambda item: (-item.score, item.device))
    return ports


# ---------- Minimal Modbus RTU ----------

def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


class ModbusError(RuntimeError):
    pass


class MinimalModbusRTU:
    def __init__(self, serial_port: serial.Serial, slave_id: int, inter_frame_gap_s: float = 0.01):
        self.ser = serial_port
        self.slave_id = slave_id
        self.inter_frame_gap_s = inter_frame_gap_s
        self.lock = threading.Lock()

    def _effective_inter_frame_gap_s(self) -> float:
        configured = max(0.0, float(self.inter_frame_gap_s))
        try:
            baud = max(1, int(self.ser.baudrate))
        except Exception:
            baud = 9600
        # Modbus RTU silent interval is 3.5 character times. Use the larger of that or a small practical floor.
        char_time_s = 11.0 / float(baud)
        protocol_gap_s = 3.5 * char_time_s
        return max(configured, protocol_gap_s, 0.0005)

    def _read_exact_with_deadline(self, size: int, deadline: float) -> bytes:
        buf = bytearray()
        while len(buf) < size:
            now = time.monotonic()
            if now >= deadline:
                break
            chunk = self.ser.read(size - len(buf))
            if chunk:
                buf.extend(chunk)
                continue
            if time.monotonic() >= deadline:
                break
        return bytes(buf)

    def _exchange(self, payload: bytes, expected_function: int) -> bytes:
        frame = payload + crc16_modbus(payload).to_bytes(2, byteorder='little')
        deadline = time.monotonic() + max(0.01, float(getattr(self.ser, 'timeout', 0.2) or 0.2))
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(frame)
            self.ser.flush()
            time.sleep(self._effective_inter_frame_gap_s())
            header = self._read_exact_with_deadline(2, deadline)
            if len(header) < 2:
                raise ModbusError(f'Short response header: expected 2 bytes, got {len(header)} bytes')
            slave_id = header[0]
            function = header[1]
            if function & 0x80:
                rest = self._read_exact_with_deadline(3, deadline)
                response = header + rest
            elif function == 0x03:
                byte_count_raw = self._read_exact_with_deadline(1, deadline)
                if len(byte_count_raw) < 1:
                    raise ModbusError('Short response: missing byte count')
                byte_count = byte_count_raw[0]
                rest = self._read_exact_with_deadline(byte_count + 2, deadline)
                response = header + byte_count_raw + rest
            elif function == 0x06:
                rest = self._read_exact_with_deadline(4, deadline)
                response = header + rest
            else:
                rest = self.ser.read(256)
                response = header + rest
        if len(response) < 5:
            raise ModbusError(f'Invalid RTU response length: got {len(response)} bytes')
        data, received_crc = response[:-2], response[-2:]
        expected_crc = crc16_modbus(data).to_bytes(2, byteorder='little')
        if received_crc != expected_crc:
            note = ''
            active_header = bytes([self.slave_id, 0x03, READ_REGISTER_COUNT * 2])
            if response.count(active_header) >= 2:
                note = ' (response looks like repeated active-send push frames; verify board setting 504.AS=0 for Modbus RTU)'
            raise ModbusError(
                f'CRC mismatch: got {received_crc.hex()}, expected {expected_crc.hex()}, frame={response.hex(" ")}{note}'
            )
        if slave_id != self.slave_id:
            raise ModbusError(f'Unexpected slave id: got {slave_id}, expected {self.slave_id}')
        if function != expected_function and not (function & 0x80):
            raise ModbusError(f'Unexpected function: got 0x{function:02X}, expected 0x{expected_function:02X}')
        if function & 0x80:
            code = data[2] if len(data) > 2 else None
            raise ModbusError(f'Modbus exception function=0x{function:02X} code={code}')
        return response

    def read_holding_registers(self, address: int, count: int) -> Tuple[List[int], bytes, bytes]:
        payload = bytes([
            self.slave_id,
            0x03,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
        ])
        expected_min_len = 5 + count * 2
        response = self._exchange(payload, expected_function=0x03)
        raw_without_crc = response[:-2]
        byte_count = raw_without_crc[2]
        expected_byte_count = count * 2
        if byte_count != expected_byte_count:
            raise ModbusError(f'Unexpected byte count: got {byte_count}, expected {expected_byte_count}')
        values = []
        data = raw_without_crc[3:3 + byte_count]
        for i in range(0, len(data), 2):
            values.append((data[i] << 8) | data[i + 1])
        return values, payload, response

    def write_single_register(self, address: int, value: int) -> Tuple[bytes, bytes]:
        payload = bytes([
            self.slave_id,
            0x06,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        ])
        response = self._exchange(payload, expected_function=0x06)
        return payload, response


# ---------- Decoding ----------

def combine_s32_from_words(low_word: int, high_word: int) -> int:
    value = ((high_word & 0xFFFF) << 16) | (low_word & 0xFFFF)
    if value & 0x80000000:
        value -= 0x100000000
    return value



def decode_status_word(value: int) -> List[str]:
    active: List[str] = []
    for bit, label in STATUS_FLAGS.items():
        if value & (1 << bit):
            active.append(label)
    return active



def apply_decimal(value: Optional[int], decimal_code: int) -> Optional[float]:
    if value is None:
        return None
    digits = DECIMAL_CODE_TO_DIGITS.get(decimal_code, 0)
    return value / (10 ** digits)



def decode_modbus_measurement(registers: List[int], host_ts: float) -> MeasurementFrame:
    decimal_code = registers[8]
    unit_code = registers[9]
    status_word = registers[10]

    gross_raw = combine_s32_from_words(registers[0], registers[1])
    net_raw = combine_s32_from_words(registers[2], registers[3])
    peak_raw = combine_s32_from_words(registers[4], registers[5])
    internal_raw = combine_s32_from_words(registers[6], registers[7])

    interpreted = {
        'timestamp_host_iso': datetime.fromtimestamp(host_ts).isoformat(timespec='milliseconds'),
        'timestamp_host_epoch_s': host_ts,
        'decimal_code': decimal_code,
        'decimal_digits': DECIMAL_CODE_TO_DIGITS.get(decimal_code, 0),
        'unit_code': unit_code,
        'unit_label': UNIT_CODE_TO_LABEL.get(unit_code, f'unknown({unit_code})'),
        'status_word': status_word,
        'status_flags': decode_status_word(status_word),
        'gross_raw_value': gross_raw,
        'net_raw_value': net_raw,
        'peak_raw_value': peak_raw,
        'gross_raw': gross_raw,
        'net_raw': net_raw,
        'peak_raw': peak_raw,
        'internal_code_raw_value': internal_raw,
        'gross_value': apply_decimal(gross_raw, decimal_code),
        'net_value': apply_decimal(net_raw, decimal_code),
        'peak_value': apply_decimal(peak_raw, decimal_code),
        'raw_value': gross_raw,
    }
    raw_transport = {
        'registers': {f'400{idx + 1:02d}': reg for idx, reg in enumerate(registers, start=0)},
    }
    return MeasurementFrame(
        host_ts=host_ts,
        host_ts_iso=datetime.fromtimestamp(host_ts).isoformat(timespec='milliseconds'),
        mode='modbus_rtu',
        raw_transport=raw_transport,
        interpreted=interpreted,
    )


# ---------- Active-send parsing ----------

def parse_active_send_frame(
    payload: bytes,
    profile: str,
    numeric_index: int,
    hex_word_endianness: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    hex_repr = payload.hex(' ')
    raw_transport: Dict[str, Any] = {
        'byte_count': len(payload),
        'hex': hex_repr,
        'ascii_preview': payload.decode('ascii', errors='replace'),
    }

    interpreted: Dict[str, Any] = {
        'parser_profile': profile,
        'raw_value': None,
        'timestamp_source': 'host_receive_time',
    }

    stripped = payload.strip()
    if not stripped:
        interpreted['parser_result'] = 'empty_frame'
        return raw_transport, interpreted

    if profile == 'line_ascii_float':
        text = stripped.decode('ascii', errors='replace')
        interpreted['line'] = text
        interpreted['raw_value'] = float(text)
        interpreted['parsed_from'] = 'single_ascii_float'
        return raw_transport, interpreted

    if profile == 'line_ascii_csv':
        text = stripped.decode('ascii', errors='replace')
        parts = [p.strip() for p in text.split(',') if p.strip()]
        interpreted['line'] = text
        interpreted['fields'] = parts
        interpreted['raw_value'] = float(parts[numeric_index])
        interpreted['parsed_from'] = f'csv_field_{numeric_index}'
        return raw_transport, interpreted

    if profile == 'hex_s32':
        compact = ''.join(ch for ch in stripped.decode('ascii', errors='ignore') if ch in '0123456789abcdefABCDEF')
        if len(compact) < 8:
            raise ValueError('Need at least 8 hex characters for hex_s32 profile')
        data = bytes.fromhex(compact[:8])
        byteorder = 'big' if hex_word_endianness == 'big' else 'little'
        value = int.from_bytes(data, byteorder=byteorder, signed=True)
        interpreted['hex_word_endianness'] = byteorder
        interpreted['raw_value'] = value
        interpreted['parsed_from'] = 'first_4_bytes_hex_signed32'
        interpreted['line'] = stripped.decode('ascii', errors='replace')
        return raw_transport, interpreted

    text = stripped.decode('ascii', errors='replace')
    interpreted['line'] = text
    candidates: List[float] = []
    for token in text.replace(';', ',').replace('|', ',').split(','):
        token = token.strip()
        if not token:
            continue
        try:
            candidates.append(float(token))
        except ValueError:
            continue
    interpreted['numeric_candidates'] = candidates
    if candidates:
        idx = max(0, min(numeric_index, len(candidates) - 1))
        interpreted['raw_value'] = candidates[idx]
        interpreted['parsed_from'] = f'auto_numeric_candidate_{idx}'
    else:
        interpreted['parsed_from'] = 'no_numeric_candidate_found'
    return raw_transport, interpreted


def extract_registers_from_modbus_response(frame: bytes, slave_id: int, function_code: int, register_count: int) -> List[int]:
    expected_byte_count = register_count * 2
    expected_len = 3 + expected_byte_count + 2
    if len(frame) != expected_len:
        raise ValueError(f'Unexpected frame length: got {len(frame)}, expected {expected_len}')
    if frame[0] != slave_id:
        raise ValueError(f'Unexpected slave id in active-send frame: got {frame[0]}, expected {slave_id}')
    if frame[1] != function_code:
        raise ValueError(f'Unexpected function code in active-send frame: got 0x{frame[1]:02X}, expected 0x{function_code:02X}')
    if frame[2] != expected_byte_count:
        raise ValueError(f'Unexpected byte count in active-send frame: got {frame[2]}, expected {expected_byte_count}')
    received_crc = frame[-2:]
    expected_crc = crc16_modbus(frame[:-2]).to_bytes(2, byteorder='little')
    if received_crc != expected_crc:
        raise ValueError(
            f'CRC mismatch in active-send frame: got {received_crc.hex()}, expected {expected_crc.hex()}, frame={frame.hex(" ")}'
        )
    data = frame[3:-2]
    regs: List[int] = []
    for i in range(0, len(data), 2):
        regs.append((data[i] << 8) | data[i + 1])
    return regs


def decode_active_send_modbus_response(
    frame: bytes,
    host_ts: float,
    slave_id: int,
    function_code: int,
    register_count: int,
    diagnostics: Dict[str, Any],
) -> MeasurementFrame:
    registers = extract_registers_from_modbus_response(frame, slave_id, function_code, register_count)
    decoded = decode_modbus_measurement(registers=registers, host_ts=host_ts)
    decoded.mode = 'active_send'
    decoded.raw_transport = {
        'response_hex': frame.hex(' '),
        'frame_length_bytes': len(frame),
        'frame_type': 'modbus_rtu_response_push',
        'registers': {f'400{idx + 1:02d}': reg for idx, reg in enumerate(registers, start=0)},
        'diagnostics': diagnostics,
    }
    decoded.interpreted.update({
        'parser_profile': 'modbus_rtu_response_11regs',
        'parsed_from': 'active_send_binary_modbus_response',
        'timestamp_source': 'host_receive_time',
    })
    return decoded


# ---------- Transport abstractions ----------

class BoardTransport:
    def connect(self) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def read_once(self) -> MeasurementFrame:
        raise NotImplementedError

    def read_frames(self) -> List[MeasurementFrame]:
        return [self.read_once()]

    def send_command(self, command_name: str) -> None:
        raise NotImplementedError


class ModbusBoardTransport(BoardTransport):
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.ser: Optional[serial.Serial] = None
        self.client: Optional[MinimalModbusRTU] = None
        self._last_host_ts: Optional[float] = None

    def connect(self) -> None:
        cfg = self.app_state.serial_cfg
        self.ser = serial.Serial(
            port=cfg.port,
            baudrate=cfg.baudrate,
            bytesize=cfg.bytesize,
            parity=cfg.parity,
            stopbits=cfg.stopbits,
            timeout=cfg.timeout,
        )
        self.client = MinimalModbusRTU(
            serial_port=self.ser,
            slave_id=int(self.app_state.cfg.device.slave_address),
            inter_frame_gap_s=float(self.app_state.cfg.serial.inter_frame_gap_s),
        )

    def disconnect(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.client = None

    def read_once(self) -> MeasurementFrame:
        if self.client is None:
            raise RuntimeError('Transport not connected')
        t_start = time.perf_counter()
        registers, request_payload, response = self.client.read_holding_registers(
            address=READ_START_REGISTER,
            count=READ_REGISTER_COUNT,
        )
        transaction_duration_s = time.perf_counter() - t_start
        host_ts = time.time()
        frame = decode_modbus_measurement(registers=registers, host_ts=host_ts)
        observed_inter_read_s: Optional[float] = None
        observed_inter_read_hz: Optional[float] = None
        if self._last_host_ts is not None:
            observed_inter_read_s = max(0.0, host_ts - self._last_host_ts)
            if observed_inter_read_s > 0:
                observed_inter_read_hz = 1.0 / observed_inter_read_s
        self._last_host_ts = host_ts
        frame.raw_transport['request_hex'] = request_payload.hex(' ')
        frame.raw_transport['response_hex'] = response.hex(' ')
        frame.raw_transport['diagnostics'] = {
            'timestamp_source': 'host_poll_receive_time',
            'configured_poll_interval_s': float(self.app_state.cfg.device.poll_interval_s),
            'observed_inter_read_s': observed_inter_read_s,
            'observed_inter_read_hz': observed_inter_read_hz,
            'transaction_duration_s': transaction_duration_s,
            'response_bytes': len(response),
        }
        frame.interpreted.update({
            'timestamp_source': 'host_poll_receive_time',
            'configured_poll_interval_s': float(self.app_state.cfg.device.poll_interval_s),
            'observed_inter_read_s': observed_inter_read_s,
            'observed_inter_read_hz': observed_inter_read_hz,
            'transaction_duration_s': transaction_duration_s,
            'response_bytes': len(response),
        })
        return frame

    def send_command(self, command_name: str) -> None:
        if self.client is None:
            raise RuntimeError('Transport not connected')
        if command_name not in COMMANDS:
            raise ValueError(f'Unsupported command: {command_name}')
        value = COMMANDS[command_name]
        request_payload, response = self.client.write_single_register(COMMAND_REGISTER, value)
        self.app_state.push_event(
            f'Sent command {command_name} ({value}) request={request_payload.hex(" ")} response={response.hex(" ")}'
        )


class ActiveSendBoardTransport(BoardTransport):
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.ser: Optional[serial.Serial] = None
        self.line_buffer = bytearray()
        self.binary_buffer = bytearray()
        self.header_length = 3

    def connect(self) -> None:
        cfg = self.app_state.serial_cfg
        self.ser = serial.Serial(
            port=cfg.port,
            baudrate=cfg.baudrate,
            bytesize=cfg.bytesize,
            parity=cfg.parity,
            stopbits=cfg.stopbits,
            timeout=cfg.timeout,
        )
        self.binary_buffer.clear()
        self.line_buffer.clear()
        self.app_state.active_send_stats = ActiveSendStats()
        if self.ser is not None:
            self.ser.reset_input_buffer()

    def disconnect(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.line_buffer.clear()
        self.binary_buffer.clear()

    def _maybe_log_active_warning(self, message: str) -> None:
        stats = self.app_state.active_send_stats
        stats.warning_events_total += 1
        now = time.monotonic()
        detailed_limit = int(getattr(self.app_state.cfg.active_send, 'detailed_warning_limit', 8))
        emit_interval_s = float(getattr(self.app_state.cfg.active_send, 'warning_emit_interval_s', 1.0))
        if stats.warning_events_total <= detailed_limit:
            LOGGER.warning(message)
            stats.last_warning_emit_monotonic = now
            return
        if now - stats.last_warning_emit_monotonic >= emit_interval_s:
            LOGGER.warning(
                'Active-send backlog summary: parsed_ok=%d batches=%d crc_failures=%d resyncs=%d overflow_events=%d overflow_bytes=%d discarded=%d buffer_len=%d max_buffer=%d max_in_waiting=%d suppressed=%d',
                stats.frames_ok,
                stats.frames_delivered,
                stats.crc_failures,
                stats.header_resyncs,
                stats.buffer_overflow_events,
                stats.buffer_overflow_bytes,
                stats.discarded_bytes,
                len(self.binary_buffer),
                stats.max_buffer_len,
                stats.max_in_waiting,
                stats.warning_suppressed,
            )
            stats.last_warning_emit_monotonic = now
            stats.warning_suppressed = 0
            return
        stats.warning_suppressed += 1

    def _update_active_watermarks(self) -> None:
        stats = self.app_state.active_send_stats
        stats.max_buffer_len = max(stats.max_buffer_len, len(self.binary_buffer))
        if self.ser is not None:
            try:
                stats.max_in_waiting = max(stats.max_in_waiting, int(self.ser.in_waiting))
            except Exception:
                pass

    def _extract_modbus_response_frames(
        self,
        *,
        header: bytes,
        expected_len: int,
        bad_hex_limit: int,
        max_buffer_bytes: int,
    ) -> List[bytes]:
        stats = self.app_state.active_send_stats
        frames: List[bytes] = []
        if len(self.binary_buffer) > max_buffer_bytes:
            overflow = len(self.binary_buffer) - max_buffer_bytes
            stats.discarded_bytes += overflow
            stats.buffer_overflow_events += 1
            stats.buffer_overflow_bytes += overflow
            del self.binary_buffer[:overflow]
            self._maybe_log_active_warning(
                f'Active-send buffer overflow: discarded {overflow} bytes to keep buffer <= {max_buffer_bytes}'
            )
        while True:
            idx = self.binary_buffer.find(header)
            if idx < 0:
                if len(self.binary_buffer) > self.header_length - 1:
                    discard = len(self.binary_buffer) - (self.header_length - 1)
                    if discard > 0:
                        stats.discarded_bytes += discard
                        del self.binary_buffer[:discard]
                break
            if idx > 0:
                prefix = bytes(self.binary_buffer[:idx])
                preview = prefix[:bad_hex_limit].hex(' ')
                stats.discarded_bytes += idx
                stats.header_resyncs += 1
                del self.binary_buffer[:idx]
                self._maybe_log_active_warning(
                    f'Active-send resync: discarded {idx} leading byte(s) before header {header.hex(" ")}; preview={preview}'
                )
            if len(self.binary_buffer) < expected_len:
                break
            candidate = bytes(self.binary_buffer[:expected_len])
            expected_crc = crc16_modbus(candidate[:-2]).to_bytes(2, byteorder='little')
            received_crc = candidate[-2:]
            if received_crc != expected_crc:
                stats.crc_failures += 1
                stats.last_bad_candidate_hex = candidate[:bad_hex_limit].hex(' ')
                del self.binary_buffer[0]
                stats.discarded_bytes += 1
                stats.header_resyncs += 1
                self._maybe_log_active_warning(
                    'Active-send CRC mismatch '
                    f'#{stats.crc_failures}: got={received_crc.hex()} expected={expected_crc.hex()} '
                    f'candidate_len={len(candidate)} preview={stats.last_bad_candidate_hex}'
                )
                continue
            del self.binary_buffer[:expected_len]
            frames.append(candidate)
            self._update_active_watermarks()
        return frames

    def _read_modbus_response_frames_batch(self) -> Tuple[List[bytes], Dict[str, Any]]:
        if self.ser is None:
            raise RuntimeError('Transport not connected')
        slave_id = int(getattr(self.app_state.cfg.active_send, 'frame_slave_id', 0) or 0)
        if slave_id <= 0:
            slave_id = int(self.app_state.cfg.device.slave_address)
        function_code = int(self.app_state.cfg.active_send.frame_function_code)
        register_count = int(self.app_state.cfg.active_send.frame_register_count)
        expected_byte_count = register_count * 2
        expected_len = 3 + expected_byte_count + 2
        header = bytes([slave_id, function_code, expected_byte_count])
        max_buffer_bytes = int(self.app_state.cfg.active_send.max_buffer_bytes)
        chunk_size = max(1, int(self.app_state.cfg.active_send.read_chunk_bytes))
        max_read_bytes = max(chunk_size, int(getattr(self.app_state.cfg.active_send, 'max_read_bytes_per_cycle', max_buffer_bytes)))
        read_timeout_s = float(self.app_state.cfg.active_send.read_timeout_s)
        delivery_window_s = float(getattr(self.app_state.cfg.active_send, 'delivery_window_s', 0.05))
        max_frames_per_delivery = max(1, int(getattr(self.app_state.cfg.active_send, 'max_frames_per_delivery', 64)))
        stats = self.app_state.active_send_stats
        log_first_n_good = int(self.app_state.cfg.active_send.log_first_n_good_frames)
        log_summary_every_n = int(self.app_state.cfg.active_send.log_summary_every_n_good_frames)
        bad_hex_limit = int(self.app_state.cfg.active_send.log_bad_frame_hex_bytes)

        frames_batch: List[bytes] = []
        batch_started_monotonic: Optional[float] = None
        read_deadline = time.monotonic() + read_timeout_s

        while time.monotonic() < read_deadline:
            if frames_batch and batch_started_monotonic is not None:
                if (time.monotonic() - batch_started_monotonic) >= delivery_window_s:
                    break
                if len(frames_batch) >= max_frames_per_delivery:
                    break

            try:
                pending = int(self.ser.in_waiting)
            except Exception:
                pending = 0
            read_size = max(chunk_size, min(max_read_bytes, pending if pending > 0 else chunk_size))
            chunk = self.ser.read(read_size)
            if not chunk:
                if frames_batch:
                    break
                continue

            if batch_started_monotonic is None:
                batch_started_monotonic = time.monotonic()

            stats.bytes_received += len(chunk)
            stats.chunks_received += 1
            self.binary_buffer.extend(chunk)
            self._update_active_watermarks()
            frames = self._extract_modbus_response_frames(
                header=header,
                expected_len=expected_len,
                bad_hex_limit=bad_hex_limit,
                max_buffer_bytes=max_buffer_bytes,
            )
            if frames:
                frames_batch.extend(frames)
                if len(frames_batch) >= max_frames_per_delivery:
                    break

        if not frames_batch:
            stats.timeouts += 1
            raise TimeoutError(
                'Timed out waiting for active-send Modbus-style frame batch '
                f'(parsed_ok={stats.frames_ok}, batches={stats.frames_delivered}, '
                f'crc_failures={stats.crc_failures}, resyncs={stats.header_resyncs}, '
                f'discarded_bytes={stats.discarded_bytes}, buffer_len={len(self.binary_buffer)}, '
                f'max_buffer={stats.max_buffer_len})'
            )

        stats.frames_ok += len(frames_batch)
        stats.frames_delivered += 1
        stats.last_good_frame_hex = frames_batch[-1].hex(' ')

        diagnostics = {
            'decoder': 'modbus_rtu_response_push_batch',
            'slave_id': slave_id,
            'function_code': function_code,
            'register_count': register_count,
            'frames_ok': stats.frames_ok,
            'batches_delivered': stats.frames_delivered,
            'frames_in_batch': len(frames_batch),
            'crc_failures': stats.crc_failures,
            'header_resyncs': stats.header_resyncs,
            'discarded_bytes': stats.discarded_bytes,
            'bytes_received_total': stats.bytes_received,
            'chunks_received_total': stats.chunks_received,
            'buffer_len': len(self.binary_buffer),
            'max_buffer_len': stats.max_buffer_len,
            'max_in_waiting': stats.max_in_waiting,
            'delivery_window_s': delivery_window_s,
            'max_frames_per_delivery': max_frames_per_delivery,
        }

        if stats.frames_delivered <= log_first_n_good:
            LOGGER.info(
                'Active-send delivered batch #%d: frames=%d first_len=%d last_len=%d last_hex=%s',
                stats.frames_delivered,
                len(frames_batch),
                len(frames_batch[0]),
                len(frames_batch[-1]),
                frames_batch[-1].hex(' '),
            )
        elif log_summary_every_n > 0 and (stats.frames_delivered % log_summary_every_n) == 0:
            LOGGER.info(
                'Active-send summary: parsed_ok=%d batches=%d bytes=%d crc_failures=%d resyncs=%d overflow_events=%d overflow_bytes=%d discarded=%d max_buffer=%d max_in_waiting=%d',
                stats.frames_ok,
                stats.frames_delivered,
                stats.bytes_received,
                stats.crc_failures,
                stats.header_resyncs,
                stats.buffer_overflow_events,
                stats.buffer_overflow_bytes,
                stats.discarded_bytes,
                stats.max_buffer_len,
                stats.max_in_waiting,
            )

        return frames_batch, diagnostics

    def _read_legacy_frame(self) -> bytes:
        if self.ser is None:
            raise RuntimeError('Transport not connected')
        deadline = time.time() + float(self.app_state.cfg.active_send.read_timeout_s)
        while time.time() < deadline:
            chunk = self.ser.read(max(1, int(self.app_state.cfg.active_send.read_chunk_bytes)))
            if not chunk:
                continue
            if b"\n" in chunk or b"\r" in chunk:
                self.line_buffer.extend(chunk)
                for sep in (b"\n", b"\r"):
                    if sep in self.line_buffer:
                        line, _, rest = self.line_buffer.partition(sep)
                        self.line_buffer = bytearray(rest)
                        if line.strip():
                            return bytes(line)
            else:
                self.line_buffer.extend(chunk)
                if len(self.line_buffer) >= int(self.app_state.cfg.active_send.max_binary_frame_bytes):
                    data = bytes(self.line_buffer)
                    self.line_buffer.clear()
                    return data
        if self.line_buffer:
            data = bytes(self.line_buffer)
            self.line_buffer.clear()
            return data
        raise TimeoutError('Timed out waiting for active-send frame')

    def read_frames(self) -> List[MeasurementFrame]:
        profile = self.app_state.parse_profile
        slave_id = int(getattr(self.app_state.cfg.active_send, 'frame_slave_id', 0) or 0)
        if slave_id <= 0:
            slave_id = int(self.app_state.cfg.device.slave_address)
        if profile == 'modbus_rtu_response_11regs':
            frame_bytes_batch, diagnostics = self._read_modbus_response_frames_batch()
            freq_hz = ACTIVE_SEND_FREQ_CODE_TO_VALUE.get(int(self.app_state.cfg.device.active_send_frequency_code), 0)
            batch_end_ts = time.time()
            frames: List[MeasurementFrame] = []
            if freq_hz > 0:
                dt = 1.0 / float(freq_hz)
                batch_start_ts = batch_end_ts - dt * (len(frame_bytes_batch) - 1)
            else:
                dt = 0.0
                batch_start_ts = batch_end_ts
            for idx, frame_bytes in enumerate(frame_bytes_batch):
                host_ts = batch_start_ts + idx * dt if freq_hz > 0 else batch_end_ts
                frame_diag = dict(diagnostics)
                frame_diag.update({
                    'batch_index': idx,
                    'batch_size': len(frame_bytes_batch),
                    'timestamp_source': 'reconstructed_from_active_send_rate' if freq_hz > 0 else 'host_batch_end_time',
                    'configured_frequency_hz': freq_hz,
                })
                frames.append(
                    decode_active_send_modbus_response(
                        frame=frame_bytes,
                        host_ts=host_ts,
                        slave_id=slave_id,
                        function_code=int(self.app_state.cfg.active_send.frame_function_code),
                        register_count=int(self.app_state.cfg.active_send.frame_register_count),
                        diagnostics=frame_diag,
                    )
                )
            return frames
        return [self.read_once()]

    def read_once(self) -> MeasurementFrame:
        host_ts = time.time()
        profile = self.app_state.parse_profile
        slave_id = int(getattr(self.app_state.cfg.active_send, 'frame_slave_id', 0) or 0)
        if slave_id <= 0:
            slave_id = int(self.app_state.cfg.device.slave_address)
        if profile == 'modbus_rtu_response_11regs':
            frames = self.read_frames()
            return frames[-1]
        payload = self._read_legacy_frame()
        raw_transport, interpreted = parse_active_send_frame(
            payload=payload,
            profile=profile,
            numeric_index=self.app_state.parse_numeric_index,
            hex_word_endianness=self.app_state.hex_word_endianness,
        )
        interpreted.update(
            {
                'timestamp_host_iso': datetime.fromtimestamp(host_ts).isoformat(timespec='milliseconds'),
                'timestamp_host_epoch_s': host_ts,
            }
        )
        return MeasurementFrame(
            host_ts=host_ts,
            host_ts_iso=datetime.fromtimestamp(host_ts).isoformat(timespec='milliseconds'),
            mode='active_send',
            raw_transport=raw_transport,
            interpreted=interpreted,
        )

    def send_command(self, command_name: str) -> None:
        raise RuntimeError('Commands are only implemented for Modbus RTU mode')


# ---------- Worker ----------

def acquisition_worker(app_state: AppState) -> None:
    assert app_state.transport is not None
    poll_interval_s = max(0.0, float(app_state.cfg.device.poll_interval_s))
    next_poll_deadline = time.perf_counter()
    app_state.push_event(f'Worker started in mode={app_state.mode} parser={app_state.parse_profile}')
    while not app_state.stop_event.is_set():
        try:
            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                now = time.perf_counter()
                if now < next_poll_deadline:
                    time.sleep(next_poll_deadline - now)
                cycle_start = time.perf_counter()
            else:
                cycle_start = time.perf_counter()
            frames = app_state.transport.read_frames()
            if not frames:
                if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                    next_poll_deadline = cycle_start + poll_interval_s
                continue
            processed_frames = app_state.filter_frames_by_max_sampling_rate(frames)
            if not processed_frames:
                app_state.status_text = (
                    f'Connected: batch filtered by max signal rate '
                    f'(received={len(frames)}, dropped_total={app_state.sampling_stats.dropped_samples_max_rate})'
                )
                if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                    next_poll_deadline = cycle_start + poll_interval_s
                continue
            app_state.push_frames(processed_frames)
            if app_state.signal_logger is not None:
                app_state.signal_logger.write_frames(processed_frames)
            last_frame = processed_frames[-1]
            app_state.status_text = f'Connected: last frame at {last_frame.host_ts_iso} (kept={len(processed_frames)}/{len(frames)})'
            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                next_poll_deadline = cycle_start + poll_interval_s
        except TimeoutError as exc:
            app_state.status_text = f'Waiting for data: {exc}'
            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                next_poll_deadline = time.perf_counter() + poll_interval_s
        except Exception as exc:  # pragma: no cover - runtime guard
            app_state.status_text = f'Acquisition error: {exc}'
            app_state.push_event(f'Acquisition error: {exc}')
            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                next_poll_deadline = time.perf_counter() + poll_interval_s
            time.sleep(float(app_state.cfg.device.error_backoff_s))
    app_state.push_event('Worker stopped')


# ---------- UI helpers ----------

def build_plot_figure(app_state: AppState) -> go.Figure:
    fig = go.Figure()
    signal_key = get_plot_signal_key(app_state.cfg)
    with app_state.frame_lock:
        frames = list(app_state.frame_history)
    points: List[Tuple[float, float]] = []
    for frame in frames:
        value = extract_signal_value(frame, signal_key)
        if value is not None:
            points.append((frame.host_ts, value))
    render_points = points
    max_render_points = int(getattr(app_state.cfg.ui, 'max_render_plot_points', 0))
    if app_state.mode == 'active_send':
        factor = int(getattr(app_state.cfg.ui, 'active_send_render_downsample_factor', 1))
    else:
        factor = int(getattr(app_state.cfg.ui, 'modbus_rtu_render_downsample_factor', 1))
    render_points = downsample_points_for_render(render_points, factor=factor, max_points=max_render_points)
    if render_points:
        if np is not None:
            arr = np.asarray(render_points, dtype=np.float64)
            t0 = float(arr[0, 0])
            xs = (arr[:, 0] - t0).tolist()
            ys = arr[:, 1].tolist()
        else:
            t0 = render_points[0][0]
            xs = [ts - t0 for ts, _ in render_points]
            ys = [val for _, val in render_points]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode='lines',
                name=get_plot_signal_label(app_state.cfg),
                hovertemplate='t=%{x:.6f}s<br>%{fullData.name}=%{y:.6g}<extra></extra>',
            )
        )
    fig.update_layout(
        title=f'Live signal ({get_plot_signal_label(app_state.cfg)})',
        xaxis_title='Seconds since current plot window start',
        yaxis_title=get_plot_signal_label(app_state.cfg),
        margin=dict(l=20, r=20, t=40, b=20),
        height=int(app_state.cfg.ui.plot_height_px),
        template='plotly_white',
        uirevision='plot-x-window',
    )
    fig.update_xaxes(uirevision='plot-x-window')
    fig.update_yaxes(uirevision=f'plot-y:{signal_key}')
    return fig


# ---------- Main app ----------

def configure_logging(cfg: DictConfig) -> None:
    level = getattr(logging, str(cfg.app.log_level).upper(), logging.INFO)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if bool(getattr(cfg.logger, 'debug_log_to_file', False)):
        log_dir = Path(str(cfg.logger.directory)).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)
        debug_log_path = log_dir / str(cfg.logger.debug_log_filename)
        file_mode = 'a' if str(cfg.logger.write_mode).lower() == 'append' else 'w'
        file_handler = logging.FileHandler(debug_log_path, mode=file_mode, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)



def cfg_to_serial_settings(cfg: DictConfig) -> SerialSettings:
    return SerialSettings(
        port=str(cfg.serial.default_port),
        baudrate=int(cfg.serial.default_baudrate),
        bytesize=int(cfg.serial.bytesize),
        parity=str(cfg.serial.default_parity),
        stopbits=int(cfg.serial.default_stopbits),
        timeout=float(cfg.serial.timeout_s),
    )



def disconnect_state(app_state: AppState) -> None:
    app_state.stop_event.set()
    if app_state.worker_thread and app_state.worker_thread.is_alive():
        app_state.worker_thread.join(timeout=float(app_state.cfg.app.worker_join_timeout_s))
    if app_state.transport is not None:
        try:
            app_state.transport.disconnect()
        except Exception as exc:  # pragma: no cover - cleanup guard
            app_state.push_event(f'Disconnect cleanup warning: {exc}')
    app_state.transport = None
    app_state.worker_thread = None
    app_state.connected = False
    app_state.connection_label = 'DISCONNECTED'
    app_state.status_text = 'Idle'
    if app_state.signal_logger is not None:
        app_state.signal_logger.close()



def connect_state(app_state: AppState) -> None:
    disconnect_state(app_state)
    app_state.stop_event = threading.Event()
    window_size = int(getattr(app_state.cfg.ui, 'sampling_rate_window_samples', 128))
    app_state.sampling_stats.reset_all(window_size)
    if bool(getattr(app_state.cfg.ui, 'clear_plot_on_connect', True)):
        app_state.clear_signal_trace(reason='new connection', reset_session_counters=True)
    else:
        app_state.sampling_stats.reset_all(window_size)
    mode = app_state.mode
    if mode == 'modbus_rtu':
        app_state.transport = ModbusBoardTransport(app_state)
    else:
        app_state.transport = ActiveSendBoardTransport(app_state)
    try:
        if app_state.signal_logger is not None:
            app_state.signal_logger.open()
        app_state.transport.connect()
    except Exception:
        if app_state.signal_logger is not None:
            app_state.signal_logger.close()
        app_state.transport = None
        raise
    app_state.worker_thread = threading.Thread(
        target=acquisition_worker,
        args=(app_state,),
        daemon=True,
        name='acquisition-worker',
    )
    app_state.worker_thread.start()
    app_state.connected = True
    app_state.connection_label = 'CONNECTED'
    app_state.status_text = f'Connected on {app_state.serial_cfg.port}'
    app_state.push_event(
        f'Connected to {app_state.serial_cfg.port} baud={app_state.serial_cfg.baudrate} parity={app_state.serial_cfg.parity} stopbits={app_state.serial_cfg.stopbits} mode={mode}'
    )
    if mode == 'active_send':
        app_state.push_event(
            'Active-send decoder config: '
            f'parser={app_state.parse_profile} chunk_bytes={int(app_state.cfg.active_send.read_chunk_bytes)} '
            f'timeout_s={float(app_state.cfg.active_send.read_timeout_s)} '
            f'frame_slave_id={int(getattr(app_state.cfg.active_send, "frame_slave_id", 0) or 0) or int(app_state.cfg.device.slave_address)} '
            f'function=0x{int(app_state.cfg.active_send.frame_function_code):02X} '
            f'registers={int(app_state.cfg.active_send.frame_register_count)}'
        )
    if app_state.signal_logger is not None and app_state.signal_logger.enabled:
        debug_log_path = None
        if bool(getattr(app_state.cfg.logger, 'debug_log_to_file', False)):
            debug_log_path = (app_state.signal_logger.directory / str(app_state.cfg.logger.debug_log_filename)).resolve()
        app_state.push_event(
            'Logger paths: '
            f'raw={app_state.signal_logger.raw_path.resolve()} | '
            f'interpreted={app_state.signal_logger.interpreted_path.resolve()} | '
            f'gui={app_state.signal_logger.gui_path.resolve()} | '
            f'events={app_state.signal_logger.event_path.resolve()}'
            + (f' | debug={debug_log_path}' if debug_log_path is not None else '')
        )


def load_app_config(argv: Optional[List[str]] = None) -> DictConfig:
    """Load config.yaml and apply OmegaConf/Hydra-style dotlist overrides.

    NiceGUI internally re-executes the script to serve the root page / 404 fallback.
    Using the @hydra.main decorator here causes a second GlobalHydra initialization and
    crashes the app. This loader preserves config.yaml + dotlist overrides without
    relying on Hydra's global runtime state.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    config_path = Path(__file__).with_name('config.yaml')
    cfg = OmegaConf.load(config_path)

    overrides: List[str] = []
    ignored: List[str] = []
    for arg in args:
        if arg in {'-h', '--help'}:
            print(
                'Usage: python acquisition_board_gui.py [key=value ...]\n\n'
                'Examples:\n'
                '  python acquisition_board_gui.py\n'
                '  python acquisition_board_gui.py ui.port=8090 serial.default_port=/dev/ttyUSB0\n'
                '  python acquisition_board_gui.py device.mode=active_send active_send.default_parser_profile=line_ascii_csv\n'
            )
            raise SystemExit(0)

        if arg.startswith('hydra.'):
            # Ignore Hydra-specific runtime flags to keep the script compatible with
            # previous invocation habits while avoiding GlobalHydra re-initialization.
            ignored.append(arg)
            continue

        if '=' in arg and not arg.startswith('--'):
            overrides.append(arg)
        else:
            ignored.append(arg)

    if overrides:
        cfg = OmegaConf.merge(cfg, OmegaConf.from_dotlist(overrides))

    configure_logging(cfg)

    if ignored:
        LOGGER.warning('Ignoring unsupported CLI args: %s', ignored)

    return cfg


def run_app(cfg: DictConfig) -> None:
    configure_logging(cfg)
    if os.environ.get('ACQ_GUI_CONFIG_LOGGED_ONCE') != '1':
        LOGGER.info('Loaded config:\n%s', OmegaConf.to_yaml(cfg))
        os.environ['ACQ_GUI_CONFIG_LOGGED_ONCE'] = '1'

    signal_logger = SignalFileLogger(cfg)
    app_state = AppState(
        cfg=cfg,
        serial_cfg=cfg_to_serial_settings(cfg),
        mode=str(cfg.device.mode),
        raw_log=deque(maxlen=int(cfg.ui.max_retained_log_entries)),
        interpreted_log=deque(maxlen=int(cfg.ui.max_retained_log_entries)),
        event_log=deque(maxlen=int(cfg.ui.max_retained_event_entries)),
        frame_history=deque(maxlen=int(cfg.ui.max_plot_points)),
        parse_profile=str(cfg.active_send.default_parser_profile),
        parse_numeric_index=int(cfg.active_send.default_numeric_index),
        hex_word_endianness=str(cfg.active_send.default_hex_word_endianness),
        signal_logger=signal_logger,
    )

    available_ports = enumerate_ports(list(cfg.serial.port_hints))

    dark_mode = ui.dark_mode()
    if bool(cfg.ui.light_mode):
        dark_mode.disable()
    else:
        dark_mode.enable()
    ui.page_title(cfg.ui.page_title)

    header = ui.label(cfg.ui.page_title).classes('text-2xl font-bold')
    header.style('padding: 12px 0;')

    status_label = ui.label('Status: Idle').classes('text-sm')

    with ui.card().classes('w-full'):
        ui.label('Connection').classes('text-lg font-semibold')
        with ui.grid(columns=4).classes('w-full gap-4'):
            port_select = ui.select(
                options={p.device: f'{p.device} | {p.description} | {p.hwid}' for p in available_ports},
                value=app_state.serial_cfg.port if app_state.serial_cfg.port else (available_ports[0].device if available_ports else None),
                label='Serial port',
            )
            mode_select = ui.select(
                options={'modbus_rtu': 'Modbus RTU (500.AS=0)', 'active_send': 'Active send (500.AS=1)'},
                value=app_state.mode,
                label='Board mode',
            )
            baud_select = ui.select(
                options={v: f'{v} (code {k})' for k, v in BAUD_CODE_TO_VALUE.items()},
                value=app_state.serial_cfg.baudrate,
                label='Baud rate',
            )
            address_input = ui.number(
                label='Slave address (500.Ar)',
                value=int(cfg.device.slave_address),
                min=1,
                max=253,
                step=1,
                format='%.0f',
            )
            parity_select = ui.select(
                options={'N': 'None (502.Vb=0)', 'E': 'Even (502.Vb=1)', 'O': 'Odd (502.Vb=2)'},
                value=app_state.serial_cfg.parity,
                label='Parity',
            )
            stopbits_select = ui.select(
                options={1: '1 stop bit (503.so=1)', 2: '2 stop bits (503.so=2)'},
                value=app_state.serial_cfg.stopbits,
                label='Stop bits',
            )
            active_freq_select = ui.select(
                options={
                    code: f'{freq_hz} Hz (505.AF={code})'
                    for code, freq_hz in ACTIVE_SEND_FREQ_CODE_TO_VALUE.items()
                },
                value=int(cfg.device.active_send_frequency_code),
                label='Active-send frequency',
            )
            parser_select = ui.select(
                options={
                    'modbus_rtu_response_11regs': 'modbus_rtu_response_11regs',
                    'line_ascii_auto': 'line_ascii_auto',
                    'line_ascii_float': 'line_ascii_float',
                    'line_ascii_csv': 'line_ascii_csv',
                    'hex_s32': 'hex_s32',
                },
                value=app_state.parse_profile,
                label='Active-send parser profile',
            )
            numeric_index_input = ui.number(
                label='Active-send numeric field index',
                value=app_state.parse_numeric_index,
                min=0,
                max=32,
                step=1,
                format='%.0f',
            )
            hex_endianness_select = ui.select(
                options={'big': 'big', 'little': 'little'},
                value=app_state.hex_word_endianness,
                label='hex_s32 byte order',
            )

        with ui.row().classes('gap-2 mt-4'):
            def refresh_port_list() -> None:
                ports = enumerate_ports(list(cfg.serial.port_hints))
                options = {p.device: f'{p.device} | {p.description} | {p.hwid}' for p in ports}
                port_select.options = options
                if options and port_select.value not in options:
                    port_select.value = next(iter(options.keys()))
                port_select.update()
                app_state.push_event(f'Refreshed port list: {len(options)} ports found')

            def sync_form_to_state() -> None:
                app_state.serial_cfg.port = str(port_select.value or '')
                app_state.serial_cfg.baudrate = int(baud_select.value)
                app_state.serial_cfg.parity = str(parity_select.value)
                app_state.serial_cfg.stopbits = int(stopbits_select.value)
                app_state.mode = str(mode_select.value)
                app_state.parse_profile = str(parser_select.value)
                app_state.parse_numeric_index = int(numeric_index_input.value or 0)
                app_state.hex_word_endianness = str(hex_endianness_select.value)
                cfg.device.slave_address = int(address_input.value)
                cfg.device.active_send_frequency_code = int(active_freq_select.value)
                cfg.ui.plot_signal_key = str(signal_select.value)
                cfg.ui.clear_plot_on_connect = bool(clear_on_connect_switch.value)

            def on_connect() -> None:
                sync_form_to_state()
                connect_state(app_state)

            def on_disconnect() -> None:
                disconnect_state(app_state)
                app_state.push_event('Disconnected by user')

            ui.button('Refresh ports', on_click=refresh_port_list)
            ui.button('Connect', on_click=on_connect)
            ui.button('Disconnect', on_click=on_disconnect)
            connection_badge = ui.badge(app_state.connection_label)

        ui.separator().classes('mt-4 mb-2')
        ui.label('Current effective board-side communication settings you should mirror on the instrument').classes('text-lg font-semibold')
        board_cfg_preview = ui.textarea(value='', label='Board-side values to mirror').props('readonly').classes('w-full font-mono')
        board_cfg_preview.style('height: 180px; overflow-y: auto; overflow-x: auto; white-space: pre;')

    with ui.card().classes('w-full mt-4'):
        ui.label('Live signal').classes('text-lg font-semibold')
        with ui.row().classes('w-full items-center gap-3 flex-wrap'):
            signal_select = ui.select(
                options=get_plot_signal_options(),
                value=get_plot_signal_key(cfg),
                label='Plotted signal',
            )
            clear_trace_button = ui.button('Clear signal trace')
            clear_on_connect_switch = ui.switch(
                'Clear signal trace on new connection',
                value=bool(getattr(cfg.ui, 'clear_plot_on_connect', True)),
            )
        with ui.row().classes('w-full gap-4 items-start mt-2 no-wrap'):
            with ui.card().classes('w-3/4'):
                plot = ui.plotly(build_plot_figure(app_state)).classes('w-full')
            with ui.column().classes('w-1/4 gap-3'):
                with ui.card().classes('w-full'):
                    ui.label('Measured sampling rate').classes('text-base font-semibold')
                    sampling_rate_label = ui.label('').classes('w-full text-sm')
                    sampling_rate_label.style('white-space: pre-wrap;')
                with ui.expansion('Selected signal info').classes('w-full'):
                    signal_metadata_label = ui.label('').classes('w-full text-xs font-mono')
                    signal_metadata_label.style('white-space: pre-wrap;')

        def on_signal_change() -> None:
            cfg.ui.plot_signal_key = str(signal_select.value)
            plot.figure = build_plot_figure(app_state)
            plot.update()

        signal_select.on('update:model-value', lambda _event: on_signal_change())
        clear_trace_button.on('click', lambda _event: app_state.clear_signal_trace(reason='manual clear button', reset_session_counters=False))
        clear_on_connect_switch.on('update:model-value', lambda _event: setattr(cfg.ui, 'clear_plot_on_connect', bool(clear_on_connect_switch.value)))
    with ui.row().classes('w-full gap-4 items-start mt-4 no-wrap'):
        with ui.card().classes('w-1/2'):
            ui.label('Raw transport / raw interpreted').classes('text-lg font-semibold')
            raw_log_area = ui.textarea(value='', label='Raw log').props('readonly').classes('w-full font-mono')
            raw_log_area.style(f'height: {cfg.ui.log_height_px}px; overflow-y: auto; overflow-x: auto; white-space: pre;')
        with ui.card().classes('w-1/2'):
            ui.label('Interpreted data').classes('text-lg font-semibold')
            interpreted_log_area = ui.textarea(value='', label='Interpreted log').props('readonly').classes('w-full font-mono')
            interpreted_log_area.style(f'height: {cfg.ui.log_height_px}px; overflow-y: auto; overflow-x: auto; white-space: pre;')

    with ui.card().classes('w-full mt-4'):
        ui.label('Event log').classes('text-lg font-semibold')
        event_log_area = ui.textarea(value='', label='Events').props('readonly').classes('w-full font-mono')
        event_log_area.style(f'height: {cfg.ui.event_log_height_px}px; overflow-y: auto; overflow-x: auto; white-space: pre;')

    with ui.expansion('Advanced Actions').classes('w-full mt-4') as advanced_actions_expansion:
        ui.label('These actions write to register 40012 and are only available in Modbus RTU mode (500.AS=0).').classes('text-sm')
        advanced_action_buttons: List[Any] = []
        with ui.column().classes('w-full gap-2'):
            for command_meta in COMMAND_METADATA:
                def _make_handler(name: str):
                    def _handler() -> None:
                        if app_state.transport is None:
                            ui.notify('Not connected')
                            return
                        try:
                            app_state.transport.send_command(name)
                            ui.notify(f'Sent {name}')
                        except Exception as exc:
                            app_state.push_event(f'Command failed: {name} -> {exc}')
                            ui.notify(f'Command failed: {exc}', color='negative')
                    return _handler

                with ui.row().classes('w-full items-start gap-4 no-wrap'):
                    button = ui.button(command_meta['title'], on_click=_make_handler(command_meta['name']))
                    advanced_action_buttons.append(button)
                    desc = ui.label(
                        f"{command_meta['description']}\nEquivalent manual action: {command_meta['manual_equivalent']}"
                    ).classes('text-sm')
                    desc.style('white-space: pre-wrap;')

    refresh_counter = {'count': 0}

    def refresh_ui() -> None:
        refresh_counter['count'] += 1
        status_text = f'Status: {app_state.status_text}'
        if status_label.text != status_text:
            status_label.text = status_text
            status_label.update()
        if connection_badge.text != app_state.connection_label:
            connection_badge.text = app_state.connection_label
            connection_badge.update()
        visible_log_entries = int(cfg.ui.visible_log_entries)
        visible_event_entries = int(cfg.ui.visible_event_entries)
        max_log_chars = int(getattr(cfg.ui, 'max_log_textarea_chars', 120000))
        max_event_chars = int(getattr(cfg.ui, 'max_event_textarea_chars', 40000))

        raw_log_items = list(app_state.raw_log)
        interpreted_log_items = list(app_state.interpreted_log)
        event_log_items = list(app_state.event_log)
        if visible_log_entries > 0:
            raw_log_items = raw_log_items[:visible_log_entries]
            interpreted_log_items = interpreted_log_items[:visible_log_entries]
        if visible_event_entries > 0:
            event_log_items = event_log_items[:visible_event_entries]

        raw_text = build_log_text(raw_log_items, '\n', max_log_chars)
        interpreted_text = build_log_text(interpreted_log_items, '\n', max_log_chars)
        event_text = build_log_text(event_log_items, '\n', max_event_chars)
        if raw_log_area.value != raw_text:
            raw_log_area.value = raw_text
            raw_log_area.update()
        if interpreted_log_area.value != interpreted_text:
            interpreted_log_area.value = interpreted_text
            interpreted_log_area.update()
        if event_log_area.value != event_text:
            event_log_area.value = event_text
            event_log_area.update()

        plot_stride = max(1, int(getattr(cfg.ui, 'plot_update_every_n_refreshes', 1)))
        if signal_select.value != get_plot_signal_key(cfg):
            signal_select.value = get_plot_signal_key(cfg)
            signal_select.update()
        if (refresh_counter['count'] % plot_stride) == 0:
            plot.figure = build_plot_figure(app_state)
            plot.update()

        sampling_stats = app_state.sampling_stats
        target_hz = get_target_sampling_rate_hz(cfg, str(mode_select.value))
        max_hz = float(getattr(cfg.ui, 'max_signal_samples_per_second', 0.0) or 0.0)
        mean_hz, std_hz, window_count, received_count, dropped_count = sampling_stats.snapshot()
        sampling_text = (
            f'Target sampling rate: {format_rate(target_hz)}\n'
            f'Measured mean rate: {format_rate(mean_hz)}\n'
            f'Measured std-dev: {format_rate(std_hz)}\n'
            f'Window size: last {window_count} intervals / configured {int(getattr(cfg.ui, "sampling_rate_window_samples", 128))}\n'
            f'Samples received: {received_count}\n'
            f'Samples dropped by max-rate limiter: {dropped_count}\n'
            f'Configured max processed sampling rate: {format_rate(max_hz)}'
        )
        if sampling_rate_label.text != sampling_text:
            sampling_rate_label.text = sampling_text
            sampling_rate_label.update()

        signal_metadata_text = build_signal_metadata_text(app_state)
        if signal_metadata_label.text != signal_metadata_text:
            signal_metadata_label.text = signal_metadata_text
            signal_metadata_label.update()

        baud_code = next((k for k, v in BAUD_CODE_TO_VALUE.items() if v == int(baud_select.value)), None)
        parity_code = {'N': 0, 'E': 1, 'O': 2}.get(str(parity_select.value), '?')
        stop_code = int(stopbits_select.value)
        active_code = int(active_freq_select.value)
        board_cfg_text = (
            f'500.Ar = {int(address_input.value)}\n'
            f'501.br = {baud_code}  # {int(baud_select.value)} bps\n'
            f'502.Vb = {parity_code}  # {parity_select.value}\n'
            f'503.so = {stop_code}\n'
            f'504.AS = {0 if str(mode_select.value) == "modbus_rtu" else 1}\n'
            f'505.AF = {active_code}  # {ACTIVE_SEND_FREQ_CODE_TO_VALUE[active_code]} Hz\n'
        )
        if board_cfg_preview.value != board_cfg_text:
            board_cfg_preview.value = board_cfg_text
            board_cfg_preview.update()

        advanced_enabled = str(mode_select.value) == 'modbus_rtu'
        try:
            if advanced_enabled:
                advanced_actions_expansion.enable()
            else:
                advanced_actions_expansion.disable()
        except Exception:
            pass
        for button in advanced_action_buttons:
            try:
                if advanced_enabled and app_state.connected:
                    button.enable()
                else:
                    button.disable()
            except Exception:
                pass

    ui.timer(interval=float(cfg.ui.refresh_interval_s), callback=refresh_ui)

    def cleanup() -> None:
        disconnect_state(app_state)

    app.on_shutdown(cleanup)
    ui.run(host=str(cfg.ui.host), port=int(cfg.ui.port), reload=False, title=str(cfg.ui.page_title))


def main() -> None:
    cfg = load_app_config()
    run_app(cfg)


if __name__ in {'__main__', '__mp_main__'}:
    main()
