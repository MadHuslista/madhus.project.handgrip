from __future__ import annotations

import csv
import json
import logging
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
    timeouts: int = 0
    crc_failures: int = 0
    header_resyncs: int = 0
    discarded_bytes: int = 0
    last_good_frame_hex: str = ''
    last_bad_candidate_hex: str = ''


class SignalFileLogger:
    def __init__(self, cfg: DictConfig):
        self.enabled = bool(getattr(cfg.logger, 'enabled', False))
        self.directory = Path(str(cfg.logger.directory)).expanduser()
        self.write_mode = str(cfg.logger.write_mode).lower()
        if self.write_mode not in {'append', 'overwrite'}:
            raise ValueError(f'logger.write_mode must be append or overwrite, got {self.write_mode}')

        self.raw_path = self.directory / str(cfg.logger.raw_signal_filename)
        self.interpreted_path = self.directory / str(cfg.logger.interpreted_signal_filename)
        self.gui_path = self.directory / str(cfg.logger.gui_signal_filename)

        self._raw_fp: Optional[TextIO] = None
        self._interpreted_fp: Optional[TextIO] = None
        self._gui_fp: Optional[TextIO] = None
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
        self._gui_writer = csv.writer(self._gui_fp)

        if self.write_mode == 'overwrite' or not gui_file_preexisting:
            self._gui_writer.writerow(['host_ts_epoch_s', 'host_ts_iso', 'mode', 'raw_value'])
            self._gui_fp.flush()

    def close(self) -> None:
        with self._lock:
            for fp in (self._raw_fp, self._interpreted_fp, self._gui_fp):
                if fp is not None and not fp.closed:
                    fp.flush()
                    fp.close()
            self._raw_fp = None
            self._interpreted_fp = None
            self._gui_fp = None
            self._gui_writer = None

    def write_frame(self, frame: MeasurementFrame) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._raw_fp is None or self._interpreted_fp is None or self._gui_fp is None or self._gui_writer is None:
                raise RuntimeError('SignalFileLogger.write_frame called before open()')

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
            self._gui_writer.writerow([frame.host_ts, frame.host_ts_iso, frame.mode, raw_value])

            self._raw_fp.flush()
            self._interpreted_fp.flush()
            self._gui_fp.flush()

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
    plot_points: Deque[Tuple[float, float]] = field(default_factory=lambda: deque(maxlen=5000))
    parse_profile: str = 'line_ascii_auto'
    parse_numeric_index: int = 0
    hex_word_endianness: str = 'big'
    signal_logger: Optional[SignalFileLogger] = None
    active_send_stats: ActiveSendStats = field(default_factory=ActiveSendStats)

    def push_event(self, message: str) -> None:
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line = f'[{ts}] {message}'
        self.event_log.appendleft(line)
        LOGGER.info(message)

    def push_frame(self, frame: MeasurementFrame) -> None:
        with self.frame_lock:
            self.latest_frame = frame
        self.raw_log.appendleft(json.dumps(frame.raw_transport, ensure_ascii=False, indent=2))
        self.interpreted_log.appendleft(json.dumps(frame.interpreted, ensure_ascii=False, indent=2))

        if 'raw_value' in frame.interpreted and frame.interpreted['raw_value'] is not None:
            self.plot_points.append((frame.host_ts, float(frame.interpreted['raw_value'])))

        if self.signal_logger is not None:
            self.signal_logger.write_frame(frame)


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

    def _exchange(self, payload: bytes, expected_min_len: int) -> bytes:
        frame = payload + crc16_modbus(payload).to_bytes(2, byteorder='little')
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(frame)
            self.ser.flush()
            time.sleep(self.inter_frame_gap_s)
            response = self.ser.read(256)
        if len(response) < expected_min_len:
            raise ModbusError(f'Short response: expected at least {expected_min_len} bytes, got {len(response)} bytes')
        if len(response) < 5:
            raise ModbusError('Invalid RTU response length')
        data, received_crc = response[:-2], response[-2:]
        expected_crc = crc16_modbus(data).to_bytes(2, byteorder='little')
        if received_crc != expected_crc:
            raise ModbusError(
                f'CRC mismatch: got {received_crc.hex()}, expected {expected_crc.hex()}, frame={response.hex(" ")}'
            )
        if data[0] != self.slave_id:
            raise ModbusError(f'Unexpected slave id: got {data[0]}, expected {self.slave_id}')
        if data[1] & 0x80:
            code = data[2] if len(data) > 2 else None
            raise ModbusError(f'Modbus exception function=0x{data[1]:02X} code={code}')
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
        response = self._exchange(payload, expected_min_len=expected_min_len)
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
        response = self._exchange(payload, expected_min_len=8)
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

    def send_command(self, command_name: str) -> None:
        raise NotImplementedError


