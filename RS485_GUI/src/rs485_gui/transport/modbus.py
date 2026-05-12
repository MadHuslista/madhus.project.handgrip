"""Modbus RTU polling transport.

``MinimalModbusRTU`` implements a minimal subset of the Modbus RTU protocol
(function codes 0x03 and 0x06) sufficient to poll the acquisition board and
send single-register commands.

``ModbusBoardTransport`` wraps it as a :class:`~rs485_gui.transport.base.BoardTransport`.

Dependency chain: models, constants, core/codec, transport/base
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import serial

from rs485_gui.constants import COMMANDS, READ_REGISTER_COUNT, READ_START_REGISTER
from rs485_gui.core.codec import (
    crc16_modbus,
    decode_modbus_measurement,
    lsl_local_clock,
)
from rs485_gui.models import MeasurementFrame
from rs485_gui.transport.base import BoardTransport

if TYPE_CHECKING:
    from rs485_gui.state import AppState

LOGGER = logging.getLogger(__name__)


class ModbusError(RuntimeError):
    """Raised on any Modbus RTU protocol violation."""


class MinimalModbusRTU:
    """Minimal Modbus RTU master for function codes 0x03 (read) and 0x06 (write).

    Uses a per-instance lock so a single ``MinimalModbusRTU`` object may be
    shared between the worker thread and the command handler without races.
    """

    def __init__(
        self,
        serial_port: serial.Serial,
        slave_id: int,
        inter_frame_gap_s: float = 0.001,
    ) -> None:
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
        # Modbus RTU silent interval = 3.5 character times
        protocol_gap_s = 3.5 * (11.0 / float(baud))
        return max(configured, protocol_gap_s, 0.0005)

    def _read_exact_with_deadline(self, size: int, deadline: float) -> bytes:
        buf = bytearray()
        while len(buf) < size:
            if time.monotonic() >= deadline:
                break
            chunk = self.ser.read(size - len(buf))
            if chunk:
                buf.extend(chunk)
        return bytes(buf)

    def _exchange(self, payload: bytes, expected_function: int) -> bytes:
        frame = payload + crc16_modbus(payload).to_bytes(2, byteorder='little')
        timeout = max(0.01, float(getattr(self.ser, 'timeout', 0.2) or 0.2))
        deadline = time.monotonic() + timeout
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(frame)
            self.ser.flush()
            time.sleep(self._effective_inter_frame_gap_s())
            header = self._read_exact_with_deadline(2, deadline)
            if len(header) < 2:
                raise ModbusError(
                    f'Short response header: expected 2 bytes, got {len(header)}'
                )
            slave_id = header[0]
            function = header[1]
            if function & 0x80:
                rest = self._read_exact_with_deadline(3, deadline)
                response = header + rest
            elif function == 0x03:
                byte_count_raw = self._read_exact_with_deadline(1, deadline)
                if not byte_count_raw:
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
            raise ModbusError(
                f'Invalid RTU response length: got {len(response)} bytes'
            )
        data, received_crc = response[:-2], response[-2:]
        expected_crc = crc16_modbus(data).to_bytes(2, byteorder='little')
        if received_crc != expected_crc:
            note = ''
            active_header = bytes([self.slave_id, 0x03, READ_REGISTER_COUNT * 2])
            if response.count(active_header) >= 2:
                note = (
                    ' (response looks like repeated active-send push frames; '
                    'verify board setting 504.AS=0 for Modbus RTU)'
                )
            raise ModbusError(
                f'CRC mismatch: got {received_crc.hex()}, '
                f'expected {expected_crc.hex()}, '
                f'frame={response.hex(" ")}{note}'
            )
        if slave_id != self.slave_id:
            raise ModbusError(
                f'Unexpected slave id: got {slave_id}, expected {self.slave_id}'
            )
        if function != expected_function and not (function & 0x80):
            raise ModbusError(
                f'Unexpected function: got 0x{function:02X}, '
                f'expected 0x{expected_function:02X}'
            )
        if function & 0x80:
            code = data[2] if len(data) > 2 else None
            raise ModbusError(
                f'Modbus exception function=0x{function:02X} code={code}'
            )
        return response

    def read_holding_registers(
        self, address: int, count: int
    ) -> tuple[list[int], bytes, bytes]:
        """Read *count* holding registers starting at *address*.

        Returns ``(values, request_payload, raw_response)``.
        """
        payload = bytes([
            self.slave_id, 0x03,
            (address >> 8) & 0xFF, address & 0xFF,
            (count >> 8) & 0xFF, count & 0xFF,
        ])
        response = self._exchange(payload, expected_function=0x03)
        raw_without_crc = response[:-2]
        byte_count = raw_without_crc[2]
        expected_byte_count = count * 2
        if byte_count != expected_byte_count:
            raise ModbusError(
                f'Unexpected byte count: got {byte_count}, expected {expected_byte_count}'
            )
        data = raw_without_crc[3:3 + byte_count]
        values = [(data[i] << 8) | data[i + 1] for i in range(0, len(data), 2)]
        return values, payload, response

    def write_single_register(
        self, address: int, value: int
    ) -> tuple[bytes, bytes]:
        """Write *value* to a single holding register at *address*.

        Returns ``(request_payload, raw_response)``.
        """
        payload = bytes([
            self.slave_id, 0x06,
            (address >> 8) & 0xFF, address & 0xFF,
            (value >> 8) & 0xFF, value & 0xFF,
        ])
        response = self._exchange(payload, expected_function=0x06)
        return payload, response


class ModbusBoardTransport(BoardTransport):
    """Polling Modbus RTU transport.

    On each ``read_frames()`` call, issues one FC-03 read and returns a
    single decoded :class:`~rs485_gui.models.MeasurementFrame`.
    """

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.ser: serial.Serial | None = None
        self.client: MinimalModbusRTU | None = None
        self._last_host_ts: float | None = None

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

    def read_frames(self) -> list[MeasurementFrame]:
        return [self._read_once()]

    def _read_once(self) -> MeasurementFrame:
        if self.client is None:
            raise RuntimeError('Transport not connected')

        read_start_reg = int(self.app_state.cfg.device.get('read_start_register', READ_START_REGISTER))
        read_reg_count = int(self.app_state.cfg.device.get('read_register_count', READ_REGISTER_COUNT))

        t_start = time.perf_counter()
        registers, request_payload, response = self.client.read_holding_registers(
            address=read_start_reg,
            count=read_reg_count,
        )
        transaction_duration_s = time.perf_counter() - t_start
        host_ts = time.time()
        host_lsl_ts = lsl_local_clock()

        frame = decode_modbus_measurement(
            registers=registers,
            host_ts=host_ts,
            host_lsl_ts=host_lsl_ts,
            rs485_clock=host_lsl_ts,
            rs485_clock_source='modbus_rtu_host_lsl_clock',
        )

        observed_inter_read_s: float | None = None
        observed_inter_read_hz: float | None = None
        if self._last_host_ts is not None:
            observed_inter_read_s = max(0.0, host_ts - self._last_host_ts)
            if observed_inter_read_s > 0:
                observed_inter_read_hz = 1.0 / observed_inter_read_s
        self._last_host_ts = host_ts

        diagnostics = {
            'timestamp_source': 'host_poll_receive_time',
            'configured_poll_interval_s': float(self.app_state.cfg.device.poll_interval_s),
            'observed_inter_read_s': observed_inter_read_s,
            'observed_inter_read_hz': observed_inter_read_hz,
            'transaction_duration_s': transaction_duration_s,
            'response_bytes': len(response),
        }
        frame.raw_transport['request_hex'] = request_payload.hex(' ')
        frame.raw_transport['response_hex'] = response.hex(' ')
        frame.raw_transport['diagnostics'] = diagnostics
        frame.interpreted.update(diagnostics)
        frame.session_id = self.app_state.get_session_id()
        frame.board_profile = self.app_state.build_board_profile_snapshot()
        return frame

    def send_command(self, command_name: str) -> None:
        if self.client is None:
            raise RuntimeError('Transport not connected')
        if command_name not in COMMANDS:
            raise ValueError(f'Unsupported command: {command_name}')
        cmd_register = int(
            self.app_state.cfg.device.get('command_register', 11)
        )
        value = COMMANDS[command_name]
        request_payload, response = self.client.write_single_register(cmd_register, value)
        self.app_state.push_event(
            f'Sent command {command_name} ({value}) '
            f'request={request_payload.hex(" ")} response={response.hex(" ")}'
        )
