from __future__ import annotations

import binascii
import json
import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import hydra
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

    # default: line_ascii_auto
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

    def disconnect(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.line_buffer.clear()

    def _read_frame(self) -> bytes:
        if self.ser is None:
            raise RuntimeError('Transport not connected')
        deadline = time.time() + float(self.app_state.cfg.active_send.read_timeout_s)
        while time.time() < deadline:
            chunk = self.ser.read(max(1, int(self.app_state.cfg.active_send.read_chunk_bytes)))
            if not chunk:
                continue
            if b'\n' in chunk or b'\r' in chunk:
                self.line_buffer.extend(chunk)
                for sep in (b'\n', b'\r'):
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
        payload = self._read_frame()
        raw_transport, interpreted = parse_active_send_frame(
            payload=payload,
            profile=self.app_state.parse_profile,
            numeric_index=self.app_state.parse_numeric_index,
            hex_word_endianness=self.app_state.hex_word_endianness,
        )
        host_ts = time.time()
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
    app_state.push_event(f'Worker started in mode={app_state.mode}')
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
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    )



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



def connect_state(app_state: AppState) -> None:
    disconnect_state(app_state)
    app_state.stop_event = threading.Event()
    mode = app_state.mode
    if mode == 'modbus_rtu':
        app_state.transport = ModbusBoardTransport(app_state)
    else:
        app_state.transport = ActiveSendBoardTransport(app_state)
    app_state.transport.connect()
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


@hydra.main(version_base=None, config_path='.', config_name='config')
def main(cfg: DictConfig) -> None:
    configure_logging(cfg)
    LOGGER.info('Loaded config:\n%s', OmegaConf.to_yaml(cfg))

    app_state = AppState(
        cfg=cfg,
        serial_cfg=cfg_to_serial_settings(cfg),
        mode=str(cfg.device.mode),
        parse_profile=str(cfg.active_send.default_parser_profile),
        parse_numeric_index=int(cfg.active_send.default_numeric_index),
        hex_word_endianness=str(cfg.active_send.default_hex_word_endianness),
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
            raw_log_area = ui.textarea(value='', label='Raw log').props('readonly autogrow').classes('w-full')
            raw_log_area.style(f'height: {cfg.ui.log_height_px}px;')
        with ui.card().classes('w-1/2'):
            ui.label('Interpreted data').classes('text-lg font-semibold')
            interpreted_log_area = ui.textarea(value='', label='Interpreted log').props('readonly autogrow').classes('w-full')
            interpreted_log_area.style(f'height: {cfg.ui.log_height_px}px;')

    with ui.card().classes('w-full mt-4'):
        ui.label('Event log').classes('text-lg font-semibold')
        event_log_area = ui.textarea(value='', label='Events').props('readonly autogrow').classes('w-full')
        event_log_area.style(f'height: {cfg.ui.event_log_height_px}px;')

    with ui.card().classes('w-full mt-4'):
        ui.label('Current effective board-side communication settings you should mirror on the instrument').classes('text-lg font-semibold')
        board_cfg_preview = ui.textarea(value='', label='Board-side values to mirror').props('readonly autogrow').classes('w-full')

    def refresh_ui() -> None:
        status_label.text = f'Status: {app_state.status_text}'
        status_label.update()
        connection_badge.text = app_state.connection_label
        connection_badge.update()
        raw_log_area.value = '\n\n'.join(list(app_state.raw_log)[: int(cfg.ui.visible_log_entries)])
        raw_log_area.update()
        interpreted_log_area.value = '\n\n'.join(list(app_state.interpreted_log)[: int(cfg.ui.visible_log_entries)])
        interpreted_log_area.update()
        event_log_area.value = '\n'.join(list(app_state.event_log)[: int(cfg.ui.visible_event_entries)])
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


if __name__ in {'__main__', '__mp_main__'}:
    main()
