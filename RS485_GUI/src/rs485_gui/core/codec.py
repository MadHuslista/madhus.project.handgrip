"""Pure Modbus RTU / RS485 codec functions.

All functions here are stateless and have no I/O side effects.
They can be unit-tested without any hardware or serial port.

Dependency chain: models, constants  (no I/O, no UI)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from rs485_gui.constants import (
    DECIMAL_CODE_TO_DIGITS,
    STATUS_FLAGS,
    UNIT_CODE_TO_LABEL,
)
from rs485_gui.models import MeasurementFrame

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRC-16 Modbus
# ---------------------------------------------------------------------------

def crc16_modbus(data: bytes) -> int:
    """Compute the CRC-16/Modbus checksum for *data*.

    Returns the 16-bit integer checksum (little-endian wire format).
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


# ---------------------------------------------------------------------------
# Register-level decoding helpers
# ---------------------------------------------------------------------------

def combine_s32_from_words(low_word: int, high_word: int) -> int:
    """Combine two unsigned 16-bit Modbus register words into a signed 32-bit integer.

    The board packs 32-bit values as (low_word, high_word).
    """
    value = ((high_word & 0xFFFF) << 16) | (low_word & 0xFFFF)
    if value & 0x80000000:
        value -= 0x100000000
    return value


def decode_status_word(value: int) -> list[str]:
    """Decode the board status bitfield into a list of active flag names."""
    return [label for bit, label in STATUS_FLAGS.items() if value & (1 << bit)]


def apply_decimal(value: int | None, decimal_code: int) -> float | None:
    """Scale an integer register value by the board decimal-point code."""
    if value is None:
        return None
    digits = DECIMAL_CODE_TO_DIGITS.get(decimal_code, 0)
    return value / (10 ** digits)


# ---------------------------------------------------------------------------
# LSL clock helper (stateless, no pylsl import required at module level)
# ---------------------------------------------------------------------------

def lsl_local_clock() -> float:
    """Return the host clock in the Lab Streaming Layer local-clock domain.

    Falls back to ``time.time()`` when pylsl is not installed.  This keeps
    the GUI functional when IPC is disabled, but IPC startup will reject the
    absence of pylsl when ``ipc.require_pylsl_clock=true``.
    """
    try:
        from pylsl import local_clock as _pylsl_local_clock  # type: ignore[import]
        return float(_pylsl_local_clock())
    except Exception:
        return time.time()


# ---------------------------------------------------------------------------
# Full-frame decoders
# ---------------------------------------------------------------------------

def decode_modbus_measurement(
    registers: list[int],
    host_ts: float,
    host_lsl_ts: float | None = None,
    rs485_clock: float | None = None,
    rs485_clock_source: str = 'host_lsl_clock',
) -> MeasurementFrame:
    """Decode 11 Modbus holding registers into a :class:`~rs485_gui.models.MeasurementFrame`.

    Expects registers in the order documented for PLC addresses 40001–40011:
    [gross_low, gross_high, net_low, net_high, peak_low, peak_high,
     internal_low, internal_high, decimal_code, unit_code, status_word]
    """
    if host_lsl_ts is None:
        host_lsl_ts = lsl_local_clock()
    if rs485_clock is None:
        rs485_clock = host_lsl_ts

    decimal_code = registers[8]
    unit_code = registers[9]
    status_word = registers[10]

    gross_raw = combine_s32_from_words(registers[0], registers[1])
    net_raw = combine_s32_from_words(registers[2], registers[3])
    peak_raw = combine_s32_from_words(registers[4], registers[5])
    internal_raw = combine_s32_from_words(registers[6], registers[7])

    interpreted: dict[str, Any] = {
        'timestamp_host_iso': datetime.fromtimestamp(host_ts).isoformat(timespec='milliseconds'),
        'timestamp_host_epoch_s': host_ts,
        'host_lsl_ts': float(host_lsl_ts),
        'rs485_clock': float(rs485_clock),
        'rs485_clock_source': rs485_clock_source,
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
        # Calibration v2 canonical aliases
        'reference_clock_s': float(rs485_clock),
        'reference_status': status_word,
    }
    interpreted['reference_force_N'] = interpreted.get('net_value')

    raw_transport: dict[str, Any] = {
        'registers': {f'400{idx + 1:02d}': reg for idx, reg in enumerate(registers)},
    }

    return MeasurementFrame(
        host_ts=host_ts,
        host_ts_iso=datetime.fromtimestamp(host_ts).isoformat(timespec='milliseconds'),
        mode='modbus_rtu',
        raw_transport=raw_transport,
        interpreted=interpreted,
        session_id='',
        board_profile={},
    )