class ModbusBoardTransport(BoardTransport):
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.ser: Optional[serial.Serial] = None
        self.client: Optional[MinimalModbusRTU] = None

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
        registers, request_payload, response = self.client.read_holding_registers(
            address=READ_START_REGISTER,
            count=READ_REGISTER_COUNT,
        )
        frame = decode_modbus_measurement(registers=registers, host_ts=time.time())
        frame.raw_transport['request_hex'] = request_payload.hex(' ')
        frame.raw_transport['response_hex'] = response.hex(' ')
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

    def _read_modbus_response_frame(self) -> Tuple[bytes, Dict[str, Any]]:
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
        deadline = time.time() + float(self.app_state.cfg.active_send.read_timeout_s)
        stats = self.app_state.active_send_stats
        log_first_n_good = int(self.app_state.cfg.active_send.log_first_n_good_frames)
        log_summary_every_n = int(self.app_state.cfg.active_send.log_summary_every_n_good_frames)
        bad_hex_limit = int(self.app_state.cfg.active_send.log_bad_frame_hex_bytes)
        while time.time() < deadline:
            chunk = self.ser.read(chunk_size)
            if not chunk:
                continue
            stats.bytes_received += len(chunk)
            stats.chunks_received += 1
            self.binary_buffer.extend(chunk)
            if len(self.binary_buffer) > max_buffer_bytes:
                overflow = len(self.binary_buffer) - max_buffer_bytes
                stats.discarded_bytes += overflow
                del self.binary_buffer[:overflow]
                LOGGER.warning(
                    'Active-send buffer overflow: discarded %d bytes to keep buffer <= %d bytes',
                    overflow,
                    max_buffer_bytes,
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
                    LOGGER.warning(
                        'Active-send resync: discarded %d leading byte(s) before header %s; preview=%s',
                        idx,
                        header.hex(' '),
                        preview,
                    )
                    del self.binary_buffer[:idx]
                if len(self.binary_buffer) < expected_len:
                    break
                candidate = bytes(self.binary_buffer[:expected_len])
                expected_crc = crc16_modbus(candidate[:-2]).to_bytes(2, byteorder='little')
                received_crc = candidate[-2:]
                if received_crc != expected_crc:
                    stats.crc_failures += 1
                    stats.last_bad_candidate_hex = candidate[:bad_hex_limit].hex(' ')
                    LOGGER.warning(
                        'Active-send CRC mismatch #%d: got=%s expected=%s candidate_len=%d preview=%s',
                        stats.crc_failures,
                        received_crc.hex(),
                        expected_crc.hex(),
                        len(candidate),
                        stats.last_bad_candidate_hex,
                    )
                    del self.binary_buffer[0]
                    stats.discarded_bytes += 1
                    stats.header_resyncs += 1
                    continue
                del self.binary_buffer[:expected_len]
                stats.frames_ok += 1
                stats.last_good_frame_hex = candidate.hex(' ')
                diagnostics = {
                    'decoder': 'modbus_rtu_response_push',
                    'slave_id': slave_id,
                    'function_code': function_code,
                    'register_count': register_count,
                    'frames_ok': stats.frames_ok,
                    'crc_failures': stats.crc_failures,
                    'header_resyncs': stats.header_resyncs,
                    'discarded_bytes': stats.discarded_bytes,
                    'bytes_received_total': stats.bytes_received,
                    'chunks_received_total': stats.chunks_received,
                }
                if stats.frames_ok <= log_first_n_good:
                    LOGGER.info('Active-send good frame #%d: len=%d hex=%s', stats.frames_ok, len(candidate), candidate.hex(' '))
                elif log_summary_every_n > 0 and (stats.frames_ok % log_summary_every_n) == 0:
                    LOGGER.info(
                        'Active-send summary: frames_ok=%d bytes=%d crc_failures=%d resyncs=%d discarded=%d',
                        stats.frames_ok,
                        stats.bytes_received,
                        stats.crc_failures,
                        stats.header_resyncs,
                        stats.discarded_bytes,
                    )
                return candidate, diagnostics
        stats.timeouts += 1
        raise TimeoutError(
            'Timed out waiting for active-send Modbus-style frame '
            f'(frames_ok={stats.frames_ok}, crc_failures={stats.crc_failures}, '
            f'resyncs={stats.header_resyncs}, discarded_bytes={stats.discarded_bytes}, '
            f'buffer_len={len(self.binary_buffer)})'
        )

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

    def read_once(self) -> MeasurementFrame:
        host_ts = time.time()
        profile = self.app_state.parse_profile
        slave_id = int(getattr(self.app_state.cfg.active_send, 'frame_slave_id', 0) or 0)
        if slave_id <= 0:
            slave_id = int(self.app_state.cfg.device.slave_address)
        if profile == 'modbus_rtu_response_11regs':
            frame_bytes, diagnostics = self._read_modbus_response_frame()
            return decode_active_send_modbus_response(
                frame=frame_bytes,
                host_ts=host_ts,
                slave_id=slave_id,
                function_code=int(self.app_state.cfg.active_send.frame_function_code),
                register_count=int(self.app_state.cfg.active_send.frame_register_count),
                diagnostics=diagnostics,
            )
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
        raise RuntimeError('Active-send mode has no documented command payload in the manual; use Modbus RTU mode for write operations.')


# ---------- Worker ----------

def acquisition_worker(app_state: AppState) -> None:
    assert app_state.transport is not None
    poll_interval_s = float(app_state.cfg.device.poll_interval_s)
    app_state.push_event(f'Worker started in mode={app_state.mode} parser={app_state.parse_profile}')
    while not app_state.stop_event.is_set():
        try:
            frame = app_state.transport.read_once()
            app_state.push_frame(frame)
            app_state.status_text = f'Connected: last frame at {frame.host_ts_iso}'
            if app_state.mode == 'modbus_rtu':
                time.sleep(poll_interval_s)
        except TimeoutError as exc:
            app_state.status_text = f'Waiting for data: {exc}'
        except Exception as exc:  # pragma: no cover - runtime guard
            app_state.status_text = f'Acquisition error: {exc}'
            app_state.push_event(f'Acquisition error: {exc}')
            time.sleep(float(app_state.cfg.device.error_backoff_s))
    app_state.push_event('Worker stopped')


# ---------- UI helpers ----------

def build_plot_figure(app_state: AppState) -> go.Figure:
    fig = go.Figure()
    with app_state.frame_lock:
        points = list(app_state.plot_points)
    if points:
        t0 = points[0][0]
        xs = [ts - t0 for ts, _ in points]
        ys = [val for _, val in points]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode='lines',
                name='raw_value',
            )
        )
    fig.update_layout(
        title='Live signal (host-relative time vs raw interpreted value)',
        xaxis_title='Seconds since current plot window start',
        yaxis_title='Raw interpreted value',
        margin=dict(l=20, r=20, t=40, b=20),
        height=int(app_state.cfg.ui.plot_height_px),
        template='plotly_white',
    )
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
        app_state.push_event(
            f'Signal logger active dir={app_state.signal_logger.directory} mode={app_state.signal_logger.write_mode} files=({app_state.signal_logger.raw_path.name}, {app_state.signal_logger.interpreted_path.name}, {app_state.signal_logger.gui_path.name})'
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
    LOGGER.info('Loaded config:\n%s', OmegaConf.to_yaml(cfg))

    signal_logger = SignalFileLogger(cfg)
    app_state = AppState(
        cfg=cfg,
        serial_cfg=cfg_to_serial_settings(cfg),
        mode=str(cfg.device.mode),
        raw_log=deque(maxlen=int(cfg.ui.max_retained_log_entries)),
        interpreted_log=deque(maxlen=int(cfg.ui.max_retained_log_entries)),
        event_log=deque(maxlen=int(cfg.ui.max_retained_event_entries)),
        plot_points=deque(maxlen=int(cfg.ui.max_plot_points)),
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

    with ui.card().classes('w-full mt-4'):
        ui.label('Modbus actions / commands').classes('text-lg font-semibold')
        ui.label('These write to register 40012. They only work when the board is in Modbus RTU mode (500.AS=0).').classes('text-sm')
        with ui.row().classes('gap-2 flex-wrap'):
            for command_name in COMMANDS:
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

                ui.button(command_name, on_click=_make_handler(command_name))

    with ui.card().classes('w-full mt-4'):
        ui.label('Live signal').classes('text-lg font-semibold')
        plot = ui.plotly(build_plot_figure(app_state)).classes('w-full')

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

    with ui.card().classes('w-full mt-4'):
        ui.label('Current effective board-side communication settings you should mirror on the instrument').classes('text-lg font-semibold')
        board_cfg_preview = ui.textarea(value='', label='Board-side values to mirror').props('readonly').classes('w-full font-mono')
        board_cfg_preview.style('height: 180px; overflow-y: auto; overflow-x: auto; white-space: pre;')

    def refresh_ui() -> None:
        status_label.text = f'Status: {app_state.status_text}'
        status_label.update()
        connection_badge.text = app_state.connection_label
        connection_badge.update()
        visible_log_entries = int(cfg.ui.visible_log_entries)
        visible_event_entries = int(cfg.ui.visible_event_entries)

        raw_log_items = list(app_state.raw_log)
        interpreted_log_items = list(app_state.interpreted_log)
        event_log_items = list(app_state.event_log)
        if visible_log_entries > 0:
            raw_log_items = raw_log_items[:visible_log_entries]
            interpreted_log_items = interpreted_log_items[:visible_log_entries]
        if visible_event_entries > 0:
            event_log_items = event_log_items[:visible_event_entries]

        raw_log_area.value = '\n\n'.join(raw_log_items)
        raw_log_area.update()
        interpreted_log_area.value = '\n\n'.join(interpreted_log_items)
        interpreted_log_area.update()
        event_log_area.value = '\n'.join(event_log_items)
        event_log_area.update()
        plot.figure = build_plot_figure(app_state)
        plot.update()

        baud_code = next((k for k, v in BAUD_CODE_TO_VALUE.items() if v == int(baud_select.value)), None)
        parity_code = {'N': 0, 'E': 1, 'O': 2}.get(str(parity_select.value), '?')
        stop_code = int(stopbits_select.value)
        active_code = int(active_freq_select.value)
        board_cfg_preview.value = (
            f'500.Ar = {int(address_input.value)}\n'
            f'501.br = {baud_code}  # {int(baud_select.value)} bps\n'
            f'502.Vb = {parity_code}  # {parity_select.value}\n'
            f'503.so = {stop_code}\n'
            f'504.AS = {0 if str(mode_select.value) == "modbus_rtu" else 1}\n'
            f'505.AF = {active_code}  # {ACTIVE_SEND_FREQ_CODE_TO_VALUE[active_code]} Hz\n'
        )
        board_cfg_preview.update()

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