def extract_registers_from_modbus_response(
    frame: bytes,
    slave_id: int,
    function_code: int,
    register_count: int,
) -> list[int]:
    """Validate and unpack registers from a raw active-send Modbus response frame.

    Raises :class:`ValueError` on any structural or CRC mismatch.
    """
    expected_byte_count = register_count * 2
    expected_len = 3 + expected_byte_count + 2
    if len(frame) != expected_len:
        raise ValueError(
            f'Unexpected frame length: got {len(frame)}, expected {expected_len}'
        )
    if frame[0] != slave_id:
        raise ValueError(
            f'Unexpected slave id in active-send frame: got {frame[0]}, expected {slave_id}'
        )
    if frame[1] != function_code:
        raise ValueError(
            f'Unexpected function code in active-send frame: '
            f'got 0x{frame[1]:02X}, expected 0x{function_code:02X}'
        )
    if frame[2] != expected_byte_count:
        raise ValueError(
            f'Unexpected byte count in active-send frame: '
            f'got {frame[2]}, expected {expected_byte_count}'
        )
    received_crc = frame[-2:]
    expected_crc = crc16_modbus(frame[:-2]).to_bytes(2, byteorder='little')
    if received_crc != expected_crc:
        raise ValueError(
            f'CRC mismatch in active-send frame: '
            f'got {received_crc.hex()}, expected {expected_crc.hex()}, '
            f'frame={frame.hex(" ")}'
        )
    data = frame[3:-2]
    return [(data[i] << 8) | data[i + 1] for i in range(0, len(data), 2)]


def decode_active_send_modbus_response(
    frame: bytes,
    host_ts: float,
    host_lsl_ts: float,
    slave_id: int,
    function_code: int,
    register_count: int,
    diagnostics: dict[str, Any],
) -> MeasurementFrame:
    """Decode one binary active-send push frame into a :class:`~rs485_gui.models.MeasurementFrame`."""
    registers = extract_registers_from_modbus_response(
        frame, slave_id, function_code, register_count
    )
    decoded = decode_modbus_measurement(
        registers=registers,
        host_ts=host_ts,
        host_lsl_ts=host_lsl_ts,
        rs485_clock=host_lsl_ts,
        rs485_clock_source='active_send_reconstructed_lsl_clock',
    )
    decoded.mode = 'active_send'
    decoded.raw_transport = {
        'response_hex': frame.hex(' '),
        'frame_length_bytes': len(frame),
        'frame_type': 'modbus_rtu_response_push',
        'registers': {f'400{idx + 1:02d}': reg for idx, reg in enumerate(registers)},
        'diagnostics': diagnostics,
    }
    decoded.interpreted.update({
        'parser_profile': 'modbus_rtu_response_11regs',
        'parsed_from': 'active_send_binary_modbus_response',
        'timestamp_source': 'host_receive_time',
    })
    return decoded


# ---------------------------------------------------------------------------
# Utility formatting used by multiple subsystems
# ---------------------------------------------------------------------------

def truncate_text(text: str, max_chars: int) -> str:
    """Truncate *text* to at most *max_chars*, appending an omission notice."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    keep = max(16, max_chars - 24)
    omitted = len(text) - keep
    return f'{text[:keep]} ... (+{omitted} chars)'


def build_log_text(items: list[str], separator: str, max_total_chars: int) -> str:
    """Join *items* with *separator*, truncating once *max_total_chars* is exceeded."""
    if max_total_chars <= 0:
        return separator.join(items)
    selected: list[str] = []
    used = 0
    total_items = len(items)
    for idx, item in enumerate(items):
        extra = len(item) + (len(separator) if selected else 0)
        if used + extra > max_total_chars:
            remaining = total_items - idx
            selected.append(
                f'... truncated, {remaining} older entr{"y" if remaining == 1 else "ies"} hidden ...'
            )
            break
        selected.append(item)
        used += extra
    return separator.join(selected)
